# Spec — `app/managers/account_invoice_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092
> **Revision 2026-11-17 (owner, OQ-47 from the return manager specs):** new `void_invoice` R3c [BUG-2788]: voiding a return credit note cancels its pending return, and is refused for a completed return. Placed here for the same reason as O1 (every void path goes through this manager), decided by Claude under the reviewer's delegation (2026-11-17). R3b is narrowed by R3c. Still APPROVED. Cards to revise: R3b cards; new R3c cards.
> **Revision 2026-11-14 (apply-review, owner chat "Invoice lock after completion"):** added the completed-order freeze (Shared: *Completed-order freeze* F1–F7) and its rules `delete_invoice` R2a [BUG-2730], `revert_to_draft` R2a [BUG-2733], R2b [BUG-2730], R3a [BUG-2736], `void_invoice` R3a [BUG-2731], R3b; note on the dead `locked` status (BUG-2735) in the Overview. Placement decided: the check lives in this manager (see *Owner decision O1* below). Still APPROVED — every point was answered by the owner; detail texts and the "order's invoice" definition are best-practice defaults, delegated by reviewer. Cards to revise: see Gap log R1. **2026-11-14, later:** owner answered O1 follow-up (e); added `update_invoice` R3b (the three admin edits stay allowed on a completed order).

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically

- **HR-9** `update_invoice` R13 — a draft update stamps `updated_by` even when the request is empty or every value equals the stored one. Intended: `updated_by` written only when at least one field actually changes value. — 🐞 BUG-620
**Answer:** bug — per HR-9 (house rule)
- **HR-9** `update_invoice` R6 — a confirmed-invoice update stamps `updated_by` whenever an editable field is present in the request, even if its value is unchanged. Intended: only when a value actually changes. — 🐞 BUG-620
**Answer:** bug — per HR-9 (house rule)
- **HR-10** `confirm_invoice` R1 — invoice read without a row lock; two concurrent confirms (or confirm racing void/update/item edits) can both pass the status check. Intended: row read `FOR UPDATE`; the loser sees the new state and gets the normal 400. — 🐞 BUG-621
**Answer:** bug — per HR-10 (house rule)
- **HR-10** `revert_to_draft` R1 — no row lock; a payment recorded concurrently (payment recording does lock the invoice) can land on an invoice that is being reverted. Intended: row read `FOR UPDATE`. — 🐞 BUG-621
**Answer:** bug — per HR-10 (house rule)
- **HR-10** `void_invoice` R1 — no row lock; a payment recorded between the payment scan and the commit stays active on a voided invoice. Intended: row read `FOR UPDATE` (payment recording already locks the same row, so the two serialize). — 🐞 BUG-621
**Answer:** bug — per HR-10 (house rule)
- **HR-10** `delete_invoice` R1 — no row lock; a concurrent confirm can pass while the draft is being deleted. Intended: row read `FOR UPDATE`. — 🐞 BUG-621
**Answer:** bug — per HR-10 (house rule)
- **HR-10** `update_invoice` R1 — no row lock; a draft-only edit (e.g. `account_id`) can be applied to an invoice another request is confirming. Intended: row read `FOR UPDATE`. — 🐞 BUG-621
**Answer:** bug — per HR-10 (house rule)
- **HR-10** `set_receiving_started` R1 — no row lock; two concurrent receipts can both see the flag unset and log two `receiving_started_set` events (duplicate side effect). Intended: row read `FOR UPDATE`; the second call is a no-op. — 🐞 BUG-621
**Answer:** bug — per HR-10 (house rule)
- **HR-8** `list_invoices` R11 (shared filter; also `list_invoices_page`, `summarize_invoices`) — `account_name_search` is placed in `ILIKE '%…%'` unescaped: `%` or `_` alone matches every account. Intended: `%`, `_` and `\` matched literally. Fix in `app/dao/account_invoice.py`. — 🐞 BUG-622
**Answer:** bug — per HR-8 (house rule)
- **HR-8** `list_invoices` R10 (shared filter) — the "search text is all digits → also match invoice id" shortcut uses Unicode `isdigit()`: `"²"` crashes with `ValueError` (500), `"١٢"` matches invoice 12. Intended: only ASCII `0-9` triggers the id match; other digits never raise. Fix in `app/dao/account_invoice.py`. — 🐞 BUG-622
**Answer:** bug — per HR-8 (house rule)
- **HR-8** `list_accounts_hub_page` R4 — hub `search` placed in `ILIKE '%…%'` unescaped. Intended: `%`, `_` and `\` matched literally. — 🐞 BUG-622
**Answer:** bug — per HR-8 (house rule)
- **HR-6** `list_accounts_hub_page` R6 — hub page ordered by account name **case-sensitively** (`"apex"` sorts after `"Zeta"`), then `id`. Intended: name case-insensitive ascending, then `id` ascending. — 🐞 BUG-623
**Answer:** bug — per HR-6 (house rule)

### Precedent matches — confirm all with ok

### P1. Linked order type accepts any text — 🐞 BUG-624
**Background:** an invoice can be linked to an order through `order_type` + `order_id`. Recognised types elsewhere in the code are `purchase_order`, `expense_order`, `sales_order`, `work_order`.
**What happens today:** `create_invoice` stores any `order_type` string up to 30 characters as typed (`"Purchase_Order"`, `"po"`, `"banana"`).
**Example:** `POST /invoices` with `order_type: "Purchase_Order"` succeeds; order-number search and "resync items" never recognise the link, and resync silently syncs zero items.
**Rules affected:** `create_invoice` R9a
**Answer:** bug — per BUG-022 precedent: `order_type` trimmed + lower-cased and only `purchase_order`/`expense_order`/`sales_order`/`work_order` accepted, anything else 422 (fix in `AccountInvoiceCreate`) (precedent — confirmed: ok)
**Resolution:** `order_type` trimmed + lower-cased, restricted to the four known values, 422 otherwise (fix lives in `AccountInvoiceCreate`). Rules: `create_invoice` R9a.

### P2. Linked order id is never checked — 🐞 BUG-625
**Background:** `order_id` has no foreign key (it is polymorphic) — nothing in the database checks it.
**What happens today:** `create_invoice` and a draft `update_invoice` store any `order_id`: a non-existent id, or the id of an order in another workspace.
**Example:** workspace A creates an invoice with `order_type: "purchase_order", order_id: 999` where PO 999 belongs to workspace B; the invoice is saved, and "resync items" later fails with 404 for a link the user was allowed to create.
**Rules affected:** `create_invoice` R9b, `update_invoice` R2b, R12
**Answer:** bug — per BUG-340 precedent: when `order_id` is given it must name an existing, live order of the given `order_type` in the same workspace, otherwise 404 and nothing written (precedent — confirmed: ok)
**Resolution:** `order_id`, when given, validated to exist, be live and belong to the workspace for the given `order_type`; 404 otherwise, nothing written. Rules: `create_invoice` R9b, R9c, `update_invoice` R2b, R12, R12a (R9c/R12a added in fill-gaps G5/G13; R2b — `order_type` sendable on update — added in fill-gaps G15).

### P3. Whitespace-only void reason accepted — 🐞 BUG-626
**Background:** voiding requires a reason (`VoidInvoiceRequest.void_note`, min length 1); the reason is stored permanently on the invoice and copied onto every auto-voided payment.
**What happens today:** `"   "` passes the schema and the manager stores it as the reason.
**Example:** a user voids a paid invoice with reason `"   "`; the invoice and its payments show an empty void reason forever.
**Rules affected:** `void_invoice` R8
**Answer:** bug — per BUG-004/BUG-125 precedent: `VoidInvoiceRequest` strips whitespace and rejects a blank/whitespace-only `void_note` with 422; stored trimmed (precedent — confirmed: ok)
**Resolution:** `VoidInvoiceRequest` trims `void_note` and rejects blank/whitespace-only with 422; the manager still just stores whatever (now-validated, trimmed) string it receives. Rules: `void_invoice` R8.

### New questions

### Q1. The amount entered when creating an invoice is thrown away at confirmation — 🐞 BUG-627
**Background:** invoices have line items. Confirming ("finalizing") recomputes `invoice_amount` as the sum of the items' line subtotals. `POST /invoices` requires an `invoice_amount`, and a draft's amount cannot be edited afterwards (see Q5).
**What happens today:** confirm always replaces the stored amount with the item total, whatever was entered at creation.
**Example:** a user creates a manual payable invoice for 1,000.00 and confirms it without adding line items; the confirmed invoice is worth 0.00 (and shows as `paid`). With one 400.00 item it becomes 400.00, not 1,000.00.
**Rules affected:** `create_invoice` R9, `confirm_invoice` R4, `_recalculate_invoice_amount` R1–R3
**Suggested answer:** bug — the invoice amount is always the sum of its line items: create does not accept a client amount (draft starts at 0.00 and follows its items), so nothing entered is silently discarded
**Answer:** bug — invoice amount is always the sum of its line items; create does not accept a client amount (draft starts at 0.00 and follows its items) (reviewer accepted suggestion)
**Resolution:** `invoice_amount` removed from `AccountInvoiceCreate`; a new draft always starts at 0.00 and follows its items from creation (`_recalculate_invoice_amount` stays correct as-is — it is the source of truth, not the bug). Rules: `create_invoice` R9.

### Q2. An invoice with no line items can be confirmed — 🐞 BUG-628
**Background:** see Q1 — the confirmed amount is the item total.
**What happens today:** confirming a draft with zero items succeeds; the invoice is finalized at 0.00 and, because paid (0) ≥ amount (0), its payment status becomes `paid`.
**Example:** a user clicks "Finalize" on an empty draft; a 0.00 confirmed invoice marked `paid` appears in the account's history.
**Rules affected:** `confirm_invoice` R4
**Suggested answer:** bug — confirming a draft with no line items is rejected with 400 ("Add at least one line item before confirming"), nothing changed
**Answer:** bug — confirming a draft with no line items is rejected with 400, nothing changed (reviewer accepted suggestion)
**Resolution:** confirm requires at least one line item; zero items → 400, nothing changed. Rules: `confirm_invoice` R4.

### Q3. Moving a draft to another account skips the account checks that create applies — 🐞 BUG-629
**Background:** accounts can be deactivated (`is_active = False`) or barred from invoicing (`allow_invoices = False`). Creating an invoice for such an account is refused (400 / 403).
**What happens today:** changing a draft's `account_id` checks only that the account exists in the workspace and is not deleted; an inactive account or one with invoices disabled is accepted.
**Example:** account "Old Supplier" is inactive; creating an invoice for it fails with 400, but creating it for "Acme" and then editing the draft to "Old Supplier" succeeds.
**Rules affected:** `update_invoice` R10
**Suggested answer:** bug — a draft's new account passes the same checks as create: deleted → 400 "Cannot assign invoice to deleted account", inactive → 400, `allow_invoices = False` → 403
**Answer:** bug — new account passes the same checks as create: deleted 400, inactive 400, allow_invoices false 403 (reviewer accepted suggestion)
**Resolution:** draft account-change now applies the same four checks as `create_invoice` R1–R4. Rules: `update_invoice` R10, R10a (`account_id = 0` → 404, added in fill-gaps G6).

### Q4. Sending `null` for a required field fails with a database error — 🐞 BUG-630
**Background:** the update schema makes every field optional and allows explicit `null`. The update keeps every field the client sent, including `null`s.
**What happens today:** `null` for a column that cannot be empty (`account_id`, `invoice_type`, `invoice_date`, `allow_payments`) reaches the database and fails with a not-null violation, which the app answers with a generic 400 conflict error; nothing is saved.
**Example:** `PUT /invoices/5` with `{"invoice_date": null}` on a draft (or `{"allow_payments": null}` on a confirmed invoice) returns 400 "Resource Conflict" instead of a validation message naming the field.
**Rules affected:** `update_invoice` R5, R12
**Suggested answer:** bug — `AccountInvoiceUpdate` rejects `null` for `account_id`, `invoice_type`, `invoice_date` and `allow_payments` with 422 naming the field; nullable fields (`due_date`, `description`, `notes`, `invoice_number`, `vendor_invoice_number`, `payment_locked_reason`, `order_id`) can still be cleared with `null`
**Answer:** bug — AccountInvoiceUpdate rejects null for non-nullable fields with 422 naming the field; nullable fields can still be cleared (reviewer accepted suggestion)
**Resolution:** combined with Q5 into one schema-level fix (BUG-630 — same `AccountInvoiceUpdate` change). Rules: `update_invoice` R2a.

### Q5. `invoice_amount` in an update request is silently ignored — 🐞 BUG-630
**Background:** the update schema has an `invoice_amount` field.
**What happens today:** on a draft it is dropped before saving; on a confirmed invoice it is not in the editable set. The request succeeds (200) and the amount is unchanged.
**Example:** a user edits a draft's amount from 500.00 to 750.00; the response is 200 but the invoice still says 500.00.
**Rules affected:** `update_invoice` R5, R12
**Suggested answer:** bug — a request that sets `invoice_amount` is rejected with 422 ("amount is derived from line items"); remove the field from `AccountInvoiceUpdate`
**Answer:** bug — a request setting invoice_amount is rejected with 422; remove the field from AccountInvoiceUpdate (reviewer accepted suggestion)
**Resolution:** `invoice_amount` removed from `AccountInvoiceUpdate`; any value in the request → 422 (same schema change as Q4, logged as one bug, BUG-630). Rules: `update_invoice` R2a, R11.

### Q6. Editing a confirmed invoice silently ignores non-editable fields — 🐞 BUG-631
**Background:** once confirmed, only `allow_payments`, `payment_locked_reason` and `due_date` may change.
**What happens today:** any other field in the request (description, notes, invoice number, account, dates, type) is dropped without an error; if none of the three editable fields is present the call returns 200 with the invoice unchanged.
**Example:** a user edits a confirmed invoice's `notes` and `due_date`; the response is 200, the due date changes, the notes do not, and nothing tells the user.
**Rules affected:** `update_invoice` R4, R5
**Suggested answer:** bug — a confirmed-invoice update that includes any field outside the editable three (with a value different from the stored one) is rejected with 400 naming those fields, nothing saved (internal callers only send header changes for drafts)
**Answer:** bug — a confirmed-invoice update including changed non-editable fields is rejected with 400 naming them, nothing saved (reviewer accepted suggestion)
**Resolution:** any sent field outside the editable three whose value differs from what is stored now rejects the whole update with 400, naming the field(s); a same-value resend of such a field stays a silent no-op. Rules: `update_invoice` R4, R4a.

### Q7. Change events are logged when nothing changed — 🐞 BUG-632
**Background:** every invoice has an activity log (events). Updates write events such as "Due date updated" and "Payments enabled".
**What happens today:** on a confirmed invoice, an event is logged for every editable field present in the request even when its value is unchanged (e.g. `due_date_changed` with old = new). On a draft, "Invoice details updated" is logged on every successful update, including an empty request.
**Example:** the UI saves a confirmed invoice with `allow_payments: true` (already true); the activity log gains "Payments enabled" although nothing happened.
**Rules affected:** `update_invoice` R7–R9, R14
**Suggested answer:** bug — an event is logged only for fields whose value actually changed; a draft update that changes nothing logs no event, and its metadata lists only changed fields
**Answer:** bug — events logged only for fields whose value actually changed; no-op draft update logs no event (reviewer accepted suggestion)
**Resolution:** confirmed-path events (R7–R9) now fire only when the field's value actually changes; draft-path event (R14) now fires only when at least one field changed, with metadata limited to the changed fields. Rules: `update_invoice` R7, R8, R9, R14.

### Q8. Confirm, revert, void and receiving-started do not record who changed the invoice — 🐞 BUG-633
**Background:** invoices have `updated_by` ("last changed by"); `updated_at` is refreshed automatically by the database on every change.
**What happens today:** edits set `updated_by`, but confirm, revert-to-draft, void and setting the receiving flag do not, so `updated_at` moves while `updated_by` still names whoever last edited details (the acting user is only in the event log).
**Example:** Alice edits a draft; Bob confirms and later voids it. The invoice shows "updated by Alice" with the void's timestamp.
**Rules affected:** `confirm_invoice` R5, `revert_to_draft` R5, `void_invoice` R6, `set_receiving_started` R3
**Suggested answer:** bug — each of these actions sets `updated_by` to the acting user (`set_receiving_started`: to `performed_by` when given)
**Answer:** bug — each action sets updated_by to the acting user (reviewer accepted suggestion)
**Resolution:** each of the four actions now sets `updated_by` (confirm/revert/void → `user_id`; `set_receiving_started` → `performed_by`). Rules: `confirm_invoice` R5, `revert_to_draft` R5, `void_invoice` R6, `set_receiving_started` R3.

### Q9. Draft invoices count as open balances — 🐞 BUG-634
**Background:** a draft is not yet finalized (its amount can still change and payments cannot be recorded against it). "Open balance" lists and KPIs include every non-voided invoice whose payment status is unpaid/partial/overdue.
**What happens today:** drafts are included in: the open-invoices list for an account, the hub KPIs (open count, outstanding total, accounts with open balance) and the accounts-hub per-account rollups.
**Example:** a purchase order creates a 5,000.00 draft invoice for Acme; the dashboard immediately shows 5,000.00 payable to Acme and lists the draft among open invoices to pay, although payment against it is refused.
**Rules affected:** `list_open_invoices_page` R2, `get_invoices_hub_summary` R2–R4, `list_accounts_hub_page` R2
**Suggested answer:** bug — open-balance lists, KPIs and rollups count only confirmed invoices
**Answer:** bug — open-balance lists, KPIs and rollups count only confirmed invoices (reviewer accepted suggestion)
**Resolution:** combined with Q10 (same fix concept — exclude drafts from money/open-balance views). Rules: `list_open_invoices_page` R2, `get_invoices_hub_summary` R2, `list_accounts_hub_page` R2, `summarize_invoices` R2.

### Q10. Invoice summary totals include drafts — 🐞 BUG-634
**Background:** the account invoice summary returns count, invoiced total, paid total and outstanding total for the current filters. Voided invoices are excluded from the money totals.
**What happens today:** drafts are included in the invoiced and outstanding totals (the count covers every matching invoice, voided included).
**Example:** Acme has one confirmed 1,000.00 invoice and one 5,000.00 draft; the summary shows invoiced 6,000.00, outstanding 6,000.00.
**Rules affected:** `summarize_invoices` R2
**Suggested answer:** bug — money totals include only confirmed invoices; the count keeps covering all matching invoices
**Answer:** bug — money totals include only confirmed invoices; count still covers all matches (reviewer accepted suggestion)
**Resolution:** logged together with Q9 as one bug (BUG-634): every open-balance/money view now excludes drafts; `summarize_invoices`'s `invoice_count` is unaffected (still counts everything matching, voided included). Rules: `summarize_invoices` R2.

### Q11. No invoice ever becomes "overdue" — 🐞 BUG-635
**Background:** `payment_status` is documented as `unpaid`/`partial`/`paid`/`overdue`, and the hub reports an overdue count per type and an "has overdue" flag per account.
**What happens today:** nothing in the backend ever sets `overdue`; recalculation always yields unpaid/partial/paid. Overdue counts are always 0 and the `overdue` filter always returns nothing.
**Example:** an invoice due 2026-01-01 and still unpaid in September shows `unpaid`; the hub says "0 overdue".
**Rules affected:** `_recalculate_payment_status` R1–R3, `get_invoices_hub_summary` R2, `list_accounts_hub_page` R3
**Suggested answer:** bug — overdue is derived at query time: a confirmed invoice with an open balance and `due_date` before today counts as overdue (in counts, flags and the `payment_status=overdue` filter)
**Answer:** bug — overdue derived at query time: confirmed, open balance, due_date before today (reviewer accepted suggestion)
**Resolution:** `_recalculate_payment_status` is unchanged (it correctly only ever stores paid/partial/unpaid — that was never the bug); "overdue" becomes a query-time derivation wherever it is reported. Rules: `get_invoices_hub_summary` R2, `list_accounts_hub_page` R3, `list_invoices` R5a (the `payment_status=overdue` filter — added in fill-gaps G4).

### Q12. Hub "accounts with open balance" counts accounts the hub list hides — 🐞 BUG-636
**Background:** accounts can be deactivated. The accounts hub lists only active accounts, and `total_active_accounts` counts only active ones.
**What happens today:** the open-balance KPIs (`accounts_with_any_open_balance`, per-type `accounts_with_open_count`, open counts and totals) include invoices of inactive accounts, but the hub list and its payable/receivable sections never show those accounts.
**Example:** inactive "Old Supplier" still has a 2,000.00 unpaid bill. The hub says "3 accounts with open payables, 12,000.00" but the Payable section lists only 2 accounts summing to 10,000.00.
**Rules affected:** `get_invoices_hub_summary` R2–R3, `list_accounts_hub_page` R1–R2
**Suggested answer:** bug — the hub list also shows inactive accounts that still have an open balance (in every section), so the list and the KPIs cover the same accounts; `total_active_accounts` unchanged
**Answer:** bug — hub list also shows inactive accounts that still have an open balance; total_active_accounts unchanged (reviewer accepted suggestion)
**Resolution:** `get_invoices_hub_summary` was already correct (R1 already counts inactive accounts); the fix is entirely in `list_accounts_hub_page` R1, which now also admits inactive accounts with an open balance. Rules: `list_accounts_hub_page` R1.

### Q13. A whitespace-only invoice-number search returns almost nothing — 🐞 BUG-637
**Background:** the invoice-number search box matches invoice number, vendor invoice number and linked order numbers. Search text is trimmed.
**What happens today:** `"   "` counts as a search; after trimming it becomes an empty pattern that only matches invoices whose number is exactly empty, so the list is (nearly) empty.
**Example:** a user types a space in the search box; the invoice list goes blank instead of showing all invoices.
**Rules affected:** `list_invoices` R9
**Suggested answer:** bug — a blank or whitespace-only search is treated as no search filter
**Answer:** bug — blank/whitespace-only search treated as no search filter (reviewer accepted suggestion)
**Resolution:** a blank/whitespace-only `invoice_number_search` (after trimming) is now treated as "no filter". Rules: `list_invoices` R9a.

### Q14. "Manual items update" branch of item sync is never used — remove, dead code
**Background:** `sync_items_from_list` has an `is_manual` flag that changes the logged event to "Items updated" (`item_manually_updated`).
**What happens today:** no caller ever passes `is_manual=True`; every sync is logged as `items_synced` "Items synced from order (N lines)".
**Example:** unreachable from any endpoint or service.
**Rules affected:** `sync_items_from_list` R8
**Suggested answer:** remove
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** `sync_items_from_list` R8 (the `is_manual=True` branch) removed from scope — dead code, confirmed unreachable (no caller anywhere in `app/` or `tests/` passes `is_manual=True`). Logged to `account_invoice_manager.deadcode-staging.md`, not a bug, no BUG ID.

### Q15. Events recorded at the same instant come back in no fixed order — 🐞 BUG-638
**Background:** the activity log is returned newest first by timestamp. One update can write up to three events within the same request.
**What happens today:** events with identical timestamps have no tie-breaker, so their order can differ between calls.
**Example:** an update changing due date, payments flag and lock reason writes three events; the log shows them in varying order on refresh.
**Rules affected:** `get_events` R2
**Suggested answer:** bug — ties broken by event `id` descending (newest insert first)
**Answer:** bug — ties broken by event id descending (reviewer accepted suggestion)
**Resolution:** combined with Q16 into one bug (same root cause — missing tie-breaker on a "returned in some order" list). Rules: `get_events` R2.

### Q16. Line items with the same line number come back in no fixed order — 🐞 BUG-638
**Background:** items are returned ordered by `line_number`. Items added one by one through the item endpoints default to line number 1.
**What happens today:** items sharing a line number have no tie-breaker; their order can change between calls.
**Example:** three manually added items all have line number 1; the invoice shows them in a different order after a refresh.
**Rules affected:** `get_items` R2
**Suggested answer:** bug — ties broken by item `id` ascending
**Answer:** bug — ties broken by item id ascending (reviewer accepted suggestion)
**Resolution:** logged together with Q15 as one bug (BUG-638). Rules: `get_items` R2.

### Q17. A draft that once had (voided) payments cannot be deleted — 🐞 BUG-639
**Background:** payments can be voided individually; voided payment rows stay. A confirmed invoice whose payments are all voided can be reverted to draft. Deleting a draft is a hard delete.
**What happens today:** deleting such a draft fails: the ORM tries to detach the voided payment rows by setting their invoice reference to empty, which the database refuses (not-null), so the delete errors out (generic 400 conflict) and nothing is deleted. Invoice status-history rows from the old tracker behave the same way.
**Example:** invoice #7 confirmed → payment 100.00 recorded → payment voided → reverted to draft → "Delete" fails with a database error.
**Rules affected:** `delete_invoice` R4
**Suggested answer:** bug — deleting a draft that has payment rows (even voided) is refused with a clear 400 ("Invoice has payment history — confirm and void it instead"); drafts without payment rows delete as today
**Answer:** bug — delete of a draft with payment rows (even voided) is refused with a clear 400 telling the user to confirm and void instead (reviewer accepted suggestion)
**Resolution:** a draft with `invoice_payments` rows (or legacy status-history rows) is now refused up front with a clear 400, instead of failing at flush with a generic conflict. Rules: `delete_invoice` R4.

### Owner decision O1 (chat, 2026-11-14). Invoices of completed orders are frozen: 🐞 BUG-2730, BUG-2731, BUG-2733, BUG-2736
**Background:** an order (purchase, sales, expense, work) points at its own invoice through `<order>.invoice_id`. Return credit notes are separate invoices, created and confirmed when a return starts. They name the same order through `order_type` / `order_id`, and the return row (`purchase_order_returns` / `sales_order_returns`) points at them through `invoice_id`.
**What happened before:** revert, void and delete never read the order. A completed sales, expense or work order's invoice could be reverted, edited and re-confirmed, voided (which cancels its payments) or deleted. A credit note could be reverted to draft and its items edited. A revert blocked by receiving told the user to "zero out received quantities", which they cannot do.
**Answer:** owner in chat, 2026-11-14 (recorded in `docs/testing/owner-questions.md`, "Invoice lock after completion"). Once the linked order is completed (any type), its invoice is fully frozen: revert, void and delete are refused with 400 and nothing is written. Payments may still be recorded or voided. Mistakes are fixed with a credit note or return. Return credit notes are never editable after creation: to correct one, void it and make a new return. Related: a completed PO, or one with goods received, can't be voided (BUG-2734, in `purchase_order_service`, not here).
**Resolution:** rules `delete_invoice` R2a, `revert_to_draft` R2a, R2b, R3a, `void_invoice` R3a, R3b, built on the shared *Completed-order freeze* F1–F7.
**Placement (decided by Claude, delegated by reviewer):** the check belongs in **this manager**, not only in `account_invoice_service`. Today the manager reads only the invoice row, but it has the session and can read the four order tables, `statuses` and the two return tables itself. The BUG-625 fix (`create_invoice` R9d) already makes it read order rows by type. The manager is the one choke point: besides the invoice endpoints, `delete_invoice` / `void_invoice` are called directly by the PO, sales, expense and work-order services (section unconfirm, order void, return cancel). A service-only check would leave those paths able to bypass the freeze.
**Follow-ups for the `account_invoice_service` spec (not written yet):**
- (a) BUG-2732: `delete_invoice` unlinks every order type, not only POs.
- (b) The service's own PO guard on `/void` (any PO line with `quantity_received > 0` → 400 `Cannot void invoice after receiving has been recorded on the linked order`) runs before the manager and stays as it is.
- (c) The manager's freeze 400s pass through unchanged, and the transaction is rolled back.
- (d) BUG-2734 belongs to the `purchase_order_service` spec.
- (e) **Owner, 2026-11-14 (second answer, recorded in `owner-questions.md`):** the three edits a confirmed invoice still allows (`update_invoice` R3: `due_date`, `allow_payments`, `payment_locked_reason`) stay editable after the order is completed, because they don't change the invoice's money. Rule: `update_invoice` R3b. This is today's behavior, not a bug.

## Overview
`AccountInvoiceManager` owns the lifecycle of account invoices (payables and receivables): draft → confirmed → voided (terminal), with revert confirmed → draft and hard delete of drafts. It creates invoices for accounts, edits them (fully while draft, only admin fields + due date once confirmed), replaces line items from orders (`sync_items_from_list`), recomputes amounts and payment status, voids invoices together with their payments, and appends an activity event for each action. It also forwards list, summary and hub queries to the invoice DAO. Callers: `AccountInvoiceService` (invoice endpoints), purchase/expense/sales/work-order services (auto-created invoices), `PurchaseOrderManager` (receiving flag), `InvoicePaymentManager`/`AttachmentManager` and the invoice-item endpoints (`_log_event`, `_recalculate_invoice_amount`). Invariants it protects: workspace isolation (other workspace → 404), no edits to voided invoices, confirmed amount frozen from items, voided invoices have no active payments and zero paid amount. Since the 2026-11-14 owner decision (O1): a completed order's invoice can't be reverted, voided or deleted, and a return credit note can't be reverted.

**Invoice statuses:** `invoice_status` only ever holds `draft`, `confirmed` or `voided`, and this manager sets and checks only those three. Other modules also test for a fourth value, `locked`, but nothing ever sets it, so those checks never fire (🐞 BUG-2735, `dead-status`; decided together with the BUG-2730 fix). The freeze is **not** a stored status. It is worked out from the linked order's state each time (F1–F7), so no rule here reads or writes `locked`. A test must never set `invoice_status = "locked"` to simulate a frozen invoice.

**Callables:** 21 specified · 1 not specified
**Externals to mock:** `utcnow` (patch `app.managers.account_invoice_manager.utcnow`; note `InvoiceEvent.created_at` / `InvoiceItem.created_at` column defaults call `app.utils.time.utcnow` directly and are not affected by that patch)
**Integration-only behavior:** none (all queries run on the test Postgres)

**Notes for the test designer**
- Managers never commit; everything below is "flushed, not committed" unless stated.
- Events are rows in `invoice_events` (`event_type`, `description`, `metadata_json`, `performed_by`, `workspace_id`, `invoice_id`); assert on them via the database.
- Fixtures need: workspace(s), profile(s), `accounts` rows (`is_active`, `is_deleted`, `allow_invoices` flags), `account_invoices`, `invoice_items`, `invoice_payments`. `account_invoices.account_id` is `ON DELETE RESTRICT`.
- Order-number search needs `purchase_orders` / `expense_orders` / `sales_orders` / `work_orders` rows (columns `po_number`, `expense_number`, `sales_order_number`, `work_order_number`, `invoice_id`, `workspace_id`).
- Rules tagged `[BUG-NNN]` state the **intended** behavior and are expected to fail until the code changes — the `*(Today: …)*` note in each keeps current behavior visible for tests that must still assert what happens now (e.g. to prove the xfail actually fails for the stated reason).
- 20 new bugs from this review are logged in `account_invoice_manager.bugs-staging.md` (BUG-620–BUG-639, not yet merged into `docs/testing/bugs.md`); the dead `sync_items_from_list(is_manual=True)` branch is logged in `account_invoice_manager.deadcode-staging.md`.
- (G1) While `AccountInvoiceCreate.invoice_amount` still exists (BUG-627 unfixed), passing cases must build the schema with `invoice_amount=0.00` only if the field is present (e.g. a helper that adds it when `"invoice_amount" in AccountInvoiceCreate.model_fields`), so they keep passing after the fix.
- (G3) "Today" for overdue (BUG-635) is the application clock, `utcnow().date()` — patch `app.managers.account_invoice_manager.utcnow` to pin it (see `get_invoices_hub_summary` R2). Until the fix exists, choose due dates far from any real "today" (e.g. 2020-01-01 overdue, 2099-12-31 not) for the today-passing parts.
- (G7) Legacy status-history rows live in `invoice_status_tracker` (model `InvoiceStatusTracker`): `workspace_id` (not null), `invoice_id` (not null, FK `ON DELETE CASCADE`), `from_status` / `to_status` (not null, ≤ 20 chars, e.g. `"draft"` → `"confirmed"`), `changed_by` (nullable profile id), `changed_at` (not null datetime). Exposed on the invoice as the ORM backref `status_history` (no `passive_deletes`).
- (G8) Tables whose `invoice_id` points at an invoice with `ON DELETE SET NULL`: `purchase_orders`, `expense_orders`, `sales_orders`, `work_orders`, `purchase_order_returns`, `sales_order_returns`, `machine_item_ledger`, `project_component_item_ledger`. Ledger rows are heavy to build (`machine_item_ledger` needs `machine_id`, `item_id`, `transaction_type`, `quantity`, `unit_cost`, `total_cost`, `qty_before`, `qty_after`, `source_type`, `performed_by`); one ledger table is enough to prove `delete_invoice` R3.
- (G10) Event / item `created_at` comes from a per-row Python default, so two rows inserted separately normally differ by microseconds; to create a real tie set `created_at` (events) or `line_number` (items) explicitly to equal values. For a strict xfail on BUG-638 to fail today, the setup must make the heap order differ from the intended order (e.g. update the lower-id row so it moves to the end of the heap). If the executor still sees an XPASS, report it back as a gap — do not drop the case.
- (G14) Order rows have no common soft-delete flag: a non-live purchase or expense order is built with `voided = True`; a non-live work order with `is_deleted = True` (or `status = "VOIDED"`); a sales order cannot be non-live. Never set `is_deleted` on `purchase_orders` / `expense_orders` / `sales_orders` — the column does not exist. See `create_invoice` R9d.
- (O1) Completed orders, for the freeze (F2):
  - **PO:** `current_status_id` → a `statuses` row named `"Complete"`. Every `purchase_orders` row needs a `current_status_id` (NOT NULL), so a "not completed" PO points at a status named `"Draft"`, `"Planning"` or `"Receiving"`.
  - **Sales order:** `order_completed = True`.
  - **Expense order:** `completed_at` set to any datetime.
  - **Work order:** `status = "COMPLETED"`.
  - A **not completed** order must be set up explicitly: PO stage `Draft`, SO `order_completed = False`, EO `completed_at = None`, WO `status = "DRAFT"`.
  - A **return credit note** (F6) is an invoice whose id is in `purchase_order_returns.invoice_id` or `sales_order_returns.invoice_id` of the same workspace. It carries `order_type` / `order_id` of the order, but the order's own `invoice_id` points elsewhere (or is NULL).
- (G11) Account names are **not** unique within a workspace (`accounts.name` has an index but no unique constraint), so two accounts both named `"Acme"` (or `"Acme"` and `"acme"`) are a valid setup for the `id` tie-break of `list_accounts_hub_page` R6.

## Not specified
- `AccountInvoiceManager.__init__` — wires collaborators, no logic

---

## `AccountInvoiceManager._get_or_404(session, invoice_id, workspace_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** internal (used by: `get_invoice`, `update_invoice`, `delete_invoice`, `confirm_invoice`, `revert_to_draft`, `void_invoice`, `get_events`, `get_items`)

**Purpose:** load one invoice of the workspace or fail with 404.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| invoice_id | int | invoice primary key |
| workspace_id | int | caller's workspace |

**Returns:** the `AccountInvoice` (any status: draft, confirmed or voided).

**Rules:**
- **R1.** An invoice with that id in the workspace is returned, whatever its `invoice_status` (voided included) and whether or not its account is inactive or soft-deleted.
- **R2.** No invoice with that id → 404.
- **R3.** Workspace isolation: an invoice with that id that belongs to another workspace → the same 404.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found in workspace | `HTTPException` 404 | `Invoice with ID {invoice_id} not found` |

**Side effects:** none

---

## `AccountInvoiceManager._log_event(session, invoice, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** internal (used by every write method here; also `InvoicePaymentManager`, `AttachmentManager`, invoice-item endpoints)

**Purpose:** append one activity event to an invoice's log.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| invoice | AccountInvoice | must already have an `id` (flushed) |
| event_type | str | stored as given (≤ 50 chars by column) |
| description | str | stored as given (not null) |
| performed_by | int \| None | profile id; may be `None` |
| metadata | dict \| None | stored as JSON in `metadata_json`; `None` stored as SQL NULL/JSON null |

**Returns:** `None`.

**Rules:**
- **R1.** One `invoice_events` row is inserted and flushed with `workspace_id` = the invoice's workspace, `invoice_id` = the invoice's id, and `event_type`, `description`, `performed_by`, `metadata_json` = the given values.
- **R2.** `created_at` is set to the current UTC time by the column default.

**Errors:** none raised by the method itself (a non-JSON-serialisable metadata value fails at flush).

**Side effects:** one event row, flushed.

---

## `AccountInvoiceManager._recalculate_payment_status(invoice)`
**Shape:** compute
**Persistence:** pure (mutates the given object, no flush)
**Visibility:** internal (used by: `_recalculate_invoice_amount`)

**Purpose:** derive `payment_status` from paid vs. invoice amount.

**Rules:**
- **R1.** `paid_amount >= invoice_amount` → `payment_status = "paid"` (includes both being 0.00, and overpayment).
- **R2.** Otherwise, `paid_amount > 0` → `"partial"`.
- **R3.** Otherwise → `"unpaid"`. A previous value of `"overdue"` (or anything else) is always replaced by one of these three.

This method is not itself buggy: it only ever derives paid/partial/unpaid, which is correct — "overdue" is a query-time concept, not something this method (or any stored row) should hold. See BUG-635 for where "overdue" is actually derived (`get_invoices_hub_summary`, `list_accounts_hub_page`).

**Returns:** `None` (G12).

**Errors:** none. **Side effects:** sets `invoice.payment_status` in memory only.

---

## `AccountInvoiceManager._recalculate_invoice_amount(session, invoice)`
**Shape:** compute
**Persistence:** reads (mutates the invoice in memory; no explicit flush)
**Visibility:** internal (used by: `confirm_invoice`, `sync_items_from_list`; also invoice-item endpoints)

**Purpose:** set the invoice amount to the sum of its line items and refresh payment status.

**Rules:**
- **R1.** `invoice_amount` becomes the exact decimal sum of `line_subtotal` of all `invoice_items` with this `invoice_id` **and** the invoice's `workspace_id` (items with the same invoice id in another workspace are ignored).
- **R2.** No items → `invoice_amount = 0.00`.
- **R3.** Then `payment_status` is recomputed per `_recalculate_payment_status` R1–R3.

This method is correct as-is (not tagged) — it is the source of truth for the invoice amount; BUG-627 is that `create_invoice` let a client-supplied amount coexist with it and get silently overwritten, not that this method is wrong.

**Returns:** `None` (G12).

**Errors:** none. **Side effects:** `invoice_amount`, `payment_status` set on the object; persisted at the caller's next flush.

---

## `AccountInvoiceManager.create_invoice(session, invoice_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (service `create_invoice`; purchase/expense/sales/work-order services)

**Purpose:** create a draft invoice for an account.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| invoice_data | AccountInvoiceCreate | `account_id` int (required); `invoice_type` must match `payable`\|`receivable`; `invoice_amount` — **[BUG-627] removed from the schema entirely; see R9** *(today: Decimal ≥ 0, required)*; `invoice_date` date (required); `order_type` — **[BUG-624] trimmed + lower-cased, must be one of `purchase_order`/`expense_order`/`sales_order`/`work_order`, else 422; see R9a** *(today: ≤ 30 chars, any text)*; `order_id` — **[BUG-625] must name an existing, live, same-workspace order of `order_type`, else 404; see R9b** *(today: any int, unchecked)*; `invoice_number`/`vendor_invoice_number` ≤ 100 chars; `due_date`, `description`, `notes`, `payment_locked_reason` optional; `allow_payments` default `True` |
| workspace_id | int | |
| user_id | int | creator |

**Returns:** the new `AccountInvoice`, flushed (has `id`), not committed.

**Rules:**
- **R1.** Account not found in the workspace (missing, or belongs to another workspace) → 404, nothing written.
- **R2.** Account soft-deleted → 400 "Cannot create invoice for deleted account" (checked before active/allow flags).
- **R3.** Account live but `is_active = False` → 400.
- **R4.** Account live and active but `allow_invoices = False` → 403.
- **R5.** Otherwise an invoice is created with `invoice_status = "draft"`, `payment_status = "unpaid"`, `paid_amount = 0.00`, `receiving_started = False`, `workspace_id` = given workspace, `created_by = user_id`.
- **R6.** Fields sent as `None` are not passed, so column defaults apply (`due_date`, `description`, `notes`, reference numbers, `order_*`, `payment_locked_reason` → NULL). `allow_payments` is stored as given (default `True`).
- **R7.** `created_at` set by the database; `updated_by`, `updated_at`, `last_synced_at`, `void_note` stay NULL.
- **R8.** One event: `event_type "created"`, description `"Draft invoice created"`, `performed_by = user_id`, metadata `{"invoice_type": <type>, "account_id": <account id>}`.
- **R9.** [BUG-627] `invoice_amount` is not accepted at all — `AccountInvoiceCreate` has no such field. A new draft always starts at `invoice_amount = 0.00`, `payment_status = "unpaid"`, and follows its line items from then on (see `_recalculate_invoice_amount`). *(Today: `AccountInvoiceCreate.invoice_amount` is required, accepted, and stored — then silently discarded the moment the invoice is confirmed, per `confirm_invoice` R4.)*
  A client that still sends `invoice_amount` gets a 422 from `AccountInvoiceCreate` (unknown field rejected — `ValidationError` with `loc = ("invoice_amount",)`), the same as `update_invoice` R2a; it is never silently ignored (G1, best-practice default, delegated by reviewer).
- **R9a.** [BUG-624] `order_type`, when given, is trimmed and lower-cased and must be one of `purchase_order`, `expense_order`, `sales_order`, `work_order`; any other value is rejected by `AccountInvoiceCreate` with 422. *(Today: any text up to 30 characters is accepted and stored as typed — see P1.)*
- **R9b.** [BUG-625] `order_id`, when given, must name an existing, live order of the given `order_type` in the same workspace ("live" per type is defined in R9d below), or the create is rejected with 404, detail `Order with ID {order_id} not found` (G2, best-practice default, delegated by reviewer), nothing written. *(Today: any integer is accepted; a non-existent id or one belonging to another workspace is stored unchecked — see P2.)*
- **R9c.** [BUG-625] `order_type` and `order_id` must be given together or not at all: exactly one of them given (the other absent or `null`) is rejected by `AccountInvoiceCreate` with 422, `loc` naming the missing one (G13, best-practice default, delegated by reviewer). Every internal caller (PO/EO/SO/WO services) already sends both. *(Today: either one alone is accepted and stored.)*
- **R9d.** [BUG-625] "Live" order, per `order_type` (G14, best-practice default, delegated by reviewer): `purchase_order` → `purchase_orders.voided = False` (the table has **no** `is_deleted` column); `expense_order` → `expense_orders.voided = False` (no `is_deleted` column); `work_order` → `work_orders.is_deleted = False` **and** `status != "VOIDED"`; `sales_order` → any existing row (`sales_orders` has neither a void nor a soft-delete column). A voided purchase/expense order, or a soft-deleted or voided work order, is treated exactly like a missing one: 404 `Order with ID {order_id} not found`, nothing written. The same definition applies to `update_invoice` R12/R12a.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| account not in workspace | 404 | `Account with ID {account_id} not found` |
| account deleted | 400 | `Cannot create invoice for deleted account` |
| account inactive | 400 | `Cannot create invoice for inactive account` |
| account `allow_invoices` false | 403 | `Invoices are not allowed for this account` |
| `order_type` not one of the four known values | 422 (schema) | — (BUG-624) |
| `invoice_amount` present in request | 422 (schema) | `loc = ("invoice_amount",)` — BUG-627 |
| `order_id` given but order not found/live/in-workspace | 404 | `Order with ID {order_id} not found` — BUG-625 |
| only one of `order_type` / `order_id` given | 422 (schema) | `loc` names the missing field — BUG-625 |

**Side effects:** one `account_invoices` row + one event row, flushed.

---

## `AccountInvoiceManager.get_invoice(session, invoice_id, workspace_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public

**Rules:**
- **R1.** Returns the invoice; not found / other workspace → 404 — per `_get_or_404` R1–R3.

**Errors / Side effects:** as `_get_or_404`; none.

---

## Shared: invoice list filters
Used by `list_invoices`, `list_invoices_page`, `list_open_invoices_page`, `summarize_invoices`, `get_invoices_hub_summary`. Stated once here under `list_invoices`; the others point to it.

## `AccountInvoiceManager.list_invoices(session, workspace_id, account_id=None, invoice_type=None, payment_status=None, invoice_status=None, invoice_number_search=None, account_name_search=None, invoice_date_from=None, invoice_date_to=None, due_date_from=None, due_date_to=None, amount_min=None, amount_max=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (`GET /invoices`; API passes all filters, `limit` 1–1000, `skip ≥ 0`)

**Purpose:** filtered, paged list of the workspace's invoices.

**Returns:** list of `AccountInvoice`.

**Rules (filter rules R1–R14 apply to every method using the shared filters):**
- **R1.** Only invoices of `workspace_id` are returned (workspace isolation).
- **R2.** Invoices whose account is soft-deleted are never returned (inactive accounts' invoices are returned).
- **R3.** Voided and draft invoices are included unless a status filter excludes them.
- **R4.** `account_id` given (not `None`, `0` included) → only that account's invoices.
- **R5.** `invoice_type`, `payment_status`, `invoice_status`: when truthy, exact, case-sensitive equality on that column; empty string = no filter; an unknown value returns nothing.
- **R5a.** [BUG-635] `payment_status = "overdue"` is a derived filter, not column equality: it returns invoices with `invoice_status = "confirmed"`, `payment_status` in `unpaid`/`partial`, and a `due_date` before today (today as in `get_invoices_hub_summary` R2). The `unpaid` and `partial` filters stay plain column equality, so an overdue invoice still matches its stored `unpaid`/`partial` value (G4, best-practice default, delegated by reviewer). *(Today: exact equality on the column, which never holds `"overdue"`, so the filter returns nothing — Q11.)* Applies to every method using the shared filters that accepts `payment_status`.
- **R6.** `invoice_date_from`/`invoice_date_to`: inclusive bounds on `invoice_date`.
- **R7.** `due_date_from`/`due_date_to`: inclusive bounds on `due_date`; an invoice with no due date is excluded whenever either bound is given.
- **R8.** `amount_min`/`amount_max` (not `None`, `0` included): inclusive bounds on `invoice_amount`.
- **R9.** `invoice_number_search`, when given and not blank after trimming, is matched as a case-insensitive substring, with `%`, `_`, `\` matched literally, against any of: `invoice_number`; `vendor_invoice_number`; the number of a purchase/expense/sales/work order **of the same workspace** that the invoice links to (`order_type` + `order_id`); the number of such an order whose `invoice_id` points to the invoice.
- **R9a.** [BUG-637] A blank or whitespace-only `invoice_number_search` (after trimming) is treated as **no search filter** — every invoice passes this condition. *(Today: it trims to an empty pattern that matches only invoices whose invoice or vendor number is exactly `""`, so the list comes back almost empty — see Q13.)*
- **R10.** [BUG-622, HR-8] When the trimmed `invoice_number_search` consists only of ASCII digits `0-9`, invoices whose `id` equals that number also match; any other digit characters are searched as text only and never raise. *(Today: Unicode `isdigit()` — `"²"` raises `ValueError`, `"١٢"` matches id 12.)*
- **R11.** [BUG-622, HR-8] `account_name_search` (when truthy): case-insensitive substring of the account name, with `%`, `_`, `\` matched literally. *(Today: not escaped — `%` or `_` matches every account; also not trimmed — a leading/trailing-space search is not specifically flagged, that part is unchanged.)*
- **R12.** Filters combine with AND; all filtering happens before paging.
- **R13.** Order: `invoice_date` descending, then `id` descending.
- **R14.** `skip`/`limit` applied after filtering and ordering (defaults 0 / 100).

**Errors:** none of its own.
**Side effects:** none.

---

## `AccountInvoiceManager.list_open_invoices_page(session, *, workspace_id, account_id, prioritize_purchase_order_id=None, skip=0, limit=10)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (`GET /accounts/{id}/open-invoices`, `limit` 1–100)

**Purpose:** paged open-balance invoices of one account, optionally with a given PO's invoice first.

**Returns:** `(items, total)` — `total` = count of all matching invoices before paging.

**Rules:**
- **R1.** Shared filters R1–R2, R4 with the given `account_id` (another workspace's account → empty, total 0).
- **R2.** [BUG-634] Only "open" invoices: `invoice_status = "confirmed"` **and** `payment_status` in `unpaid`/`partial`. Drafts and voided invoices are excluded. *(Today: any non-voided invoice — including drafts — with `payment_status` in `unpaid`/`partial`/`overdue` counts; see Q9. In practice `payment_status` is never literally `"overdue"` — BUG-635 — so today's real difference from intended is just the draft inclusion.)*
- **R3.** `prioritize_purchase_order_id` given (not `None`): invoices with `order_type = "purchase_order"` and `order_id` = that value come first; within each group order is `invoice_date` desc, `id` desc. Not given → `invoice_date` desc, `id` desc.
- **R4.** `skip`/`limit` applied after ordering (defaults 0 / 10); `total` ignores them.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceManager.list_invoices_page(session, *, workspace_id, account_id=None, …filters…, open_balance_only=False, prioritize_purchase_order_id=None, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (service `list_account_invoices_page`: always passes `account_id`; never passes `account_name_search`, `amount_min`, `amount_max`, `open_balance_only`, `prioritize_purchase_order_id`; API `limit` 1–1000, default 50)

**Returns:** `(items, total)`, `total` = count before paging.

**Rules:**
- **R1.** Filtering per shared filters R1–R12.
- **R2.** `open_balance_only=True` adds the open-balance condition of `list_open_invoices_page` R2 (confirmed-only, per BUG-634).
- **R3.** Ordering and prioritisation per `list_open_invoices_page` R3; `skip`/`limit` after ordering (defaults 0 / 100); `total` ignores paging.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceManager.get_invoices_hub_summary(session, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (`GET /invoices/hub-summary`)

**Purpose:** workspace-level open-balance KPIs.

**Returns:** tuple `(payable, receivable, accounts_with_any_open_balance, total_active_accounts)`; `payable` / `receivable` are tuples `(open_count: int, outstanding_total: Decimal, overdue_count: int, accounts_with_open_count: int)`.

**Rules:**
- **R1.** Only the workspace's invoices whose account is not soft-deleted count (inactive accounts count).
- **R2.** [BUG-634, BUG-635] Per type (`payable`, `receivable`), over invoices that are `invoice_status = "confirmed"` with `payment_status` in `unpaid`/`partial`: `open_count` = number of such invoices; `outstanding_total` = sum of `invoice_amount − paid_amount` (0 when none); `overdue_count` = those additionally having a `due_date` that is before today's date (UTC) — "today" is the application clock `utcnow().date()` read in the manager (patchable via `app.managers.account_invoice_manager.utcnow`), not the database's `CURRENT_DATE`; a `due_date` equal to today is **not** overdue, the day before is; an invoice with no `due_date` is never overdue (G3, best-practice default, delegated by reviewer); `accounts_with_open_count` = distinct accounts among them. *(Today: drafts are included in the open set — BUG-634/Q9 — and `overdue_count` counts `payment_status = "overdue"`, which is never stored, so it is always 0 — BUG-635/Q11.)*
- **R3.** `accounts_with_any_open_balance` = distinct accounts with at least one such (now confirmed-only) invoice of either type, per R2.
- **R4.** `total_active_accounts` = accounts of the workspace with `is_active = True` and `is_deleted = False`, whether or not they have invoices.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceManager.list_accounts_hub_page(session, *, workspace_id, section="overview", search=None, skip=0, limit=50)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (`GET /accounts/hub`, `limit` 1–500)

**Purpose:** paged accounts of the hub with per-type open-balance rollups.

**Returns:** `(rows, total)`; each row is `(account, payable_agg, receivable_agg)`, each agg having `outstanding_total`, `open_count`, `has_overdue`.

**Rules:**
- **R1.** [BUG-636] Accounts of the workspace that are **not soft-deleted**, and either `is_active = True` **or** have at least one open-balance invoice (payable or receivable, per R2). *(Today: only active, not-soft-deleted accounts are included, so an inactive account with an open balance is invisible here although it counts in the hub KPIs — see Q12.)*
- **R2.** [BUG-634] Per account and type, the agg covers that account's **confirmed**, non-voided invoices with `payment_status` in `unpaid`/`partial`: `outstanding_total` = sum of `invoice_amount − paid_amount`, `open_count` = count; an account with none → `0`, `0`, `False`. *(Today: drafts are included — see Q9; the filter also lists `payment_status = "overdue"`, which is never stored — BUG-635.)*
- **R3.** [BUG-635] `has_overdue` is `True` when any of the account's invoices counted in R2 additionally has a `due_date` before today's date (UTC) — same "today" source and boundary as `get_invoices_hub_summary` R2. *(Today: checks `payment_status = "overdue"`, which is never stored, so `has_overdue` is always `False` — see Q11.)*
- **R4.** [BUG-622, HR-8] `search` (when truthy): case-insensitive substring of the account name, `%`, `_`, `\` matched literally. *(Today: unescaped.)*
- **R5.** `section = "payable"` → only accounts whose payable `outstanding_total > 0`; `"receivable"` → receivable `> 0`; any other value (incl. `"overview"`) → no balance filter.
- **R6.** [BUG-623, HR-6] Order: account name case-insensitive ascending, then `id` ascending. Account names are not unique in a workspace, so equal (or case-insensitively equal) names are a real case and are ordered by `id`. *(Today: case-sensitive name order.)*
- **R7.** `total` = count after filters, before paging; `skip`/`limit` after ordering.

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceManager.summarize_invoices(session, workspace_id, …filters…)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (`GET /accounts/{id}/invoice-summary`; that endpoint never passes `account_name_search`)

**Returns:** `(invoice_count: int, invoiced_total: Decimal, paid_total: Decimal, outstanding_total: Decimal)`.

**Rules:**
- **R1.** Matching set per shared filters R1–R12 (no paging). `invoice_count` = all matching invoices, voided included — unaffected by BUG-634.
- **R2.** [BUG-634] Money totals over matching invoices that are `invoice_status = "confirmed"` and not voided: sum of `invoice_amount`, sum of `paid_amount`, sum of `invoice_amount − paid_amount`; each `0` when nothing matches. *(Today: drafts are included in the money totals — see Q10.)*

**Errors:** none. **Side effects:** none.

---

## `AccountInvoiceManager.update_invoice(session, invoice_id, invoice_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (`PUT /invoices/{id}`; PO and EO services send header changes for linked drafts)

**Purpose:** edit an invoice — fully while draft, only admin fields + due date once confirmed.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| invoice_data | AccountInvoiceUpdate | all optional; explicit `null` allowed for every field **except** — **[BUG-630] `account_id`, `invoice_type`, `invoice_date`, `allow_payments` (422 if `null`); see R2a** *(today: `null` reaches the database and fails with a not-null integrity error)*; `invoice_type` pattern `payable`\|`receivable`; `invoice_amount` — **[BUG-630] removed from the schema entirely, any value in the request → 422; see R2a, R11** *(today: ≥ 0, present but silently unused)*; reference numbers ≤ 100 chars; `order_id` int, nullable; `order_type` — **[BUG-625] new nullable field added to the schema by the fix, same normalisation and allowed values as `create_invoice` R9a; see R2b, R12a** *(today: `AccountInvoiceUpdate` has no `order_type` field — a sent `order_type` is silently ignored and never appears among the sent fields)*. Only fields the client actually sent are considered. |

**Returns:** the invoice (updated and flushed, or unchanged).

**Rules:**
- **R1.** [BUG-621, HR-10] Invoice not found / other workspace → 404 per `_get_or_404`; the row is read with a row lock (`SELECT … FOR UPDATE`). *(Today: no lock — a draft-only edit can be applied concurrently with a confirm of the same invoice.)*
- **R2.** Voided invoice → 400 "Voided invoices cannot be edited", nothing written.
- **R2a.** [BUG-630] Schema-level (`AccountInvoiceUpdate`), applies to both paths below: an explicit `null` for `account_id`, `invoice_type`, `invoice_date` or `allow_payments` is rejected with 422 naming the field (a Pydantic `ValidationError` whose error `loc` is `(<field>,)`; message text not fixed — G2, best-practice default, delegated by reviewer); other fields (`due_date`, `description`, `notes`, `invoice_number`, `vendor_invoice_number`, `payment_locked_reason`, `order_id`, and — once it exists, R2b — `order_type`) can still be cleared with `null`. Any `invoice_amount` in the request (the schema no longer has the field) is rejected with 422 ("amount is derived from line items"). *(Today: `null` for a non-nullable column reaches the database and fails with a not-null integrity error, answered as a generic 400 "Resource Conflict" instead of a field-naming validation error — Q4; `invoice_amount` sent is silently dropped on a draft, R11, and simply not in the editable set on a confirmed invoice, R3, so the request succeeds (200) as if it worked — Q5.)*
- **R2b.** [BUG-625] Schema-level (`AccountInvoiceUpdate`): `order_type` can be sent on update. It is optional and nullable (`null` clears it, subject to the pairing rule in R12a); a non-null value is trimmed and lower-cased and must be one of `purchase_order`, `expense_order`, `sales_order`, `work_order`, otherwise 422 (`ValidationError` with `loc = ("order_type",)`) — the same normalisation as `create_invoice` R9a. A sent `order_type` (a value or explicit `null`) counts as a sent field (it is in `model_fields_set`). On a draft it is applied and validated per R12/R12a and appears in the R14 event metadata when it changes; on a confirmed invoice it is a non-editable field like any other (R4/R4a) (G15, best-practice default, delegated by reviewer). *(Today: the schema has no `order_type` field; a sent `order_type` is silently dropped by Pydantic, is not in `model_fields_set`, and the stored `order_type` can never be changed or cleared through update.)*
- *Confirmed invoice:*
- **R3.** Only `allow_payments`, `payment_locked_reason`, `due_date` are applied, when sent (explicit `null` included, subject to R2a).
- **R3b.** (owner, 2026-11-14, O1 (e)) The completed-order freeze (F1–F4) does **not** apply here. On a confirmed invoice that belongs to a completed order, edits to `due_date`, `allow_payments` and `payment_locked_reason` are applied exactly as for any confirmed invoice (R3, R5–R9), because they don't change the invoice's money. There is no F5 refusal. This is today's behavior, unchanged. It is stated so the freeze fix doesn't spread to update.
- **R4.** [BUG-631] Any sent field **outside** those three whose value differs from what is currently stored causes the whole update to be rejected with 400, naming the offending field(s) — detail `Cannot edit confirmed invoice fields: <field names, comma-separated, sorted>. Revert to draft to edit them.`; tests assert the status and that every offending field name appears in the detail (G2, best-practice default, delegated by reviewer); nothing is saved. Checked before anything is applied. *(Today: such fields are silently dropped — sent but ignored, no error, no comparison — see Q6.)*
- **R4a.** A sent field outside the editable three whose value **matches** what is already stored is a no-op: ignored, no rejection (this part of today's "drop extraneous fields" behavior is correct and unchanged).
- **R5.** None of the three editable fields is sent, and no other field triggers R4 → invoice returned unchanged: no `updated_by`, no event.
- **R6.** [BUG-620, HR-9] `updated_by = user_id` only when at least one of the three actually changes value. *(Today: set whenever one of them is sent, even if unchanged.)*
- **R7.** [BUG-632] `due_date` sent **and its value changes** → event `due_date_changed`, "Due date updated", metadata `{"old_due_date": <ISO date or null>, "new_due_date": <ISO date or null>}`; sent but unchanged → no event. *(Today: event logged whenever `due_date` is sent, even unchanged — see Q7.)*
- **R8.** [BUG-632] `allow_payments` sent **and its value changes** → event `allow_payments_changed`, description "Payments enabled" when the new value is truthy else "Payments disabled", metadata `{"allow_payments": <value>}`; sent but unchanged → no event. *(Today: event logged whenever sent, even unchanged.)*
- **R9.** [BUG-632] `payment_locked_reason` sent **and its value changes** → event `payment_lock_changed`, "Payment lock updated", metadata `{"payment_locked_reason": <value>}`; sent but unchanged → no event. *(Today: event logged whenever sent, even unchanged.)*
- *Draft (any status other than voided/confirmed):*
- **R10.** [BUG-629] `account_id` sent, truthy and different from the current account: account not in workspace → 404 `Account with ID {account_id} not found`; account soft-deleted → 400 `Cannot assign invoice to deleted account`; account `is_active = False` → 400 `Cannot assign invoice to inactive account`; account `allow_invoices = False` → 403 `Invoices are not allowed for this account` — the same four checks as `create_invoice` R1–R4. Same account or absent → no check (`null` never gets here, R2a). *(Today: only existence and soft-delete are checked; an inactive account or one with `allow_invoices = False` is accepted — see Q3.)*
- **R10a.** [BUG-629] `account_id = 0` is treated like any other id, not as "no change": no account 0 exists, so it is rejected with 404 `Account with ID 0 not found`, nothing written (G6, best-practice default, delegated by reviewer). *(Today: `0` is falsy, so the account check is skipped and the value is stored, which violates the `account_id` foreign key at flush and surfaces as a generic integrity error / 400 "Resource Conflict"; nothing is saved.)*
- **R11.** Sent fields are applied, except `invoice_amount` — rejected at the schema level (R2a, BUG-630), never reaches here. Status, paid amount, void note and receiving flag cannot be set (not in the schema).
- **R12.** Sent values are stored as sent, including `null` (clears nullable fields per R2a) and any `order_id` — when `order_id` is sent and changes, it is validated the same way as `create_invoice` R9b: must name an existing, live order (live per `create_invoice` R9d) of the invoice's effective `order_type` (R12a) in the workspace, else 404 `Order with ID {order_id} not found`, nothing written (BUG-625, P2). `null`/absence of `order_type`/`order_id` skips this check.
- **R12a.** [BUG-625] The check in R12 uses the **effective** pair after the update: `order_type` = the value sent in this request if sent, else the stored one; `order_id` likewise. It runs whenever either field is sent and the effective pair differs from the stored pair (so changing only `order_type` re-validates the stored `order_id` against the new type). The effective pair must be both set or both `null`; exactly one set → 400 `order_type and order_id must be set together`, nothing written (G5, G13, best-practice default, delegated by reviewer). *(Today: neither field is checked; any combination is stored.)*
- **R13.** [BUG-620, HR-9] `updated_by = user_id` only when at least one field changes value. *(Today: always, even for `{}`.)*
- **R14.** [BUG-632] Event `item_manually_updated`, "Invoice details updated", `performed_by = user_id`, metadata = every field that actually **changed** → `str(value)` (`null` → `"None"`), `updated_by` excluded; when **no** field changes, no event is logged. *(Today: logged on every successful draft update, even `{}`, producing metadata `{}` — see Q7.)*
- **R15.** `updated_at` is refreshed by the database whenever a column value changes.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found | 404 | `Invoice with ID {id} not found` |
| voided | 400 | `Voided invoices cannot be edited` |
| `null` for `account_id`/`invoice_type`/`invoice_date`/`allow_payments` | 422 (schema) | field-specific — BUG-630 |
| `invoice_amount` present in request | 422 (schema) | "amount is derived from line items" — BUG-630 |
| confirmed: changed field outside the editable three | 400 | `Cannot edit confirmed invoice fields: <fields>. Revert to draft to edit them.` — BUG-631 |
| draft: new account not in workspace | 404 | `Account with ID {account_id} not found` |
| draft: new account deleted | 400 | `Cannot assign invoice to deleted account` |
| draft: new account inactive | 400 | `Cannot assign invoice to inactive account` — BUG-629 |
| draft: new account `allow_invoices` false | 403 | `Invoices are not allowed for this account` — BUG-629 |
| draft: `account_id = 0` | 404 | `Account with ID 0 not found` — BUG-629 |
| `order_type` sent but not one of the four known values | 422 (schema) | `loc = ("order_type",)` — BUG-625 (field added by the fix, R2b) |
| draft: `order_id` not a live, in-workspace order of `order_type` | 404 | `Order with ID {order_id} not found` — BUG-625 |
| draft: effective `order_type`/`order_id` pair half-set | 400 | `order_type and order_id must be set together` — BUG-625 |

**Side effects:** invoice columns updated + flushed; 0–3 event rows (confirmed) or 0–1 (draft).

---

## Shared: Completed-order freeze (owner decision O1, 2026-11-14)
Used by `delete_invoice` R2a, `revert_to_draft` R2a/R2b, `void_invoice` R3a/R3b. Stated once here. None of it exists in the code today: every rule that uses it carries a bug tag.

- **F1. The order's invoice** (best-practice default, delegated by reviewer). An invoice belongs to an order when a row in `purchase_orders`, `sales_orders`, `expense_orders` or `work_orders` of the **same workspace** has `invoice_id` = this invoice's id. This is the order's own invoice slot. The invoice's `order_type` / `order_id` alone do **not** make it the order's invoice, so a return credit note (F6) or a manually linked invoice whose order points elsewhere is never frozen by F2. A row of another workspace pointing at the invoice is invalid data and is ignored (links across workspaces are never valid).
- **F2. Frozen** = the invoice belongs (F1) to at least one order that is **completed**. Completion per kind, the same marks as `orders_overview_service` spec D4–D7 (but completion only, not "committed"):
  - **Purchase order:** stage `Complete`, i.e. the `statuses.name` of `current_status_id` is exactly `"Complete"`. `Receiving` is not completed.
  - **Sales order:** `order_completed = True`.
  - **Expense order:** `completed_at IS NOT NULL`. Expense orders have no status column.
  - **Work order:** `status = "COMPLETED"`. `IN_PROGRESS`, `DRAFT` and `VOIDED` are not completed.
- **F3.** Only completion is read. The order's `voided` / `is_deleted` flags, its approvals and its payments do not change the answer. The state is read at call time.
- **F4.** Any invoice status can be frozen: a draft that belongs to a completed order is frozen too (it can't be deleted).
- **F5. A refusal** is `HTTPException` 400 with detail `Invoice is locked — the linked <kind> is completed. Correct it with a credit note or return.`, where `<kind>` is `purchase order`, `sales order`, `expense order` or `work order` (that of the completed order; if several are completed, the first in that order). Nothing is written: the invoice row is unchanged (status, amounts, `void_note`, `updated_by`), no payment is touched, no row is deleted, and no event is logged.
- **F6. Return credit note** = an invoice whose id is the `invoice_id` of a `purchase_order_returns` or `sales_order_returns` row of the same workspace. A credit note is never editable after creation (BUG-2733): revert is refused (`revert_to_draft` R2a). Void stays allowed whatever the order's state (`void_invoice` R3b): voiding it and starting a new return is the way to correct one. Delete is already impossible, because a credit note is confirmed at creation (`delete_invoice` R2).
- **F7. Out of scope of this manager.** Payments on a frozen invoice may still be recorded or voided (owner): that is `InvoicePaymentManager`, unaffected. `update_invoice`, `confirm_invoice`, `set_receiving_started` and `sync_items_from_list` are not changed by O1 (`update_invoice` R3b states this explicitly, owner 2026-11-14).

---

## `AccountInvoiceManager.delete_invoice(session, invoice_id, workspace_id, user_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (`DELETE /invoices/{id}`; PO/EO/SO/WO services)

**Returns:** the deleted invoice object (detached from the database row).

**Rules:**
- **R1.** [BUG-621, HR-10] Not found / other workspace → 404 per `_get_or_404`; row read with a row lock (`FOR UPDATE`). *(Today: no lock — a concurrent confirm can pass while the draft is being deleted.)*
- **R2.** `invoice_status` other than `draft` → 400 "Only draft invoices can be deleted. This invoice is '<status>'. Use void instead.", nothing deleted.
- **R2a.** [BUG-2730] A draft that is frozen (F1–F4) is refused per F5, and nothing is deleted. This check runs after R2 and before R4. *(Today: not checked. The draft of a completed order is deleted like any other draft, per R3.)*
- **R3.** Draft that is not frozen, with no `invoice_payments` rows and no legacy status-history rows → the invoice row is hard-deleted (flushed); its items and events are removed by the database cascade; rows pointing to it in `purchase_orders`, `expense_orders`, `sales_orders`, `work_orders`, `purchase_order_returns`, `sales_order_returns`, `machine_item_ledger` and `project_component_item_ledger` stay and get `invoice_id = NULL` (all `ON DELETE SET NULL`). `user_id` is not recorded anywhere.
- **R4.** [BUG-639] A draft that has `invoice_payments` rows (e.g. voided ones kept after revert-to-draft) or legacy status-history rows (`invoice_status_tracker` rows with this `invoice_id` — see Notes for the test designer, G7) is refused up front with 400 "Invoice has payment history — confirm and void it instead", nothing deleted. *(Today: no such check — the flush is attempted, fails with a not-null integrity error, is reported as a generic 400 conflict, and nothing is deleted anyway — see Q17. The practical no-delete outcome is the same; the bug is the confusing, unexplained error.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found | 404 | `Invoice with ID {id} not found` |
| not draft | 400 | `Only draft invoices can be deleted. This invoice is '{status}'. Use void instead.` |
| draft belongs to a completed order | 400 | `Invoice is locked — the linked <kind> is completed. Correct it with a credit note or return.` — BUG-2730 |
| draft has payment/status-history rows | 400 | `Invoice has payment history — confirm and void it instead` — BUG-639 |

**Side effects:** row deletion as above; no event.

---

## `AccountInvoiceManager.confirm_invoice(session, invoice_id, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (`POST /invoices/{id}/confirm`; PO/EO/SO/WO services)

**Purpose:** finalize a draft: freeze its amount from its items.

**Rules:**
- **R1.** [BUG-621, HR-10] Not found / other workspace → 404. The invoice row is read with a row lock. *(Today: no lock.)*
- **R2.** Voided → 400 "Voided invoices cannot be confirmed".
- **R3.** Already confirmed → 400 "Invoice is already confirmed".
- **R4.** [BUG-628] Confirm requires at least one line item: a draft with zero items is rejected with 400 "Add at least one line item before confirming", nothing changed. *(Today: confirms successfully — `_recalculate_invoice_amount` R2 yields 0.00 and, since paid (0) ≥ amount (0), `payment_status` becomes `"paid"` — see Q2.)* Otherwise `invoice_amount` = sum of its items and `payment_status` recomputed per `_recalculate_invoice_amount` R1, R3 (any previously stored amount is replaced — the amount was never client-settable to begin with once BUG-627 is fixed).
- **R5.** [BUG-633] `invoice_status = "confirmed"`, `last_synced_at` = current UTC time (`utcnow`); `updated_by = user_id`; flushed. *(Today: `updated_by` not changed — see Q8.)*
- **R6.** Event `confirmed`, "Invoice finalized", `performed_by = user_id`, metadata `{"invoice_amount": "<amount as string, 2 decimals>"}`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found | 404 | `Invoice with ID {id} not found` |
| voided | 400 | `Voided invoices cannot be confirmed` |
| confirmed | 400 | `Invoice is already confirmed` |
| no line items | 400 | `Add at least one line item before confirming` — BUG-628 |

**Side effects:** invoice updated + flushed; one event.

---

## `AccountInvoiceManager.revert_to_draft(session, invoice_id, workspace_id, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (`POST /invoices/{id}/revert-to-draft`)

**Rules:**
- **R1.** [BUG-621, HR-10] Not found → 404. Row read with a row lock. *(Today: no lock.)*
- **R2.** Status not `confirmed` (draft or voided) → 400 "Only confirmed invoices can be reverted to draft. Current status: '<status>'."
- **R2a.** [BUG-2733] A confirmed return credit note (F6) → 400 `Return credit notes cannot be reverted to draft. Void it and create a new return instead.`, nothing written. This runs after R2 and before R2b, R3 and R4, whatever the order's state, receiving flag or payments. *(Today: not checked. A credit note has `receiving_started = False` and usually nothing paid, so the revert succeeds and its items become editable.)*
- **R2b.** [BUG-2730] A frozen invoice (F1–F4) is refused per F5, nothing written. This runs after R2a and before R3 and R4, so a completed PO's invoice with `receiving_started = True` or with payments gets the freeze detail. *(Today: not checked. A completed sales, expense or work order's confirmed invoice with nothing paid reverts to draft. A completed PO's invoice is refused only through R3, because its flag is set.)*
- **R3.** `receiving_started` true → 400, nothing written, checked before payments. This works today.
- **R3a.** [BUG-2736] The R3 detail is `Cannot revert to draft — goods have been received on the linked order. Record a return instead.`. It gives no advice that can't be followed, because the flag is never cleared (best-practice default text, delegated by reviewer). *(Today: `Cannot revert to draft — receiving has been recorded on the linked order. Zero out received quantities first.`)*
- **R4.** `paid_amount` > 0 → 400 (payments message). `paid_amount` of 0 or NULL passes (voided payments do not count).
- **R5.** [BUG-633] Otherwise `invoice_status = "draft"`, flushed; amount, payment status, `last_synced_at` unchanged; `updated_by = user_id`. *(Today: `updated_by` unchanged — see Q8.)*
- **R6.** Event `reverted_to_draft`, "Reverted to draft", `performed_by = user_id`, metadata NULL.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found | 404 | `Invoice with ID {id} not found` |
| not confirmed | 400 | `Only confirmed invoices can be reverted to draft. Current status: '{status}'.` |
| return credit note | 400 | `Return credit notes cannot be reverted to draft. Void it and create a new return instead.` — BUG-2733 |
| belongs to a completed order | 400 | `Invoice is locked — the linked <kind> is completed. Correct it with a credit note or return.` — BUG-2730 |
| receiving started | 400 | [BUG-2736] `Cannot revert to draft — goods have been received on the linked order. Record a return instead.` *(today: `Cannot revert to draft — receiving has been recorded on the linked order. Zero out received quantities first.`)* |
| paid > 0 | 400 | `Cannot revert to draft — invoice has active payments. Void all payments first.` |

**Side effects:** status flushed; one event.

---

## `AccountInvoiceManager.void_invoice(session, invoice_id, workspace_id, user_id, void_note)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (`POST /invoices/{id}/void`; PO/SO return flows)

**Rules:**
- **R1.** [BUG-621, HR-10] Not found → 404. Row read with a row lock. *(Today: no lock.)*
- **R2.** Already voided → 400 "Invoice is already voided".
- **R3.** Draft → 400 "Draft invoices cannot be voided — delete them instead".
- **R3a.** [BUG-2731] A confirmed invoice that is frozen (F1–F4) is refused per F5. Nothing is written: no payment is voided and the invoice keeps its status, `paid_amount`, `payment_status` and `void_note`. This runs after R2 and R3 and before R4. *(Today: not checked. A completed sales, expense or work order's invoice is voided and all its active payments are cancelled. For a PO, only the service's received-quantity guard stops it, and only on the `/void` endpoint.)*
- **R3b.** A return credit note (F6) is never frozen by R3a: the order's completion does not matter for it. Whether its void goes ahead depends only on its return, per R3c.
- **R3c.** [BUG-2788] (owner, OQ-47, 2026-11-17) For a return credit note (F6), the return row (`purchase_order_returns` / `sales_order_returns` of this workspace with `invoice_id` = this invoice) is read with a row lock after R2 and R3: return `completed` → 400 `This return is completed — its goods have already moved. Start a new return or issue a separate credit note.`, nothing written (invoice, payments, return unchanged, no event); return `pending` → the void goes ahead per R4–R7 **and** the return gets `status = 'voided'` and `paid = False` (via the return manager's `sync_return_paid`), flushed; return already `voided` → the void goes ahead per R4–R7, return unchanged. *(Today: the return is never read; the void always goes ahead and the return keeps its status.)* `PurchaseOrderService.void_return` / `SalesService.void_return` keep working: they void through this method on a pending return.
- **R4.** Otherwise every payment of this invoice with `is_voided = False` gets `is_voided = True`, `voided_at` = current UTC time, `voided_by = user_id`, `void_note = "Automatically voided — invoice #<id> was voided. Reason: <void_note>"`. Already-voided payments are untouched.
- **R5.** Invoice: `invoice_status = "voided"`, `void_note` = the given note, `paid_amount = 0.00`, `payment_status = "unpaid"`; `invoice_amount` unchanged; flushed.
- **R6.** [BUG-633] `updated_by = user_id`. *(Today: not changed — see Q8.)*
- **R7.** Event `voided`, "Invoice voided", `performed_by = user_id`, metadata `{"prior_status": "confirmed", "payments_voided": <count of payments voided now>, "void_note": <note>}`.
- **R8.** [BUG-626] `void_note` is stored as given; the request schema (`VoidInvoiceRequest`) trims it and rejects a blank/whitespace-only value with 422 before the manager runs, so the manager only ever receives a non-blank, trimmed note. *(Today: `VoidInvoiceRequest` only requires length ≥ 1, so `"   "` passes and the manager stores it verbatim — see P3.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found | 404 | `Invoice with ID {id} not found` |
| voided | 400 | `Invoice is already voided` |
| draft | 400 | `Draft invoices cannot be voided — delete them instead` |
| belongs to a completed order | 400 | `Invoice is locked — the linked <kind> is completed. Correct it with a credit note or return.` — BUG-2731 |
| credit note of a completed return | 400 | `This return is completed — its goods have already moved. Start a new return or issue a separate credit note.` — BUG-2788 |
| `void_note` blank/whitespace-only | 422 (schema) | — BUG-626 |

**Side effects:** payments + invoice updated, flushed; one event.

---

## `AccountInvoiceManager.set_receiving_started(session, invoice_id, workspace_id, performed_by, reason="")`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (only caller: `PurchaseOrderManager`, for confirmed invoices after the first receipt)

**Rules:**
- **R1.** [BUG-621, HR-10] Invoice not found / other workspace → returns `None`, no error, nothing written. Row read with a row lock. *(Today: no lock.)*
- **R2.** `receiving_started` already true → returns the invoice unchanged, no event.
- **R3.** [BUG-633] Otherwise `receiving_started = True` (any status — the method itself does not check draft/voided), flushed; `updated_by = performed_by` when `performed_by` is given, else unchanged. *(Today: `updated_by` unchanged — see Q8.)*
- **R4.** Event `receiving_started_set`, description = `reason` when non-empty else "Receiving started on linked order", `performed_by` as given (may be `None`), metadata NULL.

**Errors:** none. **Side effects:** flag flushed; one event.

---

## `AccountInvoiceManager.sync_items_from_list(session, invoice, items, user_id, is_manual=False)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (PO/EO/SO/WO services, service `resync_items`)

**Purpose:** replace a draft's line items with the given list and recompute its amount.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| invoice | AccountInvoice | already loaded |
| items | list[dict] | keys = `InvoiceItem` columns (`description`, `quantity`, `unit_price`, `line_subtotal` required by the table) |
| user_id | int \| None | |
| is_manual | bool | **dead code — no caller anywhere passes `True`; the `item_manually_updated` branch is not specified, see the note after R7 and the dead-code checklist** |

**Returns:** `None`.

**Rules:**
- **R1.** Invoice status not `draft` → returns immediately: nothing deleted, created or logged, no error.
- **R2.** Draft: every existing item of the invoice (by `invoice_id`, any workspace) is deleted.
- **R3.** One item row per dict, in list order; `workspace_id`, `invoice_id`, `created_by` default to the invoice's workspace, the invoice id and `user_id` only when the dict lacks them; `last_synced_at` is always set to the current UTC time. The caller's dicts are modified in place with these keys.
- **R4.** Empty list → all items removed, amount 0.00.
- **R5.** Invoice `last_synced_at` = the same timestamp; amount and payment status recomputed per `_recalculate_invoice_amount` R1–R3; flushed.
- **R6.** Event `items_synced`, description "Items synced from order (<N> lines)", `performed_by = user_id`, metadata `{"item_count": N, "items": [...]}`.
- **R7.** Each metadata item: `description` = the dict's description, or when empty/missing `"Line <line_number>"` (`line_number` key if present, else 1-based position); `quantity`, `unit_price`, `line_subtotal` as `str(value)` (e.g. `Decimal("2.50")` → `"2.50"`); `unit` as given (`null` when missing). Each metadata item has exactly these five keys and no others (other dict keys such as `item_id`, `line_number`, `source_order_item_id` are not copied) (G12).
- **R7a.** The `null` fallback for `quantity` / `unit_price` / `line_subtotal` is unreachable: those columns are `NOT NULL` with no default, and each item row is flushed as it is created (R3), so a dict missing one of them (or with `None`) fails at flush before any metadata is built — nothing is logged and the error propagates (see Errors). Not to be tested as a metadata outcome (G9). `description` is likewise `NOT NULL`, so the `"Line <n>"` fallback is reachable only with an empty string `""` description, not a missing one.

**Not specified:** the `is_manual=True` branch (event `item_manually_updated`, description "Items updated") — dead code, to be removed (reviewer, Q14). No caller in `app/` or `tests/` ever passes `is_manual=True`; every real sync logs `items_synced`. Logged in `account_invoice_manager.deadcode-staging.md`. Not a bug, no BUG ID.

**Errors:** none of its own; a dict missing a required column (`description`, `quantity`, `unit_price`, `line_subtotal`) or carrying `None` for one fails with a SQLAlchemy `IntegrityError` (not-null violation) at that item's flush; existing items have already been deleted in the session and no event is written (the caller's transaction must roll back).

**Side effects:** items replaced, invoice updated, one event; all flushed.

---

## `AccountInvoiceManager.get_events(session, invoice_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (`GET /invoices/{id}/events`)

**Rules:**
- **R1.** Invoice not found / other workspace → 404 per `_get_or_404`.
- **R2.** [BUG-638] Returns all events of the invoice in that workspace, newest `created_at` first, ties broken by `id` descending (newest insert first); no paging. *(Today: equal timestamps have no tie-breaker, so their order can differ between calls — see Q15.)* Each entry is a dict: `id`, `workspace_id`, `invoice_id`, `event_type`, `description`, `metadata_json`, `performed_by`, `performed_by_name` (profile name, `None` when no performer or the profile is gone), `created_at`.

**Side effects:** none.

---

## `AccountInvoiceManager.get_items(session, invoice_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (`GET /invoices/{id}/items`)

**Rules:**
- **R1.** Invoice not found / other workspace → 404.
- **R2.** [BUG-638] Returns all `InvoiceItem` rows of the invoice in that workspace, ordered by `line_number` ascending, ties broken by `id` ascending; no paging. *(Today: equal line numbers have no tie-breaker, so their order can change between calls — see Q16.)*

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| mgr:39 | invoice found in workspace? | `_get_or_404` R1–R3 |
| mgr:66 | paid ≥ amount | `_recalculate_payment_status` R1 |
| mgr:68 | paid > 0 | `_recalculate_payment_status` R2 |
| mgr:70 | else | `_recalculate_payment_status` R3 |
| mgr:76 | items empty vs non-empty | `_recalculate_invoice_amount` R1, R2 |
| mgr:94 | account not found | `create_invoice` R1 |
| mgr:97 | account deleted | `create_invoice` R2 |
| mgr:100 | account inactive | `create_invoice` R3 |
| mgr:103 | allow_invoices false | `create_invoice` R4 |
| mgr:107 | `exclude_none` drops None fields | `create_invoice` R6 |
| mgr:305 | voided | `update_invoice` R2 |
| mgr:309 | confirmed vs draft path | `update_invoice` R3 / R10 |
| mgr:313–314 | field in allowed set | `update_invoice` R3 |
| mgr:316 | nothing allowed sent | `update_invoice` R5 |
| mgr:323 | due_date sent | `update_invoice` R7 |
| mgr:324–325 | old/new due date None | `update_invoice` R7 |
| mgr:334 | other allowed fields remain | `update_invoice` R8, R9 |
| mgr:335 | allow_payments sent | `update_invoice` R8 |
| mgr:339 | enabled truthy | `update_invoice` R8 |
| mgr:343 | payment_locked_reason sent | `update_invoice` R9 |
| mgr:354 | account_id truthy and different (`0` falsy) | `update_invoice` R10, R10a |
| mgr:358 | new account not found | `update_invoice` R10 |
| mgr:361 | new account deleted | `update_invoice` R10 |
| mgr:366–367 | protected fields popped | `update_invoice` R11 |
| mgr:376 | metadata excludes updated_by | `update_invoice` R14 |
| mgr:389 | not draft | `delete_invoice` R2 |
| mgr:396 | delete (payments present → error) | `delete_invoice` R3, R4 |
| mgr:412 | voided | `confirm_invoice` R2 |
| mgr:415 | confirmed | `confirm_invoice` R3 |
| mgr:443 | not confirmed | `revert_to_draft` R2 |
| mgr:448 | receiving_started | `revert_to_draft` R3 |
| (fix) | credit note? (F6) — not in code yet | `revert_to_draft` R2a, `void_invoice` R3b |
| (fix) | linked order completed? (F1–F4) — not in code yet | `delete_invoice` R2a, `revert_to_draft` R2b, `void_invoice` R3a |
| mgr:454 | paid > 0 (`or 0`) | `revert_to_draft` R4 |
| mgr:480 | voided | `void_invoice` R2 |
| mgr:483 | draft | `void_invoice` R3 |
| mgr:495 | loop over 0/1/many active payments | `void_invoice` R4, R7 |
| mgr:532 | not found / already set | `set_receiving_started` R1, R2 |
| mgr:538 | reason truthy | `set_receiving_started` R4 |
| mgr:560 | not draft | `sync_items_from_list` R1 |
| mgr:566 | loop over 0/1/many items | `sync_items_from_list` R3, R4 |
| mgr:567–569 | setdefault keys present/absent | `sync_items_from_list` R3 |
| mgr:577–582 | is_manual (the `True` branch is dead code — no caller ever sets it; see dead-code checklist) | `sync_items_from_list` R6 |
| mgr:585 | description empty / line_number present | `sync_items_from_list` R7 |
| mgr:586–589 | quantity/unit_price/line_subtotal None (None side unreachable) | `sync_items_from_list` R7, R7a |
| mgr:604 / 608 | invoice exists | `get_events` R1, `get_items` R1 |
| dao:33 | trimmed search empty | `list_invoices` R9a |
| dao:57 | loop over 4 order types | `list_invoices` R9 |
| dao:108 | account_id not None | `list_invoices` R4 |
| dao:110–114 | type/payment/status truthy | `list_invoices` R5 |
| dao:116 | invoice_number_search truthy | `list_invoices` R9 |
| dao:128 | digits → id match | `list_invoices` R10 |
| dao:131 | account_name_search truthy | `list_invoices` R11 |
| dao:133–139 | date bounds truthy | `list_invoices` R6, R7 |
| dao:141–143 | amount bounds not None | `list_invoices` R8 |
| dao:145 | open_balance_only | `list_open_invoices_page` R2, `list_invoices_page` R2 |
| dao:274 / 276 | section payable / receivable / other | `list_accounts_hub_page` R5 |
| dao:279 | search truthy | `list_accounts_hub_page` R4 |
| dao:301–303 | agg None → 0/False | `list_accounts_hub_page` R2 |
| dao:329 / 346 | distinct count None → 0 | `get_invoices_hub_summary` R2, R3 |
| dao:391 | prioritize PO given | `list_open_invoices_page` R3 |
| dao:441 (summarize) | voided excluded from totals | `summarize_invoices` R2 |
| inv_event dao | order by created_at desc | `get_events` R2 |
| inv_item dao | order by line_number | `get_items` R2 |

## Gap log
- G1 (account_invoice_manager.cases.md gap G1) — Intent (best-practice default, delegated by reviewer) + Test mechanics — `create_invoice` R9: a sent `invoice_amount` after the fix → 422 (`loc = ("invoice_amount",)`), matching `update_invoice` R2a; Errors row added; Notes: build passing cases with `invoice_amount` only while the field exists.
- G2 (gap G2) — Intent (best-practice default, delegated by reviewer) — detail texts fixed: BUG-625 404 `Order with ID {order_id} not found` (`create_invoice` R9b, `update_invoice` R12); BUG-631 400 `Cannot edit confirmed invoice fields: <fields>. Revert to draft to edit them.` (tests assert status + each field name); BUG-630 422 = `ValidationError` with `loc = (<field>,)`, message text not fixed (`update_invoice` R2a). Errors tables updated.
- G3 (gap G3) — Intent (best-practice default, delegated by reviewer) — "today" for overdue = application clock `utcnow().date()` in the manager (patch `app.managers.account_invoice_manager.utcnow`); due today is not overdue, yesterday is, no due date never is. `get_invoices_hub_summary` R2, `list_accounts_hub_page` R3; Notes updated.
- G4 (gap G4) — Contradiction — Q11 answer covers the `payment_status=overdue` filter but R5 did not. Added `list_invoices` R5a [BUG-635]: derived overdue filter (confirmed, unpaid/partial, due before today); `unpaid`/`partial` filters stay column equality (best-practice default, delegated by reviewer). Q11 Resolution and BUG-635 staging row updated; same bug, no new ID.
- G5 (gap G5) — Intent (best-practice default, delegated by reviewer) — `update_invoice` R12a [BUG-625]: validation uses the effective pair (sent value else stored), runs when either is sent and the pair changes.
- G6 (gap G6) — Intent (best-practice default, delegated by reviewer) — `update_invoice` R10 no longer lists `0` as "no check"; new R10a [BUG-629]: `account_id = 0` → 404 `Account with ID 0 not found`, nothing written (today: FK violation at flush, generic 400). Folded into BUG-629 (same fix: draft account-change validation); BUG-629 staging row updated.
- G7 (gap G7) — Fact — status-history table is `invoice_status_tracker` (columns listed in Notes for the test designer); `delete_invoice` R4 points to it.
- G8 (gap G8) — Fact — `delete_invoice` R3 now names every `ON DELETE SET NULL` referrer: `purchase_orders`, `expense_orders`, `sales_orders`, `work_orders`, `purchase_order_returns`, `sales_order_returns`, `machine_item_ledger`, `project_component_item_ledger`; Notes list the ledger's required columns.
- G9 (gap G9) — Fact — `quantity`/`unit_price`/`line_subtotal`/`description` are `NOT NULL` and each item is flushed on create, so R7's `null` branch is unreachable: new `sync_items_from_list` R7a; Errors rewritten (IntegrityError at flush, no event); Branch map row updated. Unreachable defensive expression inside a reachable comprehension, not a dead callable — not added to the dead-code list.
- G10 (gap G10) — Test mechanics — Notes: how to create real ties (explicit `created_at` / `line_number`) and make the heap order differ from the intended order; report an XPASS back as a gap.
- G11 (gap G11) — Fact — account names are not unique per workspace (no unique constraint); `list_accounts_hub_page` R6 and Notes say so, so the `id` tie-break is testable.
- G12 (gap G12) — Fact — `_recalculate_payment_status` and `_recalculate_invoice_amount` return `None`; `sync_items_from_list` R7 metadata items have exactly the five keys.
- G13 (gap G13) — Intent (best-practice default, delegated by reviewer) — `order_type`/`order_id` must be set together: `create_invoice` R9c (422 at schema, `loc` names the missing field) and `update_invoice` R12a (effective pair half-set → 400 `order_type and order_id must be set together`). Folded into BUG-625 (same linked-order validation fix); staging row updated.
- G14 (account_invoice_manager.verify.md finding 5) — Fact + Intent (best-practice default, delegated by reviewer) — `purchase_orders` has no `is_deleted` column (nor do `expense_orders` / `sales_orders`). Added `create_invoice` R9d defining "live" per order type: PO/EO `voided = False`; WO `is_deleted = False` and `status != "VOIDED"`; SO any existing row; non-live → same 404 as missing. R9b points to it; Notes say how to build a non-live order. Same fix as BUG-625 — staging row updated, no new ID.
- G15 (account_invoice_manager.verify.md finding 7; cases gap G15) — Fact + Intent (best-practice default, delegated by reviewer) — Fact: `AccountInvoiceUpdate` has no `order_type` field today (a sent value is silently ignored, not in `model_fields_set`). Intent: under the BUG-625 fix the schema gains a nullable `order_type`, normalised and restricted like `create_invoice` R9a (bad value → 422, `loc = ("order_type",)`). `update_invoice` Inputs row names it; R2a lists it among the fields clearable with `null`; new R2b states it; R12 says "effective `order_type`"; Errors row added; P2 updated. Same fix as BUG-625 — staging row updated, no new ID.
- R1 (apply-review 2026-11-14, owner chat "Invoice lock after completion": BUG-2730, 2731, 2733, 2735, 2736). This is a revision, not a cases gap. New shared block *Completed-order freeze* F1–F7. New rules `delete_invoice` R2a, `revert_to_draft` R2a, R2b, R3a (the R3 detail text, split off so the 400 itself keeps regression cover), `void_invoice` R3a, R3b. Note on the dead `locked` status in the Overview. Notes for the test designer (O1) explain how to build completed and not-completed orders and credit notes. Placement: in the manager (O1). Service follow-ups (a)–(e) are recorded under O1. **Cards in `account_invoice_manager.cases.md` to revise:**
  - **RV-05, RV-06:** the receiving detail changes (R3a, BUG-2736). Split each into a passing status/no-write card and an xfail detail card.
  - **DEL-01, DEL-11:** their PO / EO / SO / WO rows point at the draft (`invoice_id = D`), so they must be pinned **not completed** (PO stage `Draft`, SO `order_completed = False`, EO `completed_at = None`, WO `status = "DRAFT"`). Also update the *Other rows* PO/EO/SO/WO shorthand in Conventions: "neutral" must mean not completed, and a PO needs a `statuses` row for `current_status_id`.
  - Coverage-matrix rows for `delete_invoice`, `revert_to_draft`, `void_invoice`.
  - **New cards needed:** the freeze for each order kind × delete / revert / void. PO at `Receiving` is not frozen. A completed order of another workspace pointing at the invoice is ignored. An invoice linked only by `order_type` / `order_id` is not frozen. Check order: `revert_to_draft` R2 before R2a before R2b before R3 / R4; `void_invoice` R2 / R3 before R3a; `delete_invoice` R2 before R2a before R4. Credit-note revert is refused (R2a). Credit-note void on a completed PO / SO goes ahead (R3b, pass). F5: nothing written (payments untouched, 0 events).
  - **New card (2026-11-14, owner O1 (e)), pass:** on a confirmed invoice that belongs to a completed order (any kind, e.g. a sales order with `order_completed = True`), `update_invoice` changing `due_date`, `allow_payments` and `payment_locked_reason` succeeds. All three are stored, with their R7–R9 events, and there is no freeze 400 (`update_invoice` R3b).
  - Unaffected: RV-01–04, RV-07–12, VD-01–13, DEL-02–10, DEL-12, DEL-13.
