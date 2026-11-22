# Spec — `app/managers/expense_order_manager.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically — resolved
- **HR-9** `update_expense_order` R14 — 🐞 **BUG-740**. Intended: `updated_by` written only when at least one field actually changes value.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** merged with Q14 (same root cause — a side effect fires even though nothing changed). `updated_by` and the approvals-reset / `item_updated` event logging are all gated on an actual value change. Rules: `update_expense_order` R9, R14; `update_item` R8, R9.
- **HR-10** `update_expense_order` R3 — 🐞 **BUG-741**. Intended: the order row is read `FOR UPDATE`; the loser sees the completed state and gets the normal 400.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** order row read `FOR UPDATE` before the completed check. Rules: `update_expense_order` R13.
- **HR-10** `delete_expense_order` R3 — 🐞 **BUG-742**. Intended: order row read `FOR UPDATE`; loser gets 400 "Cannot delete a completed expense order".
**Answer:** bug — per HR-10 (house rule)
**Resolution:** merged with Q16 (same method, same change window). Order row read `FOR UPDATE` before the completed check; delete is also refused with 400 when an invoice is linked. Rules: `delete_expense_order` R3, R4.
- **HR-10** `add_item` R2, `update_item` R3, `remove_item` R3 — 🐞 **BUG-743**. Intended: the parent order row is read `FOR UPDATE` before the check; totals always equal the sum of the stored lines.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** parent order row read `FOR UPDATE` before the completed check in all three methods. Rules: `add_item` R2, `update_item` R3, `remove_item` R3.
- **HR-10** `set_approval` R4, R5 — 🐞 **BUG-744**. Intended: the order row is read `FOR UPDATE`; the loser sees the new state and gets the normal 400.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** order row read `FOR UPDATE` before the readiness / completed check, for both the approve and withdraw paths. Rules: `set_approval` R4, R5.
- **HR-8** `list_expense_orders_for_hub` R11 (shared by `count_expense_orders_for_hub`, `expense_order_hub_stats`, `list_expense_orders_recent_for_hub`, `expense_order_financial_snapshot`) — 🐞 **BUG-745**. Intended: `%`, `_` and `\` in the search text match literally (same pattern as BUG-013).
**Answer:** bug — per HR-8 (house rule)
**Resolution:** search text escaped before insertion into `ILIKE`. Rule: `list_expense_orders_for_hub` R11.
- **HR-6** `list_expense_orders_recent_for_hub` R2 — 🐞 **BUG-746**. Intended: `id` descending as final tie-breaker.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** merged with Q23 (same rule, same fix). Ordered by `coalesce(updated_at, created_at)` desc, then `id` desc — this also fixes never-updated orders sorting before recently-updated ones. Rule: `list_expense_orders_recent_for_hub` R2.
- **HR-6** `expense_order_financial_snapshot` R6 — 🐞 **BUG-747**. Intended: ties broken by account name case-insensitive ascending, then account id ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** applied as stated. Rule: `expense_order_financial_snapshot` R6.
- **HR-6** `expense_order_financial_snapshot` R12 — 🐞 **BUG-748**. Intended: ties broken by order `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** applied as stated. Rule: `expense_order_financial_snapshot` R12.
- **HR-6** `list_expense_orders` R2 — moot. `list_expense_orders` is removed entirely per Q24 (`remove`, no caller) — the ordering defect is deleted along with the method, no bug logged.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** moot — method removed (see Q24).

### Precedent matches — confirm all with ok

### Q1. A soft-deleted factory or department can be chosen as cost center — 🐞 BUG-340 (precedent)
**Background:** Factories and departments are soft-deleted (`is_deleted = True`, row stays). When an expense order is filed under "factory" or "department", the chosen id is checked only for "exists in this workspace".
**What happens today:** A deleted factory/department passes the check and is stored as the order's cost center (also via templates that still point to it).
**Example:** Factory 4 "Old Plant" was deleted last month. A user creates an expense order with category `factory`, cost center 4 → 201 Created; the order is booked against a factory that no longer appears anywhere in the UI.
**Rules affected:** `_validate_order_allocation` R5, R6
**Answer:** bug — per BUG-340 precedent: a soft-deleted (or missing / other-workspace) factory or department is rejected with the existing 404 "Selected factory not found" / "Selected department not found"; inactive-but-live ones still count (precedent — confirmed: ok)
**Resolution:** applied per BUG-340. Rules: `_validate_order_allocation` R5, R6.

### Q2. Line quantity and unit price accept more than 2 decimals or huge values — 🐞 BUG-021 (precedent)
**Background:** Quantity and unit price are stored as `NUMERIC(15,2)`. The line subtotal is computed in Python from the values as sent, then all three are rounded by the database on save.
**What happens today:** `quantity = 1.005`, `unit_price = 10` gives a computed subtotal 10.05 while the stored quantity is 1.01 (→ 10.10 expected); values with 14+ integer digits fail at save with a database error.
**Example:** A user enters 3 × 33.333 → stored as quantity 3, unit price 33.33, subtotal 100.00 (3 × 33.333 = 99.999 → 100.00); the line shows 3 × 33.33 = 100.00 instead of 99.99.
**Rules affected:** `_prepare_item_dict` R1, `update_item` R6
**Answer:** bug — per BUG-021 precedent: `ExpenseOrderItemCreate` / `ExpenseOrderItemUpdate` reject `quantity` / `unit_price` with more than 2 decimals or more than 13 integer digits (422), nothing written (precedent — confirmed: ok)
**Resolution:** applied per BUG-021. Rules: `_prepare_item_dict` R1, `update_item` R6.

### Q3. Line quantity can be zero or negative and unit price negative — 🐞 BUG-362 (precedent)
**Background:** The item schemas put no range on `quantity` or `unit_price`. Readiness for approval later requires every line's quantity to be above 0, but negative prices are never checked.
**What happens today:** Lines with quantity 0 or −5, or unit price −100, are saved; the order total can become 0 or negative, and a negative-price line does not block approval.
**Example:** A user adds a line "Refund" with quantity 1 and unit price −500 to a 300 order. The order total becomes −200; once approved, a payable invoice of −200 is drafted.
**Rules affected:** `_prepare_item_dict` R1, `add_item` R4, `update_item` R6
**Answer:** bug — per BUG-362 precedent: item schemas require `quantity > 0` and `unit_price >= 0` (422 otherwise, create and update), nothing written (precedent — confirmed: ok)
**Resolution:** applied per BUG-362. Rules: `_prepare_item_dict` R1, `add_item` R4, `update_item` R6.

### Q4. Required-approvals count accepts negative numbers — 🐞 BUG-362 (precedent)
**Background:** `required_approvals` on the order overrides the default "every assigned approver must approve". It is set through the order update.
**What happens today:** Any integer is stored, including negatives; a negative value makes approvals count as met with zero approvals.
**Example:** A user sends `{"required_approvals": -1}`. The order now shows "0 of −1 approvals — met", and the next item edit auto-creates the draft invoice without anyone approving.
**Rules affected:** `update_expense_order` R12, `approval_summary` R2
**Answer:** bug — per BUG-362 precedent: `ExpenseOrderUpdate.required_approvals` must be `>= 0` (422 otherwise), nothing written (precedent — confirmed: ok)
**Resolution:** applied per BUG-362. Rules: `update_expense_order` R12, `approval_summary` R2.

### Q5. Blank description is rejected on create but accepted on update — 🐞 BUG-004 (precedent)
**Background:** Create refuses an order whose description is empty or whitespace-only (400 "Description is required"). Update has no such check.
**What happens today:** `{"description": ""}` or `"   "` on update blanks the description; the order then fails the approval readiness check.
**Example:** A user clears the description box and saves → 200; the order now shows no description, and approvers get "Add a description before approvals can proceed".
**Rules affected:** `update_expense_order` R12
**Answer:** bug — per BUG-004 precedent: a blank / whitespace-only description is rejected on update too (same rule as create; nothing written) (precedent — confirmed: ok)
**Resolution:** applied per BUG-004. Rule: `update_expense_order` R12.

### New questions

### Q6. Expense numbers are globally unique in the database, so a second workspace cannot create orders — 🐞 BUG-749
**Background:** Order numbers are generated per workspace (`EXP-<year>-001`, `-002`, …, looking only at that workspace's orders). The model declares uniqueness per workspace, but the database (from the migration baseline) also has a **unique index on `expense_number` alone**, across all workspaces.
**What happens today:** When workspace B creates its first order of the year, it gets `EXP-2026-001`, which workspace A already has; the insert fails with a unique violation (409 "A database constraint was violated…" at the API). B keeps getting the same number on every retry.
**Example:** Workspace A has created 5 expense orders in 2026. A user in workspace B clicks "Create expense order" → 409 every time; B can never create expense orders until A's numbers run out of overlap.
**Rules affected:** `create_expense_order` R6
**Suggested answer:** bug — expense numbers are unique per workspace only (drop the global unique index `ix_expense_orders_expense_number`, keep `uq_eo_workspace_number`); workspace B's first order is `EXP-<year>-001`
**Answer:** bug — numbers unique per workspace only: drop global index ix_expense_orders_expense_number, keep uq_eo_workspace_number (reviewer accepted suggestion)
**Resolution:** merged with Q7, Q8 into one bug (BUG-749) — all three fix `create_expense_order` R6's number generation. Rule: `create_expense_order` R6.

### Q7. Numbering breaks after order 999 of a year — 🐞 BUG-749
**Background:** The next number is found by taking the workspace's highest `expense_number` for the year **as text** and adding 1 to its last part. As text, `EXP-2026-999` sorts above `EXP-2026-1000`.
**What happens today:** Order 1000 is created fine; for order 1001 the "highest" is still `…-999`, so it tries `EXP-2026-1000` again and fails with a unique violation (409) — permanently.
**Example:** A busy workspace has 1000 expense orders in 2026. Every further "Create expense order" returns 409 for the rest of the year.
**Rules affected:** `create_expense_order` R6
**Suggested answer:** bug — the next number is the numeric maximum of the year's suffixes + 1 (padded to at least 3 digits), so `…-999` → `…-1000` → `…-1001`
**Answer:** bug — next number = numeric max of the year's suffixes + 1, padded to at least 3 digits (reviewer accepted suggestion)
**Resolution:** merged into BUG-749 (see Q6). Rule: `create_expense_order` R6.

### Q8. Two orders created at the same moment get the same number — 🐞 BUG-749
**Background:** The number is computed by reading the current highest number, with no lock or sequence; the database rejects the duplicate.
**What happens today:** Two concurrent creates in one workspace both compute e.g. `EXP-2026-008`; the second fails with 409 and the user's order is lost.
**Example:** A recurring-template run and a user create an expense order in the same second; the user sees "A database constraint was violated" and must re-enter the order.
**Rules affected:** `create_expense_order` R6
**Suggested answer:** bug — number assignment is race-safe (per-workspace counter row locked `FOR UPDATE`, or retry on unique violation); concurrent creates both succeed with distinct numbers
**Answer:** bug — race-safe numbering (locked per-workspace counter or retry on unique violation); both creates succeed (reviewer accepted suggestion)
**Resolution:** merged into BUG-749 (see Q6). Rule: `create_expense_order` R6.

### Q9. The account on an order is not checked to belong to the workspace — 🐞 BUG-750
**Background:** `account_id` is accepted on create and update. The database only checks that some account with that id exists (in any workspace). Hub search and the "open by account" dashboard join the account and show its name.
**What happens today:** An account id from another workspace (or a soft-deleted account) is stored. Its name then appears in this workspace's search matches and dashboard; a non-existent id fails at save with a database error (409).
**Example:** User in workspace A creates an order with `account_id = 812`, which belongs to workspace B's "Acme Supplies". A's dashboard now lists "Acme Supplies" under open orders by account, disclosing B's account name.
**Rules affected:** `create_expense_order` R12, `update_expense_order` R12
**Suggested answer:** bug — `account_id` must be a live (not soft-deleted) account of the same workspace; otherwise 404 "Selected account not found", nothing written
**Answer:** bug — account_id must be a live account of the same workspace, else 404 'Selected account not found', nothing written (reviewer accepted suggestion)
**Resolution:** merged with Q11 into one bug (BUG-750, pattern `unvalidated-stored-reference` — same root cause as BUG-340: a stored foreign id accepted without checking it belongs to the workspace or is live). Rules: `create_expense_order` R12, `update_expense_order` R12.

### Q10. The linked invoice can be changed freely through the order update — 🐞 BUG-751
**Background:** An order's invoice is normally created and linked by the system after approval. `ExpenseOrderUpdate` nevertheless accepts `invoice_id`, and the manager writes it without any check; it is not recorded in the activity log and does not reset approvals.
**What happens today:** A user can point an order at any invoice id — another order's invoice in the same workspace, or an invoice in another workspace. Completing the order then confirms whichever invoice is linked; dashboard unpaid amounts are read from it.
**Example:** User sets order 12's `invoice_id` to 40 (the draft invoice of order 15). Completing order 12 confirms invoice 40 — order 15's bill — and order 12's own draft invoice is orphaned.
**Rules affected:** `update_expense_order` R12
**Suggested answer:** bug — `invoice_id` is not client-writable: removed from `ExpenseOrderUpdate` (the field is ignored/rejected with 422), only the system links invoices
**Answer:** bug — invoice_id is not client-writable (removed from ExpenseOrderUpdate); only the system links invoices (reviewer accepted suggestion)
**Resolution:** merged with Q22 into one bug (BUG-751, pattern `client-writable-internal-field`: a field that is system/internal-only is nevertheless client-settable through an update schema). Rule: `update_expense_order` R12.

### Q11. Template id on create is not validated — 🐞 BUG-750
**Background:** `ExpenseOrderCreate` accepts `order_template_id`, meant to be set only when the order is generated from a template. It is stored as given.
**What happens today:** Any id is stored: a template of another workspace is accepted (the order then reports as generated from that template); a non-existent id fails at save with a database error (409).
**Example:** A user posts a plain order with `order_template_id: 3`, a template of another workspace → 201; the order claims to come from a template the workspace cannot see.
**Rules affected:** `create_expense_order` R12
**Suggested answer:** bug — `order_template_id` on plain create must be an existing template of the same workspace (404 "Order template with ID N not found"), or better, not accepted on plain create at all
**Answer:** bug — order_template_id must be a template of the same workspace (404), or not accepted on plain create (reviewer accepted suggestion)
**Resolution:** merged into BUG-750 (see Q9) — chose "not accepted on plain create at all" (simpler than a redundant validation path): `order_template_id` is removed from `ExpenseOrderCreate` and set only internally by `create_expense_order_from_template` (best-practice default, delegated by reviewer). Rule: `create_expense_order` R12.

### Q12. Category "other" keeps a cost center id — 🐞 BUG-752
**Background:** Only factory and department orders need a cost center; for "other", the cost-center check is skipped entirely.
**What happens today:** An "other" order is saved with whatever `cost_center_id` was sent, and switching an order from `factory` to `other` keeps the old factory id on the order.
**Example:** An order is booked to factory 4, then re-categorised as "other". It still has `cost_center_id = 4`; a report that groups by cost center still counts it under factory 4.
**Rules affected:** `_validate_order_allocation` R2, `update_expense_order` R6, `create_expense_order_from_template` R3
**Suggested answer:** bug — when the (resulting) category is `other`, `cost_center_id` is stored as `null`
**Answer:** bug — when the resulting category is 'other', cost_center_id is stored as null (reviewer accepted suggestion)
**Resolution:** applied as stated. Rules: `_validate_order_allocation` R2, `update_expense_order` R6, `create_expense_order_from_template` R3.

### Q13. Optional order and line fields cannot be cleared — 🐞 BUG-753
**Background:** Update payloads drop every field sent as `null` before applying them.
**What happens today:** Sending `null` for `due_date`, `account_id`, `cost_center_id`, `description` (order) or `unit_price`, `unit`, `notes`, `description` (line) is silently ignored; the old value stays and the response is 200.
**Example:** A user removes the due date from an order and saves → 200, but the order still shows the old due date and stays in "Overdue" on the dashboard.
**Rules affected:** `update_expense_order` R2, `update_item` R5
**Suggested answer:** bug — an explicit `null` clears nullable fields (use `exclude_unset` only); required fields (`expense_category`, `expense_date`, `quantity`) reject `null` with 422
**Answer:** bug — explicit null clears nullable fields (exclude_unset only); required fields reject null with 422 (reviewer accepted suggestion)
**Resolution:** applied as stated. Rules: `update_expense_order` R2, `update_item` R4.

### Q14. Saving unchanged details (or an empty line edit) clears everyone's approvals — 🐞 BUG-740
**Background:** Editing order details (account, category, cost center, dates, description) or any line resets all recorded approvals, so approvers must approve again.
**What happens today:** The reset happens whenever one of those fields is **present** in the payload, even with its current value; for lines, any item update — including an empty one `{}` — clears approvals and logs "Line N updated".
**Example:** Two approvers have approved order 9. A user opens the edit form and presses Save without changing anything → both approvals are cleared, the approvers are notified to re-approve.
**Rules affected:** `update_expense_order` R9, `update_item` R8, R9
**Suggested answer:** bug — approvals are reset, and "updated" events logged, only when at least one field actually changes value
**Answer:** bug — reset approvals and log update events only when a field actually changes value (reviewer accepted suggestion)
**Resolution:** merged into BUG-740 (see HR-9 line — same root cause). Rules: `update_expense_order` R9, `update_item` R8, R9.

### Q15. Voided orders can still be edited and approved — 🐞 BUG-754
**Background:** Voiding an order (service) unlinks and deletes its draft invoice and marks it voided. The manager's edit guards only check "completed", never "voided".
**What happens today:** On a voided order you can change details, add/edit/remove lines, add/remove approvers and approve; approving it (via the service) can auto-create a fresh draft invoice for a voided order.
**Example:** Order 20 was voided as a duplicate. An approver later clicks Approve on it → 200, and a new draft payable invoice appears in accounting.
**Rules affected:** `update_expense_order` R3, `add_item` R2, `update_item` R3, `remove_item` R3, `add_approver` R1, `set_approval` R4
**Suggested answer:** bug — voided orders are read-only: every mutation returns 400 "Expense order is voided"
**Answer:** bug — voided orders are read-only: every mutation returns 400 'Expense order is voided' (reviewer accepted suggestion)
**Resolution:** applied as stated. Rules: `update_expense_order` R3, `add_item` R2, `update_item` R3, `remove_item` R3, `add_approver` R1, `set_approval` R4.

### Q16. Deleting an order leaves its invoice behind — 🐞 BUG-742
**Background:** Orders that are not completed can be hard-deleted (lines, approvers and activity log go with them). An order may already have a linked (draft or confirmed) invoice; the invoice stores the order id without a database link.
**What happens today:** Delete succeeds regardless of the linked invoice; the invoice remains in accounting pointing to an order that no longer exists.
**Example:** Order 30 has draft invoice 55. The user deletes order 30 → 204. Invoice 55 still shows "Auto-created from expense order EXP-2026-030" and can be confirmed and paid.
**Rules affected:** `delete_expense_order` R4
**Suggested answer:** bug — delete is refused with 400 ("Void the expense order instead") when an invoice is linked; orders without an invoice can still be deleted
**Answer:** bug — delete refused with 400 ('Void the expense order instead') when an invoice is linked (reviewer accepted suggestion)
**Resolution:** merged into BUG-742 (see HR-10 delete_expense_order line — same method). Rule: `delete_expense_order` R4.

### Q17. An order with no approvers and no explicit requirement counts as approved — 🐞 BUG-755
**Background:** When `required_approvals` is not set, the requirement is "all assigned approvers". The creator is added as approver on create, but any approver — including the creator — can be removed.
**What happens today:** After removing every approver, "approvals met" is true with 0 of 0; the next edit auto-creates the draft invoice.
**Example:** A user creates order 40 (creator is the only approver), removes themself as approver, then edits a line → a draft payable invoice is created without anyone approving.
**Rules affected:** `approval_summary` R4
**Suggested answer:** bug — with no explicit `required_approvals` and no approvers, approvals are NOT met (required = 1); only an explicit `required_approvals = 0` (e.g. from templates) waives approval
**Answer:** bug — with no explicit requirement and no approvers, approvals are not met (required = 1); only explicit required_approvals = 0 waives approval (reviewer accepted suggestion)
**Resolution:** applied as stated. Rule: `approval_summary` R4.

### Q18. Approvers can be added or removed after the order is complete — 🐞 BUG-756
**Background:** Withdrawing an approval on a completed order is refused. Adding/removing approvers has no such check.
**What happens today:** On a completed order, approvers can be added (then show as "pending") or removed (including ones who approved); the approval count shown for the finished order changes after the fact.
**Example:** Order 50 was completed with 2 of 2 approvals. Someone removes one approver → the order now reads "1 of 1 approvals" and the audit picture no longer matches who signed off.
**Rules affected:** `add_approver` R1, `remove_approver` R1
**Suggested answer:** bug — adding or removing approvers on a completed order returns 400 "Expense order is complete"
**Answer:** bug — adding/removing approvers on a completed order returns 400 'Expense order is complete' (reviewer accepted suggestion)
**Resolution:** applied as stated (pattern `missing-state-guard`, same as BUG-754). Rules: `add_approver` R1, `remove_approver` R1.

### Q19. Approving twice (or withdrawing when not approved) is recorded again — 🐞 BUG-757
**Background:** An approver can approve or withdraw their own approval.
**What happens today:** Approving when already approved succeeds, moves `approved_at` to now and logs another "Approved expense order" event; withdrawing when not approved logs "Withdrew approval".
**Example:** An approver double-clicks Approve → activity log shows "Approved expense order" twice and the approval time is the second click.
**Rules affected:** `set_approval` R6, R7
**Suggested answer:** bug — setting the state the approver already has is a no-op: no event, `approved_at` kept, record returned unchanged
**Answer:** bug — setting the state the approver already has is a no-op (no event, approved_at kept) (reviewer accepted suggestion)
**Resolution:** applied as stated. Rules: `set_approval` R6, R7.

### Q20. "Not ready for approval" message is generic when a line is incomplete — 🐞 BUG-758
**Background:** Approval is blocked until category, date, cost center, description exist and every line has a description and a quantity above 0. The explanation text covers all checks except the line-level ones.
**What happens today:** When a line has no description or quantity 0, the approver gets the generic 400 "Order is not ready for approval".
**Example:** Line 3 has no description. The approver clicks Approve → "Order is not ready for approval", with no hint which part is missing.
**Rules affected:** `approvability_gap_reason` R6, `set_approval` R4
**Suggested answer:** bug — the reason names the line problem, e.g. "Every expense line needs a description and a quantity above 0 before approvals can proceed"
**Answer:** bug — the reason names the line problem (e.g. 'Every expense line needs a description and a quantity above 0 before approvals can proceed') (reviewer accepted suggestion)
**Resolution:** applied as stated. Rules: `approvability_gap_reason` R6, `set_approval` R4.

### Q21. Creating from a template fails when the template's default approver has left — 🐞 BUG-759
**Background:** A template can name a default approver, who is added to each generated order. Adding requires an active workspace member.
**What happens today:** If the default approver is no longer an active member, the whole create-from-template call fails with 400 "User is not an active member of this workspace"; no order is created.
**Example:** Template "Monthly rent" names Rahim as approver; Rahim was suspended. Every "Create from template" for rent now fails until someone edits the template.
**Rules affected:** `create_expense_order_from_template` R8
**Suggested answer:** bug — the order is still created without that approver, and an event records that the default approver was skipped (not an active member)
**Answer:** bug — create the order without that approver and log an event saying the default approver was skipped (reviewer accepted suggestion)
**Resolution:** applied as stated. Rule: `create_expense_order_from_template` R8.

### Q22. Line `approved` flag is writable but means nothing — 🐞 BUG-751
**Background:** `ExpenseOrderItemUpdate` accepts `approved: bool`; the line model stores it. Nothing in the backend reads a line's `approved` flag (approval is per approver, per order).
**What happens today:** `{"approved": true}` on a line is saved, logs "Line N updated" and clears the order's approvals.
**Example:** A client sends `approved: true` for line 2 → line 2 shows approved in the API response, while the order still has 0 approvals.
**Rules affected:** `update_item` R5
**Suggested answer:** bug — `approved` is not accepted on line update (field removed from `ExpenseOrderItemUpdate`)
**Answer:** bug — 'approved' not accepted on line update (removed from ExpenseOrderItemUpdate) (reviewer accepted suggestion)
**Resolution:** merged into BUG-751 (see Q10). Rule: `update_item` R5.

### Q23. "Recent orders" shows never-edited orders first — 🐞 BUG-746
**Background:** The hub's recent-orders widget sorts by last update time, newest first. Orders never updated after creation have no update time; in the database, "no value" sorts before every date when sorting newest-first.
**What happens today:** Orders with no `updated_at` come first, above orders edited a minute ago.
**Example:** Workspace has 50 old orders never touched since creation and 5 edited today. The "Recent" widget (10 rows) shows 10 of the old untouched orders and none of today's edits.
**Rules affected:** `list_expense_orders_recent_for_hub` R2
**Suggested answer:** bug — order by last activity = `updated_at`, falling back to `created_at` when null, newest first, then `id` descending
**Answer:** bug — order by coalesce(updated_at, created_at) desc, then id desc (reviewer accepted suggestion)
**Resolution:** merged into BUG-746 (see HR-6 `list_expense_orders_recent_for_hub` line — same rule, same fix). Rule: `list_expense_orders_recent_for_hub` R2.

### Q24. Manager's plain `list_expense_orders` is never used — ♻️ removed
**Background:** The API list endpoint and the service go through the hub list (`list_expense_orders_for_hub`); the manager's `list_expense_orders` (category/account/invoice filter, newest created first) has no caller.
**What happens today:** Unreachable from the API. It also treats `account_id = 0` as "no filter" and orders by creation time only.
**Example:** No user-visible effect; the method only adds maintenance/test cost.
**Rules affected:** `list_expense_orders` R1–R4
**Suggested answer:** remove
**Answer:** remove (reviewer accepted suggestion)
**Resolution:** `list_expense_orders` moved to **Not specified** as dead code; its section and Branch-map rows removed. Logged in `expense_order_manager.deadcode-staging.md`. This also makes the `list_expense_orders` HR-6 violation moot (see house-rule violations above).

### Q25. Deleting an order leaves no record of it — OWNER — 🐞 BUG-1193
**Background:** An expense order has no soft delete: a delete removes the row, and the database removes its activity log with it (`ON DELETE CASCADE`). The question was asked and answered in `tests/unit/dao/expense_order_event.spec.md` Q1 and comes here through its FU-1a, because the rule is this manager's. It is recorded here on 2026-11-01, after this spec's approval.
**What happens today:** Any order that is not completed can be deleted, approved or not, and then nothing shows it ever existed: every event goes, and no row anywhere says who deleted it.
**Example:** Rahim creates expense order EO-41, two people approve it, and Rahim deletes it on Friday. On Monday the database holds no row saying who approved or deleted it.
**Rules affected:** `delete_expense_order` R5
**Answer:** bug — deleting a not-completed order must leave a record of the order and who deleted it, so it does not vanish without trace (owner, 2026-11-01)
**Resolution:** BUG-1193 (pattern `hard-delete-leaves-no-trace`). The design is the one in `tests/unit/dao/expense_order_event.spec.md` Q1 Resolution and is Claude's, not the owner's words. R5 is split: what holds today stays in R5, untagged; the record is R5a, the refused delete R5b, the required `user_id` R5c. The order's events are still not copied, and no endpoint reads `workspace_audit_logs` today. Rules: `delete_expense_order` R5, R5a, R5b, R5c.

## Overview
Business logic for **expense orders** (direct expenses without inventory, e.g. rent, utilities): create (plain or from an order template), edit details, manage lines and order totals, assign approvers and record approvals, and the activity log. The only callers are `ExpenseOrderService` (which commits and handles invoices, completion and voiding), `approval_notification_service` (readiness / approval summary) and `AttachmentManager` (`log_event`). Invariants it is meant to protect: a completed order is frozen; totals equal the sum of the lines; any edit of details or lines after an approval invalidates the approvals; every change leaves an event.

**Callables:** 34 specified · 3 not specified
**Externals to mock:** `utcnow` — patch it where it is used, not where it is defined: `app.managers.expense_order_manager.utcnow` (`approved_at` in `set_approval`) and `app.dao.expense_order.utcnow` (today / due-date windows in `expense_order_financial_snapshot`). Event `created_at` and approver `assigned_at` come from model column defaults (`default=utcnow` bound when the model module is imported), so patching either module name does **not** affect them — see Notes for the test designer. Note: `date.today()` (default expense date) and `datetime.now()` (number year) are read directly from the system clock and are not mocked.
**Integration-only behavior:** none

**Notes for the test designer:**
- The manager never commits; every write is flushed. Tests read state back from the same session.
- The test database is built by `alembic upgrade head`, which **still has** the workspace-wide unique index on `expense_number` (the fix in BUG-749/R6 requires a new migration that does not exist yet) — two workspaces creating orders in the same year collide today. The per-workspace-uniqueness part of `create_expense_order` R6 is therefore expected to fail (`xfail(strict=True, reason="BUG-749")`) until that migration lands; write the test to the intended per-workspace behavior regardless.
- Expected numbers use the current system year: `EXP-<datetime.now().year>-NNN`.
- `approval_notification_service` / service-layer behavior (invoice creation, notifications, `items_updated_at`) is out of scope here.
- `updated_at` has `onupdate=utcnow`; it may be set during create when items change the totals. Do not assert `updated_at` after create.
- Column-default timestamps (event `created_at`, approver `assigned_at`) cannot be frozen by patching `utcnow` (no freezegun/time-machine in the venv). Assert them as lying between a real-clock `utcnow()` taken just before and just after the call; when a test needs a specific order or value (e.g. `list_events` / `list_approvers` ordering), set the column explicitly on the row after it is created and flush.
- "Profile missing" branches (`add_approver` R5, `remove_approver` R3, `list_approvers` R3, `list_events` R3) are **unreachable with a real database**: approver `user_id` and membership `user_id` are non-null FKs to `profiles.id` with `ON DELETE CASCADE` (deleting the profile deletes the approver/membership row), and event `performed_by` is an FK with `ON DELETE SET NULL` (deleting the profile makes `performed_by` `None`, which is the `None` branch). The `'User #<id>'` / `None`-profile fallbacks are defensive; no case is required for them. For `list_events`, the reachable equivalent is: delete the performer's profile -> the event's `performed_by` becomes `None` and its profile entry is `None`.
- `workspace_audit_logs` (class `app.models.workspace_audit_log.WorkspaceAuditLog`, BUG-1193): columns `workspace_id`, `user_id`, `action`, `resource_type`, `resource_id`, `metadata` (attribute `metadata_json`, generic `JSON`), `ip_address`, `user_agent`, `created_at`. It has no foreign key to `expense_orders`, so a row survives the order. Read a row back by `resource_type` + `resource_id`.

## Not specified
- `ExpenseOrderManager.__init__` — wires collaborators, no logic
- `ExpenseOrderManager._is_completed` — trivial predicate (`completed_at is not None`); its effect is specified in every guard that uses it (`_guard_confirmed_updates`, `_guard_item_mutations`, `delete_expense_order`, `set_approval`)
- `ExpenseOrderManager.list_expense_orders` — dead code, to be removed (reviewer; Q24). No caller (the API list endpoint and service go through `list_expense_orders_for_hub`). See `expense_order_manager.deadcode-staging.md`.

---

## `ExpenseOrderManager._has_recorded_approvals(session, eo_id, workspace_id)`
**Shape:** helper
**Persistence:** reads
**Visibility:** internal (used by: `update_expense_order`, `add_item`, `update_item`, `remove_item`)

**Purpose:** Tell whether at least one approver of the order has approved.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| eo_id | int | order id; not checked to exist |
| workspace_id | int | only approver rows of this workspace count |

**Returns:** `bool`.

**Rules:**
- **R1.** Returns `True` when at least one approver row of the order (same workspace) has `approved = True`.
- **R2.** Returns `False` when the order has approvers but none approved, or has no approvers at all.
- **R3.** Approver rows stored with a different `workspace_id` are ignored.

**Errors:** none
**Side effects:** none

---

## `ExpenseOrderManager.is_approvable(session, eo)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `set_approval`, `approval_notification_service`)

**Purpose:** Minimal readiness gate before an approval can be recorded.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| eo | ExpenseOrder | the order; its lines are loaded by `eo.id` + `eo.workspace_id` |

**Returns:** `bool`.

**Rules:**
- **R1.** `False` when `expense_category` is empty/`None` or `expense_date` is `None`.
- **R2.** `False` when category is anything other than `other` and `cost_center_id` is `None`.
- **R3.** `False` when `description` is `None`, `""` or whitespace-only.
- **R4.** `False` when the order has no lines.
- **R5.** `False` when any line has an empty/whitespace-only/`None` description, or a quantity ≤ 0 (a `None` quantity counts as 0).
- **R6.** `True` otherwise — category `other` needs no cost center; unit price is not checked (0, `None` or negative all pass).

**Errors:** none
**Side effects:** none

---

## `ExpenseOrderManager.approvability_gap_reason(session, eo)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `set_approval`, `approval_notification_service`)

**Purpose:** Human-readable reason why the order is not ready for approval.

**Inputs:** as `is_approvable`.

**Returns:** `str` or `None`.

**Rules:** (checks in this order; first hit wins)
- **R1.** Category empty/`None` or `expense_date` `None` → `'Set category and expense date before approvals can proceed'`.
- **R2.** Category not `other` and no cost center → `'Select a <category> for this expense order before approvals can proceed'` (category text inserted as stored, e.g. `'Select a factory for …'`).
- **R3.** Description `None`/blank → `'Add a description before approvals can proceed'`.
- **R4.** No lines → `'Add at least one expense line before approvals can proceed'`.
- **R5.** No line has a blank/whitespace/`None` description or quantity ≤ 0 (a `None` quantity counts as 0) → `None`.
- **R6.** [BUG-758] Otherwise (a line has a blank description or quantity ≤ 0) → `'Every expense line needs a description and a quantity above 0 before approvals can proceed'`. *(Today: line-level problems produce no reason — `None` is returned even though `is_approvable` is `False`.)*

**Errors:** none
**Side effects:** none

---

## `ExpenseOrderManager._validate_order_allocation(session, workspace_id, expense_category, cost_center_id)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_expense_order`, `update_expense_order`)

**Purpose:** Check the category and that the cost center matches it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| expense_category | str | must be exactly `factory`, `department` or `other` (case-sensitive, no trimming) |
| cost_center_id | int \| None | factory id or department id depending on category |

**Returns:** `None`.

**Rules:**
- **R1.** A category outside `factory`/`department`/`other` (incl. `"Factory"`, `" factory"`, `""`) → 400.
- **R2.** [BUG-752] Category `other` → accepted whatever `cost_center_id` is passed as; the value itself is not checked here. *(Today: also not cleared by the caller. Now: the caller — `create_expense_order`, `update_expense_order`, `create_expense_order_from_template` — stores `cost_center_id = None` whenever the resulting category is `other`; see those rules.)*
- **R3.** Category `factory` or `department` with `cost_center_id` `None` → 400.
- **R4.** `factory`: the id must exist as a factory of this workspace; a missing id or one belonging to another workspace → 404.
- **R5.** [BUG-340 precedent] `factory`: a soft-deleted factory of this workspace is also rejected with 404 (the same "Selected factory not found" as R4). *(Today: a soft-deleted or inactive factory of this workspace is accepted.)* An inactive-but-live factory still counts as found.
- **R6.** `department`: same as R4/R5 against departments — missing, other-workspace, or soft-deleted id → 404; inactive-but-live accepted. *(Today: a soft-deleted or inactive department of this workspace is accepted.)* [BUG-340 precedent]
- **R7.** `cost_center_id = 0` is treated as a given id (looked up, → 404), not as missing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 400 | `Invalid category: <value>. Must be factory, department, or other.` |
| R3 | HTTPException 400 | `Select a <category> for this expense order` |
| R4 | HTTPException 404 | `Selected factory not found` |
| R6 | HTTPException 404 | `Selected department not found` |

**Side effects:** none

---

## `ExpenseOrderManager.resolve_invoice_account_id(record)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `ExpenseOrderService._create_draft_invoice`)

**Purpose:** Account to bill when drafting the order's invoice.

**Returns:** `record.account_id`.

**Rules:**
- **R1.** Returns the order's `account_id` when it is set (non-zero).
- **R2.** `account_id` `None` (or `0`) → 422.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R2 | HTTPException 422 | `Set an account on the expense order before creating an invoice` |

**Side effects:** none

---

## `ExpenseOrderManager.reset_approvals(session, eo_id, workspace_id, user_id, reason='Section unconfirmed')`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `update_expense_order`, `add_item`, `update_item`, `remove_item`, `ExpenseOrderService.void_expense_order`)

**Purpose:** Clear every recorded approval on the order.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| eo_id | int | order id; not checked to exist |
| user_id | int | recorded as `performed_by` of the event |
| reason | str | event description prefix; default `'Section unconfirmed'` |

**Returns:** `None`.

**Rules:**
- **R1.** Every approver of the order (same workspace) with `approved = True` gets `approved = False`, `approved_at = None`.
- **R2.** Approvers not approved are untouched; approvers of other orders/workspaces are untouched.
- **R3.** When at least one approval was cleared, one event `approvals_reset` is logged with description `'<reason> (<n> approval(s) cleared)'`, `performed_by = user_id`, no metadata.
- **R4.** When nothing was approved (or there are no approvers), nothing changes and no event is logged.

**Errors:** none
**Side effects:** approver rows updated; one event row (R3); flushed.

---

## `ExpenseOrderManager._format_scalar_value(field, value)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `_collect_field_changes`)

**Purpose:** Display text for a field value in the change log.

**Returns:** `str`.

**Rules:**
- **R1.** `None` → `'—'` (em dash).
- **R2.** A `date` (or `datetime`) → ISO format (`'2026-03-05'`).
- **R3.** A `Decimal` with no fractional part → integer text (`Decimal('10.00')` → `'10'`); otherwise normalized (`Decimal('10.50')` → `'10.5'`).
- **R4.** Anything else → `str(value)` trimmed; if that is empty → `'—'`. (`0` → `'0'`; `False` → `'False'`.)
- **R5.** `field` does not affect the result.

**Errors:** none
**Side effects:** none

---

## `ExpenseOrderManager._collect_field_changes(record, update_dict)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** internal (used by: `update_expense_order`)

**Purpose:** List of human-readable before/after changes for the tracked order fields.

**Returns:** list of `{'field', 'label', 'from_value', 'to_value'}` dicts.

**Rules:**
- **R1.** Tracked fields and labels, in this output order: `account_id` "Account", `expense_category` "Category", `cost_center_id` "Cost center", `expense_date` "Expense date", `due_date` "Due date", `description` "Description", `required_approvals` "Required approvals".
- **R2.** A tracked field is listed only when present in `update_dict` and its new value differs (`!=`) from the stored one; `from_value`/`to_value` formatted per `_format_scalar_value`.
- **R3.** Fields not tracked (e.g. `invoice_id`, `updated_by`) never appear.
- **R4.** Differences only in whitespace count as changes (`'Rent'` → `'Rent '` is listed, even though both display as `'Rent'`).

**Errors:** none
**Side effects:** none

---

## `ExpenseOrderManager._guard_confirmed_updates(record, update_dict)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `update_expense_order`)

**Rules:**
- **R1.** Completed order (`completed_at` set) and non-empty `update_dict` → 400.
- **R2.** Completed order with empty `update_dict` → passes.
- **R3.** [BUG-754] Voided order (`voided` true) and non-empty `update_dict` → 400. *(Today: voided is not checked; a voided order can still be edited.)*
- **R4.** Voided order with empty `update_dict` → passes.
- **R5.** Not completed and not voided → passes.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 400 | `Expense order is complete and cannot be edited` |
| R3 | HTTPException 400 | `Expense order is voided` |

**Side effects:** none

---

## `ExpenseOrderManager._guard_item_mutations(record)`
**Shape:** validator
**Persistence:** pure
**Visibility:** internal (used by: `add_item`, `update_item`, `remove_item`)

**Rules:**
- **R1.** Completed order → 400.
- **R2.** [BUG-754] Voided order → 400. *(Today: voided not checked; a voided order's lines can still be added/edited/removed.)*
- **R3.** Otherwise passes.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 400 | `Expense order is complete` |
| R2 | HTTPException 400 | `Expense order is voided` |

**Side effects:** none

---

## `ExpenseOrderManager._prepare_item_dict(item_dict)`
**Shape:** compute
**Persistence:** pure
**Visibility:** internal (used by: `create_expense_order`, `add_item`)

**Purpose:** Add the computed line subtotal to a line payload.

**Returns:** the same dict (mutated), with `line_subtotal` added.

**Rules:**
- **R1.** `line_subtotal = quantity × unit_price`, computed exactly from the values given. [BUG-021 precedent] `quantity`/`unit_price` are validated by `ExpenseOrderItemCreate`/`ExpenseOrderItemUpdate` before this method runs — more than 2 decimals or more than 13 integer digits is rejected with 422 at the schema, so no fractional rounding surprise reaches this computation. *(Today: no schema precision limit — a value like `quantity=1.005` computes a subtotal inconsistent with what the database stores after rounding to 2 decimals.)* [BUG-362 precedent] `quantity` must be `> 0` and `unit_price` must be `>= 0` at the schema — a zero/negative quantity or negative price never reaches this method. *(Today: no range check here or in the schema.)*
- **R2.** Missing `quantity` key → 1.
- **R3.** `unit_price` `None`/missing/0 → subtotal 0.

**Errors:** none
**Side effects:** mutates the passed dict.

---

## `ExpenseOrderManager.create_expense_order(session, data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ExpenseOrderService.create_expense_order`, `create_expense_order_from_template`)

**Purpose:** Create an order with its lines, the creator as first approver, and a `created` event.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| data | ExpenseOrderCreate | `expense_category` required str; `account_id`, `cost_center_id`, `expense_date`, `due_date`, `description`, `items` optional. [BUG-750] `order_template_id` removed — a plain create never sets it (best-practice default, delegated by reviewer — see Q11; the field is still set internally by `create_expense_order_from_template`). |
| user_id | int | creator |

**Returns:** the new `ExpenseOrder`, flushed, not committed.

**Rules:**
- **R1.** Category / cost center are checked first per `_validate_order_allocation` (400/404); nothing is written on failure.
- **R2.** Description `None`, `""` or whitespace-only → 400; nothing written. (Checked after R1.)
- **R3.** The order is stored with `workspace_id`, `created_by = user_id`, and the given fields as sent (description not trimmed). [BUG-752] Extended from Q12 for consistency with `update_expense_order` R6 (best-practice default, delegated by reviewer): when the category is `other`, `cost_center_id` is stored as `null` regardless of what was sent.
- **R4.** `expense_date` not given → today's date (`date.today()`, server clock).
- **R5.** `required_approvals` is `None`; `invoice_id` `None`; `voided` false; `completed_at` `None`.
- **R6.** [BUG-749] `expense_number` = `EXP-<current year>-<n>`, race-safe and collision-free per-workspace: `n` = the numeric maximum of the workspace's suffixes for that year (not a text comparison) + 1, zero-padded to at least 3 digits; `001` when the workspace has none that year. The read-then-write is protected against concurrent creates (a locked per-workspace counter, or retry on unique-violation) so two simultaneous creates in the same workspace both succeed with distinct numbers. The database's uniqueness constraint on `expense_number` is per-workspace only (`uq_eo_workspace_number`; the migration's workspace-wide unique index `ix_expense_orders_expense_number` is dropped), so two different workspaces can both have `EXP-<year>-001` in the same year. *(Today: three separate bugs — (1) a workspace-wide unique index makes a second workspace's first order of the year collide with another workspace's existing number, permanent 409s; (2) the "highest" suffix is compared as text, so `…-999` sorts above `…-1000` and numbering breaks after order 999; (3) no lock/sequence, so two concurrent creates in one workspace can compute the same number and the loser's order is lost to a 409.)*
- **R7.** One approver row is created: `user_id` = creator, `assigned_by` = creator, `approved = False`, `approved_at` `None`.
- **R8.** Each line in `data.items` is created in the given order with `line_number` 1, 2, 3 …, `workspace_id`, `expense_order_id`, and `line_subtotal` per `_prepare_item_dict`.
- **R9.** `subtotal` and `total_amount` of the order = sum of the line subtotals; `0` with no lines (`items` `None` or `[]`).
- **R10.** One event `created`, description `'Expense order created'`, `performed_by = user_id`, no metadata.
- **R11.** [BUG-362 precedent] A line's `quantity`/`unit_price` is already validated by the item schema (`quantity > 0`, `unit_price >= 0`) before reaching this method — see `_prepare_item_dict` R1. *(Today: a line with quantity 0/negative or negative price is accepted.)*
- **R12.** [BUG-750] `account_id` must be a live account of the same workspace, else 404 `Selected account not found`; nothing written. *(Today: `account_id` is stored without any workspace check; an id that does not exist anywhere fails at flush with `IntegrityError`, an id of another workspace is stored silently.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | see `_validate_order_allocation` | |
| R2 | HTTPException 400 | `Description is required` |
| R12 | HTTPException 404 | `Selected account not found` |

**Side effects:** 1 order row, 1 approver row, N line rows, 1 event row; flushed.

---

## `ExpenseOrderManager.update_expense_order(session, eo_id, data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ExpenseOrderService.update_expense_order`)

**Purpose:** Edit order header fields, log the changes and reset approvals when details change.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| eo_id | int | order in this workspace |
| data | ExpenseOrderUpdate | all optional: `account_id`, `expense_category`, `cost_center_id`, `expense_date`, `due_date`, `required_approvals`, `description`. [BUG-751] `invoice_id` removed — not client-writable (best-practice default, delegated by reviewer — see Q10; only the system links invoices). |

**Returns:** the updated order (flushed), with an extra attribute `_approvals_reset` (`True`/`False`).

**Rules:**
- **R1.** Order missing or in another workspace → 404; nothing written.
- **R2.** [BUG-753] Fields that are unset are ignored; an explicit `null` **clears** a nullable field (`account_id`, `cost_center_id`, `due_date`, `description`* — see R12 for description's separate blank rule) (`exclude_unset` only, not `exclude_none`). `expense_category` and `expense_date` are required and reject `null` with 422 before this method runs. An explicit `description: null` is **not** a clear: description is required, so `null` is treated as blank and rejected with 400 `Description is required` per R12; nothing written (best-practice default, delegated by reviewer). *(Today: unset **or** `null` are both ignored — sending `null` never clears a value; `description: null` returns 200 with the description unchanged.)*
- **R3.** [BUG-741] [BUG-754] The order row is read `FOR UPDATE` before the state checks. A completed order with at least one field present in the payload → 400; nothing written. A voided order with at least one field present → 400 `Expense order is voided`; nothing written. [BUG-753] A field sent as explicit `null` counts as present, so a payload of only nulls (e.g. `{"due_date": null}`) on a completed or voided order is also rejected (best-practice default, delegated by reviewer: a frozen record rejects any edit attempt). Only an empty payload passes the guard. *(Today: explicit nulls are dropped before the guard, so an all-null payload on a completed order returns 200 with nothing changed except `updated_by`; no row lock — a concurrent completion can land between the check and the write; voided orders are not checked at all and remain editable.)*
- **R4.** When `expense_category` or `cost_center_id` is in the payload, the resulting pair (payload value, else stored value) is checked per `_validate_order_allocation`; failure → 400/404, nothing written.
- **R5.** When neither is in the payload, allocation is not re-checked.
- **R6.** [BUG-752] Changing the resulting category to `other` stores `cost_center_id` as `null`, discarding the old cost center (and any `cost_center_id` sent alongside it). *(Today: the stored `cost_center_id` is kept unchanged.)*
- **R7.** When at least one tracked field changes value (per `_collect_field_changes`), one event `updated` with description `'Order details updated'`, `performed_by = user_id`, metadata `{'changes': [...]}` is logged.
- **R8.** No `updated` event when no tracked field changes value (empty payload, or every sent field equal to its stored value). Changing only `required_approvals` **does** log an `updated` event (it is a tracked field per `_collect_field_changes` R1) but does not reset approvals (R10).
- **R9.** [BUG-740] When at least one of `account_id`, `expense_category`, `cost_center_id`, `expense_date`, `due_date`, `description` **actually changes value** (per `_collect_field_changes`) **and** the order has at least one recorded approval, all approvals are reset per `reset_approvals` with reason `'Order details edited'`, and `_approvals_reset` is `True`. *(Today: the reset fires whenever one of those fields is merely present in the payload, even with its current, unchanged value.)*
- **R10.** Otherwise `_approvals_reset` is `False` and approvals are untouched; changing only `required_approvals` never resets approvals.
- **R11.** When both happen, the `approvals_reset` event is logged before the `updated` event.
- **R12.** [BUG-750] `account_id`, when present, must be a live account of the same workspace, else 404 `Selected account not found`; nothing written. *(Today: no workspace check — an id of another workspace, or a non-existent id, is stored/fails at flush.)* [BUG-362 precedent] `required_approvals` must be `>= 0` (422 at the schema otherwise). [BUG-004 precedent] `description`, when present, is rejected with 400 `Description is required` if blank/whitespace-only (same rule as create). *(Today: `required_approvals` accepts any integer; a blank/whitespace description is silently stored.)*
- **R13.** [BUG-741] Same row lock described in R3 (kept as its own rule number for the Branch map).
- **R14.** [BUG-740] `updated_by = user_id` only when at least one field actually changes value (same fix as R9 — see BUG-740). *(Today: set on every successful call, including an empty payload — also on a completed order.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 404 | `Expense order with ID <eo_id> not found` |
| R3 | HTTPException 400 | `Expense order is complete and cannot be edited` / `Expense order is voided` |
| R4 | see `_validate_order_allocation` | |
| R12 | HTTPException 404 / 400 | `Selected account not found` / `Description is required` |

**Side effects:** order row updated; approver rows/`approvals_reset` event (R9); `updated` event (R7); flushed.

---

## `ExpenseOrderManager.get_expense_order(session, eo_id, workspace_id)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: many manager methods, service, `approval_notification_service`)

**Rules:**
- **R1.** Returns the order with that id in this workspace (voided and completed orders included — orders have no soft delete).
- **R2.** Missing id, or id of another workspace's order → 404.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R2 | HTTPException 404 | `Expense order with ID <eo_id> not found` |

**Side effects:** none

---

## `ExpenseOrderManager.list_expense_orders_for_hub(session, workspace_id, *, skip=0, limit=50, **filters)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderService.list_expense_orders_page`)

**Purpose:** Filtered, paged order list for the expense-order hub.

**Inputs (filters):** `expense_category`, `account_id`, `invoice_id`, `date_from`, `date_to`, `status_ids` (list of ints), `invoice_filter` (`'invoiced'`/`'not_invoiced'`), `search`, `exclude_complete` (default **True** here), `exclude_voided` (default **True** here). The service always passes all of them, with `exclude_complete`/`exclude_voided` default False. Unknown keyword → `TypeError`.

**Returns:** list of orders.

**Rules:** (these filter rules are shared by `count_expense_orders_for_hub`, `expense_order_hub_stats`, `list_expense_orders_recent_for_hub` and the filtered part of `expense_order_financial_snapshot`)
- **R1.** Only orders of this workspace.
- **R2.** `expense_category` truthy → exact match; `""`/`None` → no filter.
- **R3.** `account_id` / `invoice_id` not `None` → exact match (`0` filters to orders with that id, i.e. none).
- **R4.** `date_from` / `date_to` → `expense_date` between them, both ends inclusive.
- **R5.** `status_ids` non-empty → order must be in at least one listed stage: `1` draft (not completed, no invoice), `2` invoiced (not completed, invoice linked), `3` complete (completed). Unknown ids are ignored; a list with only unknown ids applies **no** stage filter.
- **R6.** `invoice_filter` `'invoiced'` → invoice linked; `'not_invoiced'` → no invoice; any other value → no filter.
- **R7.** `exclude_voided` true → voided orders removed; false → included.
- **R8.** `exclude_complete` true → completed orders removed; false → included.
- **R9.** `search` `None`/blank/whitespace → no filter. Otherwise the trimmed text matches (case-insensitive substring) the order number, the category, or the linked account's name; also the category whose label (`Factory`/`Department`/`Other`) contains the text. Orders without account can still match on number/category.
- **R10.** All filters are combined with AND, applied before paging.
- **R11.** [BUG-745] `%`, `_` and `\` in the search text match literally. *(Today: unescaped — `_` or `%` alone matches every order. A backslash is Postgres's default `LIKE` escape character, so today it escapes the next character instead of matching itself: search `Acme\Ltd` does **not** find an account named `Acme\Ltd` but **does** find one named `AcmeLtd`; a search ending in `\` (e.g. `EXP\`) escapes the trailing `%` and matches only text containing `EXP%`, i.e. nothing for normal data.)*
- **R12.** Ordered by `expense_date` desc, then `created_at` desc, then `id` desc; then `skip`/`limit` (defaults 0/50).

**Errors:** `TypeError` for an unknown filter keyword.
**Side effects:** none

---

## `ExpenseOrderManager.count_expense_orders_for_hub(session, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderService.list_expense_orders_page`)

**Rules:**
- **R1.** Returns the number of distinct orders matching the filters, per `list_expense_orders_for_hub` R1–R11 (same defaults), without paging; `0` when none.

**Errors:** `TypeError` for an unknown filter keyword.
**Side effects:** none

---

## `ExpenseOrderManager.expense_order_hub_stats(session, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderService.get_expense_order_hub_stats`)

**Returns:** tuple `(total_count: int, total_value: Decimal, open_count: int, open_value: Decimal, not_invoiced_count: int)`.

**Rules:** over the orders matching the filters (per `list_expense_orders_for_hub` R1–R11):
- **R1.** `total_count` = number of orders; `total_value` = sum of `total_amount`.
- **R2.** `open_count` / `open_value` = count / sum of `total_amount` of those not completed.
- **R3.** `not_invoiced_count` = number with no invoice linked.
- **R4.** No matching orders → `(0, Decimal('0'), 0, Decimal('0'), 0)`.

**Errors:** `TypeError` for an unknown filter keyword.
**Side effects:** none

---

## `ExpenseOrderManager.list_expense_orders_recent_for_hub(session, workspace_id, *, limit=10, **filters)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderService.get_expense_order_hub_stats`)

**Rules:**
- **R1.** Orders matching the filters (per `list_expense_orders_for_hub` R1–R11), at most `limit` (default 10).
- **R2.** [BUG-746] Ordered by `coalesce(updated_at, created_at)` descending (last-activity time), then `id` descending. *(Today: ordered by `updated_at` desc, then `created_at` desc, with no `id` tie-breaker — and because `updated_at` is `null` for a never-edited order, and the database sorts `null` first when descending, never-edited orders come before recently-edited ones.)*

**Errors:** `TypeError` for an unknown filter keyword.
**Side effects:** none

---

## `ExpenseOrderManager.expense_order_financial_snapshot(session, workspace_id, **filters)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderService.get_expense_order_hub_stats`)

**Purpose:** Dashboard buckets: category, stage, open-by-account (filtered) plus due timeline and unpaid pipeline (unfiltered).

**Returns:** dict with keys `category_breakdown`, `stage_pipeline`, `open_by_account`, `due_timeline`, `unpaid_pipeline`.

**Rules — filtered part** (orders matching the filters per `list_expense_orders_for_hub` R1–R11):
- **R1.** `category_breakdown`: one entry per category present, `{key, label, count, total_value}`, ordered by `total_value` descending; label `Factory`/`Department`/`Other` for the known slugs, otherwise the slug with `_` → space, title-cased. Categories beyond the 6th would be merged into a trailing `other` entry (unreachable with 3 valid categories).
- **R2.** No matching orders → `category_breakdown = []`.
- **R3.** `stage_pipeline`: always exactly three entries in order `draft`, `invoiced`, `complete` with labels `Draft`, `Invoiced`, `Complete`, each `{key, label, count, total_value}`; stages with no orders show `0`/`Decimal(0)`. Stage: completed → complete; else invoice linked → invoiced; else draft.
- **R4.** `open_by_account`: among matching orders that are not completed and have an account, grouped per account: `{account_id, account_name, count, total_value}`.
- **R5.** Orders without an account are not in `open_by_account`.
- **R6.** [BUG-747] `open_by_account` is the top 5 by `total_value` descending, ties by account name case-insensitive, then account id. *(Today: ties unordered.)*

**Rules — actionable part** (ignores `filters`; all orders of the workspace that are **not voided and not completed**):
- **R7.** `due_timeline`: exactly four buckets in order `overdue` "Overdue", `due_this_week` "Due this week", `due_later_this_month` "Due later this month", `no_due_date` "No due date"; each `{key, label, count, total_value, samples}`.
- **R8.** With today = `utcnow().date()`: due date before today → overdue; today … coming Sunday (inclusive; when today is Sunday, only today) → due this week; after that up to the last day of the current month → due later this month; no due date → no due date; due after the current month → in no bucket. The week check is applied before the month check: when the coming Sunday falls in the next month (e.g. today 2026-03-30 Monday, Sunday 2026-04-05), a due date of 2026-04-02 is **due this week**; 2026-04-06 is in no bucket; in that week the "due later this month" bucket is always empty (every remaining day of the month, e.g. 2026-03-31, is already due this week).
- **R9.** `samples`: at most 3 per bucket, `{id, order_number, total_value, sublabel}` with `sublabel` the due date ISO string (or `None` for no-due-date), taken in order of due date ascending (no date last), then order number.
- **R10.** `unpaid_pipeline`: exactly three buckets `unpaid` "Unpaid", `partial` "Partial", `overdue` "Overdue"; each `{key, label, count, outstanding_value, samples}`. An order counts when it has a linked invoice that is not `voided` and whose `payment_status` is one of these three; it goes to the bucket of that status.
- **R11.** `outstanding_value` adds `invoice_amount − paid_amount` of each invoice (null amounts count as 0).
- **R12.** [BUG-748] Samples: at most 3 per bucket, `{id, order_number, total_value = outstanding, sublabel = payment status}`, highest outstanding first, ties by order `id` ascending. *(Today: ties unordered.)*
- **R13.** No qualifying orders → all buckets present with `0` counts, `Decimal(0)` values, empty samples.

**Errors:** `TypeError` for an unknown filter keyword.
**Side effects:** none

---

## `ExpenseOrderManager.delete_expense_order(session, eo_id, workspace_id, user_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `ExpenseOrderService.delete_expense_order`)

**Purpose:** Hard-delete a not-yet-completed order, leaving one audit record of it (BUG-1193).

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| eo_id | int | order in this workspace |
| user_id | int | the deleter; required. [BUG-1193] *(requires new parameter `user_id`; today the method has no such parameter)* |

**Rules:**
- **R1.** Order missing or in another workspace → 404; nothing deleted.
- **R2.** Completed order → 400; nothing deleted.
- **R3.** [BUG-742] The order row is read `FOR UPDATE` before the completed check. *(Today: no row lock — a completion committed concurrently can be deleted along with its order.)*
- **R4.** [BUG-742] An order with a linked invoice (draft or confirmed) → 400 `Void the expense order instead`; nothing deleted. This check runs **after** the completed check: an order that is both completed and invoiced gets R2's 400 `Cannot delete a completed expense order`. *(Today: delete succeeds regardless; the invoice remains in accounting pointing to an order that no longer exists.)* Otherwise the order row, all its lines, all its approver rows and all its events are deleted — also when the order is voided.
- **R5.** Returns `None`; no event is logged in `expense_order_events` (the log is deleted with the order).
- **R5a.** [BUG-1193] A delete that succeeds writes exactly one `workspace_audit_logs` row, through `workspace_audit_log_dao.log_action`, in the same transaction as the delete (flushed, not committed: rolling back removes the row and brings the order back). Its fields: `workspace_id` = the order's workspace; `user_id` = the deleter (the parameter, not the order's creator); `action` = `expense_order_deleted`; `resource_type` = `expense_order`; `resource_id` = the order id; `metadata` = exactly `{"number": <expense_number>, "total_amount": "<total with 2 decimals, as text>", "created_by": <creator id>, "created_at": "<ISO>"}`. Example: number `EXP-2026-041`, total 1234.50, created by U1 at 2026-01-01 09:00:00 gives `{"number": "EXP-2026-041", "total_amount": "1234.50", "created_by": <U1 id>, "created_at": "2026-01-01T09:00:00"}`; a total of 0 gives `"0.00"`. It holds for every delete that succeeds, also of a voided or an approved order. The order's events are not copied. The row stays after the order is gone. *(Today: no row is written; nothing shows the order existed or who deleted it.)*
- **R5b.** [BUG-1193] A refused delete (R1, R2, R4) writes no `workspace_audit_logs` row. *(Today: no row is written, but a call with `user_id` fails before any check because the parameter does not exist yet. The refusal in R4 itself is BUG-742.)*
- **R5c.** [BUG-1193] `user_id` is required: a call without it raises `TypeError` and deletes nothing. *(Today: no such parameter; a call without it deletes the order.)* The fix also touches `ExpenseOrderService.delete_expense_order` and `DELETE /expense-orders/{id}/`, which has no current user today and must pass it.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 404 | `Expense order with ID <eo_id> not found` |
| R2 | HTTPException 400 | `Cannot delete a completed expense order` |
| R4 | HTTPException 400 | `Void the expense order instead` |
| R5c | TypeError | Python's missing-argument message |

**Side effects:** rows deleted, flushed. Other orders' rows untouched. [BUG-1193] One `workspace_audit_logs` row added (R5a), flushed; none on a refusal (R5b).

---

## `ExpenseOrderManager.add_item(session, eo_id, data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ExpenseOrderService.add_item`)

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| data | ExpenseOrderItemCreate | `description`, `quantity` (default 1), `unit`, `unit_price`, `notes`; no ranges |

**Returns:** the new line, flushed.

**Rules:**
- **R1.** Order missing / other workspace → 404 (per `get_expense_order`).
- **R2.** [BUG-743] [BUG-754] Completed order → 400 per `_guard_item_mutations`; voided order → 400 per `_guard_item_mutations`; nothing written either way. Order row read `FOR UPDATE` before the check. *(Today: no row lock; voided orders are not checked and accept new lines.)*
- **R3.** `line_number` = highest existing line number of the order + 1 (1 for an order without lines; gaps left by removed lines are not reused).
- **R4.** Line stored with the given fields and `line_subtotal` per `_prepare_item_dict`.
- **R5.** Order `subtotal` and `total_amount` recomputed per `_recalc_totals`.
- **R6.** Event `item_added`, description `'Line <n> added'`, `performed_by = user_id`, metadata `{'line_number': n}`.
- **R7.** If the order had at least one recorded approval, all approvals are reset per `reset_approvals` with reason `'Expense items edited'` (logged after `item_added`); otherwise approvals untouched.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 404 | `Expense order with ID <eo_id> not found` |
| R2 | HTTPException 400 | `Expense order is complete` / `Expense order is voided` |

**Side effects:** line row, order totals, events, approver rows (R7); flushed.

---

## `ExpenseOrderManager.update_item(session, item_id, data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `ExpenseOrderService.update_item`)

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| data | ExpenseOrderItemUpdate | all optional: `description`, `quantity`, `unit`, `unit_price`, `notes`. [BUG-751] `approved` removed — not client-writable (see Q22; nothing in the backend reads a line's `approved` flag). |

**Returns:** the updated line, flushed.

**Rules:**
- **R1.** Line missing or in another workspace → 404 `Expense order item not found`.
- **R2.** Parent order not found in this workspace → 404 (per `get_expense_order`).
- **R3.** [BUG-743] [BUG-754] Parent completed → 400 per `_guard_item_mutations`; parent voided → 400 per `_guard_item_mutations`; nothing written either way. Parent row read `FOR UPDATE` before the check. *(Today: no row lock; voided orders are not checked and accept line edits.)*
- **R4.** [BUG-753] Unset fields are ignored; an explicit `null` clears a nullable field (`unit_price`, `unit`, `notes`, `description`). `quantity` is required and rejects `null` with 422 before this method runs. *(Today: unset **or** `null` are both ignored — cannot clear.)*
- **R5.** Given fields are written as sent.
- **R6.** When `quantity` or `unit_price` is given, `line_subtotal` = (new or stored quantity) × (new or stored unit price, `None` → 0). Otherwise `line_subtotal` unchanged.
- **R7.** Order totals recomputed per `_recalc_totals`.
- **R8.** [BUG-740] Event `item_updated`, description `'Line <n> updated'`, `performed_by = user_id`, no metadata — logged only when at least one field actually changes value. *(Today: logged on every successful call, also for an empty payload or unchanged values.)*
- **R9.** [BUG-740] If the order had at least one recorded approval **and** at least one field actually changed value, approvals reset per `reset_approvals` with reason `'Expense items edited'`. *(Today: reset fires on every call, also when nothing changed.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 404 | `Expense order item not found` |
| R2 | HTTPException 404 | `Expense order with ID <id> not found` |
| R3 | HTTPException 400 | `Expense order is complete` / `Expense order is voided` |

**Side effects:** line row, order totals, events, approver rows; flushed.

---

## `ExpenseOrderManager.remove_item(session, item_id, workspace_id, user_id)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: `ExpenseOrderService.remove_item`)

**Returns:** the deleted line object (detached/deleted state; its attributes, e.g. `expense_order_id`, `line_number`, are still readable).

**Rules:**
- **R1.** Line missing / other workspace → 404 `Expense order item not found`.
- **R2.** Parent order not found → 404.
- **R3.** [BUG-743] [BUG-754] Parent completed → 400; parent voided → 400; nothing deleted either way. Parent row read `FOR UPDATE` before the check. *(Today: no row lock; voided orders are not checked and accept line removal.)*
- **R4.** The line row is deleted; other lines keep their line numbers (no renumbering).
- **R5.** Order totals recomputed per `_recalc_totals` (0 when the last line is removed).
- **R6.** Event `item_removed`, description `'Line <n> removed'`, `performed_by = user_id`.
- **R7.** Approvals reset as `add_item` R7.

**Errors:** as `update_item` R1–R3.
**Side effects:** line deleted, totals, events, approver rows; flushed.

---

## `ExpenseOrderManager.get_items(session, eo_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: service, `account_invoice_service`)

**Rules:**
- **R1.** Order missing / other workspace → 404 (per `get_expense_order`).
- **R2.** Returns all lines of the order in this workspace, ordered by `line_number` ascending; `[]` when none.

**Errors:** 404 `Expense order with ID <eo_id> not found`.
**Side effects:** none

---

## `ExpenseOrderManager._recalc_totals(session, eo)`
**Shape:** compute
**Persistence:** writes
**Visibility:** internal (used by: `add_item`, `update_item`, `remove_item`)

**Rules:**
- **R1.** `eo.subtotal` and `eo.total_amount` = sum of the stored `line_subtotal` of all the order's lines (same workspace), a `null` subtotal counting as 0; `0` with no lines.

**Side effects:** order row updated, flushed.

---

## `ExpenseOrderManager.list_approvers(session, eo_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ExpenseOrderService.list_approvers`)

**Returns:** list of `(approver, profile_or_None, position_or_None)`.

**Rules:**
- **R1.** Order missing / other workspace → 404.
- **R2.** One tuple per approver of the order, ordered by `assigned_at` ascending.
- **R3.** `profile` = the approver's profile, `None` if it no longer exists.
- **R4.** `position` = the approver's workspace-membership position (whatever the membership status); `None` when there is no membership in this workspace or no position.
- **R5.** `[]` when no approvers.

**Errors:** 404 `Expense order with ID <eo_id> not found`.
**Side effects:** none

---

## `ExpenseOrderManager.approval_summary(session, eo)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `approvals_met`, service, `approval_notification_service`)

**Returns:** `(approved_count, required, met)`.

**Rules:**
- **R1.** `approved_count` = approvers of the order with `approved = True`.
- **R2.** `required_approvals` set (not `None`) → `required` = that value. [BUG-362 precedent] `required_approvals` is validated `>= 0` at the schema (see `update_expense_order` R12), so a negative value cannot reach this method through the API; a `0` value is still valid and means "waived".
- **R3.** Not set and at least one approver → `required` = number of approvers.
- **R4.** [BUG-755] Not set and no approvers → `required = 1`, so `met` is `False` with no approvals. Only an explicit `required_approvals = 0` (e.g. set by a template's waive-approval path) waives approval. *(Today: `required = 0`, so `met` is `True` with no approvals — removing every approver, including the creator, makes an order silently "approved".)*
- **R5.** `met` = `approved_count >= required`.

**Errors:** none
**Side effects:** none

---

## `ExpenseOrderManager.approvals_met(session, eo)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: service)

**Rules:**
- **R1.** Returns the `met` value of `approval_summary`.

---

## `ExpenseOrderManager.add_approver(session, eo_id, user_id, workspace_id, assigned_by)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: service, `create_expense_order_from_template`)

**Returns:** the new approver row, flushed.

**Rules:**
- **R1.** Order missing / other workspace → 404. [BUG-754] [BUG-756] Completed order → 400 `Expense order is complete`; voided order → 400 `Expense order is voided`. *(Today: completed and voided orders accept new approvers.)*
- **R2.** `user_id` without membership in this workspace, or with membership status other than `'active'` (e.g. `suspended`, `invited`) → 400.
- **R3.** User already an approver of this order → 409.
- **R4.** Row created: `user_id`, `assigned_by`, `approved = False`, `approved_at` `None`, `assigned_at` = now.
- **R5.** Event `approver_added`, description `'Added <name> as approver'`, `performed_by = assigned_by`, metadata `{'user_id': …, 'user_name': …}`; name = profile name, or `'User #<id>'` when the profile is missing.
- **R6.** Adding does not reset or change existing approvals.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 404 / 400 | `Expense order with ID <eo_id> not found` / `Expense order is complete` / `Expense order is voided` |
| R2 | HTTPException 400 | `User is not an active member of this workspace` |
| R3 | HTTPException 409 | `User is already an approver for this order` |

**Side effects:** approver row, event; flushed.

---

## `ExpenseOrderManager.remove_approver(session, eo_id, user_id, workspace_id, performed_by=None)`
**Shape:** delete
**Persistence:** writes
**Visibility:** public (used by: service)

**Rules:**
- **R1.** No approver row for (order, user) in this workspace — including a missing order or another workspace's order → 404 `Approver not found`. [BUG-756] Completed order → 400 `Expense order is complete`, checked after the approver-row lookup. *(Today: completed orders accept removal, including of an approver who already approved.)* Voided orders are unaffected by this fix (not in scope — see Q15's rule list) and stay removable.
- **R2.** The approver row is deleted.
- **R3.** Event `approver_removed`, description `'Removed <name> as approver'` (name as `add_approver` R5), `performed_by` = given value (may be `None`), metadata `{'user_id', 'user_name'}`.
- **R4.** Returns `None`; other approvers untouched.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 404 / 400 | `Approver not found` / `Expense order is complete` |

**Side effects:** row deleted, event; flushed.

---

## `ExpenseOrderManager.set_approval(session, eo_id, user_id, workspace_id, approved)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: service `approve_as_me` / `unapprove_as_me`)

**Returns:** the approver row, flushed.

**Rules:**
- **R1.** `user_id` is not an approver of that order in this workspace → 403 (checked first, so a missing order also gives 403).
- **R2.** Approver exists but order not found → 404 (only possible for inconsistent data).
- **R3.** Approving (`approved = True`) a completed order is not separately guarded here — it is allowed whenever the readiness gate (R4) passes, exactly as today. [BUG-754] Approving a **voided** order is now blocked (see R4). Withdrawing is blocked only on a completed order (R5); a voided order can still have its approval withdrawn (unchanged — out of scope for Q15).
- **R4.** [BUG-744] The order row is read `FOR UPDATE` before this check. [BUG-754] `approved = True` on a voided order → 400 `Expense order is voided`; nothing written. Otherwise, `approved = True` and the order fails `is_approvable` → 400 with the text of `approvability_gap_reason`; nothing written. [BUG-758] For an order whose only problem is an incomplete line, the detail is `'Every expense line needs a description and a quantity above 0 before approvals can proceed'` *(Today: `'Order is not ready for approval'`, because the gap reason is `None` for line problems)*. Once BUG-758 is fixed the `'Order is not ready for approval'` fallback is unreachable (every `is_approvable` failure has a reason); it is kept as defensive code and needs no case (best-practice default, delegated by reviewer). *(Today: no row lock; voided orders are not checked and can be approved.)*
- **R5.** [BUG-744] The order row is read `FOR UPDATE` before this check (same lock as R4, covering the withdraw path). `approved = False` on a completed order → 400; nothing written. *(Today: no row lock.)*
- **R6.** [BUG-757] Approve: `approved = True`, `approved_at = utcnow()`; event `approved`, description `'Approved expense order'`, `performed_by = user_id`. When the approver **already has** `approved = True`, this is a no-op: no event logged, `approved_at` kept at its existing value, the row returned unchanged. *(Today: re-approving moves `approved_at` to now and logs a second `approved` event.)*
- **R7.** [BUG-757] Withdraw: `approved = False`, `approved_at = None`; event `approval_withdrawn`, description `'Withdrew approval'`. When the approver **already has** `approved = False`, this is a no-op: no event logged, row returned unchanged. *(Today: withdrawing when not approved still logs a `approval_withdrawn` event.)* Withdraw does not check readiness.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R1 | HTTPException 403 | `You are not an assigned approver for this order` |
| R2 | HTTPException 404 | `Expense order with ID <eo_id> not found` |
| R4 | HTTPException 400 | `Expense order is voided` / gap reason (`Order is not ready for approval` only as an unreachable fallback after BUG-758) |
| R5 | HTTPException 400 | `Cannot withdraw approval — order is complete` |

**Side effects:** approver row, event; flushed.

---

## `ExpenseOrderManager.log_event(session, eo_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** public (used by: this manager, service, `AttachmentManager`)

**Returns:** the new event row, flushed.

**Rules:**
- **R1.** Creates an event with the given `workspace_id`, `expense_order_id`, `event_type`, `description`, `metadata` (stored as JSON, `None` allowed), `performed_by` (may be `None`), `created_at = utcnow()`.
- **R2.** No check that the order belongs to `workspace_id`; a non-existent order id fails at flush with `IntegrityError`; `event_type` longer than 50 characters fails at flush.

**Side effects:** one event row, flushed.

---

## `ExpenseOrderManager.list_events(session, eo_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: service)

**Returns:** list of `(event, profile_or_None)`.

**Rules:**
- **R1.** Order missing / other workspace → 404.
- **R2.** All events of the order in this workspace, newest first (`created_at` desc, then `id` desc); `[]` when none.
- **R3.** `profile` = profile of `performed_by`; `None` when `performed_by` is `None` or the profile no longer exists.

**Errors:** 404 `Expense order with ID <eo_id> not found`.
**Side effects:** none

---

## `ExpenseOrderManager.create_expense_order_from_template(session, template_id, workspace_id, user_id, overrides)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `ExpenseOrderService.create_expense_order_from_template`)

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| template_id | int | order template of this workspace |
| overrides | ExpenseOrderFromTemplateCreate | optional `expense_date`, `due_date`, `description` |

**Returns:** the new order, flushed.

**Rules:**
- **R1.** Template missing / other workspace → 404 `Order template with ID <id> not found`.
- **R2.** Inactive template (`is_active = False`) → 400 `Template is inactive`; nothing written.
- **R3.** The order is created per `create_expense_order` (all its rules and errors apply) with: template's `account_id`, category (template category, or `other` when empty/`None`), template's `cost_center_id` (set to `null` instead when the resulting category is `other` — `create_expense_order` R3, BUG-752), `expense_date` = override or today, `due_date` = override (template has none), description = override when non-empty else template description. "Empty" means `None` or `""` only: a whitespace-only override (e.g. `"   "`) is used as given and then rejected by `create_expense_order` R2 with 400 `Description is required`; no order is created (best-practice default, delegated by reviewer: an explicit invalid value is rejected, never silently replaced). [BUG-750] `order_template_id` is no longer part of the `create_expense_order` call (removed from `ExpenseOrderCreate` — see Q11); this method sets `order_template_id = template_id` on the created record directly afterward, so the stored value is always this validated template's id (R1 already rejects a missing / other-workspace template).
- **R4.** Lines copied from the template's lines (description, quantity, unit, unit price, notes) in template line-number order, renumbered 1…N; subtotals recomputed.
- **R5.** `requires_approval = False` → order `required_approvals = 0`; no extra event (even if `auto_approve` is also true).
- **R6.** `requires_approval = True` and `auto_approve = True` → `required_approvals = 0` and event `auto_approved`, description `'Auto-approved — following template instructions'`, metadata `{'order_template_id': id}`, `performed_by = user_id`.
- **R7.** Otherwise `required_approvals` stays `None`; when the template has a `default_approver_id` different from the creator, that user is added per `add_approver` (event `approver_added`, `assigned_by = user_id`). When it equals the creator, or is `None`, nothing is added.
- **R8.** [BUG-759] An inactive / non-member default approver does **not** fail the call: the order is still created without that approver, and an event `default_approver_skipped`, description `'Default approver <name> is not an active member and was skipped'`, metadata `{'user_id': …, 'user_name': …}`, `performed_by = user_id` is logged in place of the `approver_added` event. *(Today: fails the whole call with 400 per `add_approver` R2 — no order is created.)*
- **R9.** Finally event `created_from_template`, description `'Generated from template "<template_name>"'`, metadata `{'order_template_id': id}`, `performed_by = user_id`. Events in order: `created`, then `auto_approved` or `approver_added` (if any), then `created_from_template`.
- **R10.** The creator is always an approver (from `create_expense_order` R7), also when approval is waived.

**Errors:** as R1, R2 plus every `create_expense_order` error (e.g. 400 `Description is required` when both override and template description are empty). R8 no longer raises (see BUG-759).
**Side effects:** as `create_expense_order` plus R5–R9.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 64 | any approver approved | `_has_recorded_approvals` R1, R2 |
| dao approver 16–18 | workspace filter | `_has_recorded_approvals` R3 |
| 68 | no category / no date | `is_approvable` R1 |
| 70 | not other and no cost center | `is_approvable` R2 |
| 72 | blank description | `is_approvable` R3 |
| 75 | no items | `is_approvable` R4 |
| 77–80 | each item description / qty > 0 (`None` qty → 0) | `is_approvable` R5, R6 |
| 83 | no category / no date | `approvability_gap_reason` R1 |
| 85 | not other and no cost center | `approvability_gap_reason` R2 |
| 87 | blank description | `approvability_gap_reason` R3 |
| 90 | no items | `approvability_gap_reason` R4 |
| 92 | fall-through (line problems not reported) | `approvability_gap_reason` R5, R6 |
| 98 | invalid category | `_validate_order_allocation` R1 |
| 103 | category other | `_validate_order_allocation` R2 |
| 105 | cost center None | `_validate_order_allocation` R3, R7 |
| 110 / 114 | factory vs department | `_validate_order_allocation` R4, R6 |
| 112 | factory not found (soft-deleted ignored) | `_validate_order_allocation` R4, R5 |
| 116 | department not found | `_validate_order_allocation` R6 |
| 120 | account set (truthy) | `resolve_invoice_account_id` R1, R2 |
| 139–143 | per approver approved? | `reset_approvals` R1, R2 |
| 144 | reset_count > 0 | `reset_approvals` R3, R4 |
| 153 | value None | `_format_scalar_value` R1 |
| 155 | date | `_format_scalar_value` R2 |
| 157–158 | Decimal integral vs not | `_format_scalar_value` R3 |
| 160 | empty text | `_format_scalar_value` R4 |
| 169 | field not in update | `_collect_field_changes` R2, R3 |
| 173 | unchanged value | `_collect_field_changes` R2, R4 |
| 184 | completed and non-empty | `_guard_confirmed_updates` R1, R2 (voided branch R3–R5 not yet in source — BUG-754) |
| 191 | completed | `_guard_item_mutations` R1 (voided branch R2–R3 not yet in source — BUG-754) |
| 198 | quantity missing → 1 | `_prepare_item_dict` R2 |
| 199 | unit_price falsy → 0 | `_prepare_item_dict` R3 |
| 208 | allocation validation | `create_expense_order` R1 |
| 209 | blank description | `create_expense_order` R2 |
| dao 513–518 | last number exists / numeric suffix / fallback 001 | `create_expense_order` R6 |
| 213 | items None | `create_expense_order` R9 |
| 218 | expense_date missing | `create_expense_order` R4 |
| 233 | loop over items (0/1/many) | `create_expense_order` R8, R9 |
| 252 | order not found | `update_expense_order` R1 |
| 255 | exclude_unset / exclude_none | `update_expense_order` R2 |
| 256 | completed guard | `update_expense_order` R3 |
| 258 | category or cost center in payload | `update_expense_order` R4, R5, R6 |
| 259–260 | merge with stored values | `update_expense_order` R4 |
| 266 | details field present and approvals recorded | `update_expense_order` R9, R10 |
| 270 | changes non-empty | `update_expense_order` R7, R8 |
| 276 | updated_by always | `update_expense_order` R14 |
| 283 | order not found | `get_expense_order` R1, R2 |
| dao 132–137 | hub category / account / invoice filters | `list_expense_orders_for_hub` R2, R3 |
| dao 138–141 | date_from / date_to | `list_expense_orders_for_hub` R4 |
| dao 142, 93–111 | status_ids non-empty; stage ids 1/2/3/unknown; no clauses | `list_expense_orders_for_hub` R5 |
| dao 145–148 | invoice_filter | `list_expense_orders_for_hub` R6 |
| dao 150 | exclude_voided | `list_expense_orders_for_hub` R7 |
| dao 153 | exclude_complete | `list_expense_orders_for_hub` R8 |
| dao 156 | search blank | `list_expense_orders_for_hub` R9 |
| dao 160–166 | category label match | `list_expense_orders_for_hub` R9 |
| dao 169–171 | unescaped ILIKE | `list_expense_orders_for_hub` R11 |
| dao 233 | count None → 0 | `count_expense_orders_for_hub` R1 |
| dao 261–285 | complete vs open, invoice None, null sums | `expense_order_hub_stats` R1–R4 |
| dao 245 | recent ordering | `list_expense_orders_recent_for_hub` R2 |
| dao 317–339 | idx < 6 / other_count > 0 | `expense_order_financial_snapshot` R1, R2 |
| dao 351–362 | stage present / missing | `expense_order_financial_snapshot` R3 |
| dao 364–387 | open, joined account, top 5, account_id not None | `expense_order_financial_snapshot` R4–R6 |
| dao 72–80 | due bucket boundaries | `expense_order_financial_snapshot` R8 |
| dao 420 | beyond_scope skipped | `expense_order_financial_snapshot` R8 |
| dao 425–426 | samples < 3; due date None sublabel | `expense_order_financial_snapshot` R9 |
| dao 446–447 | invoice not voided, status in set | `expense_order_financial_snapshot` R10 |
| dao 465 | status not in buckets (unreachable after SQL filter) | `expense_order_financial_snapshot` R10 |
| dao 467–473 | outstanding, samples < 3 | `expense_order_financial_snapshot` R11, R12 |
| 346 | order not found | `delete_expense_order` R1 |
| 348 | completed | `delete_expense_order` R2 |
| 356 | loop over lines | `delete_expense_order` R4 |
| 367 | order not found | `add_item` R1 |
| 368 | completed guard | `add_item` R2 |
| 371 | max line number, default 0 | `add_item` R3 |
| 384 | approvals recorded | `add_item` R7 |
| 393 | item not found | `update_item` R1 |
| 396 | order not found | `update_item` R2 |
| 397 | completed guard | `update_item` R3 |
| 399 | exclude_unset / exclude_none | `update_item` R4 |
| 401 | qty or price in payload | `update_item` R6 |
| 403 | price None → 0 | `update_item` R6 |
| 412 | approvals recorded | `update_item` R9 |
| 420 | item not found | `remove_item` R1 |
| 423 | order not found | `remove_item` R2 |
| 424 | completed guard | `remove_item` R3 |
| 434 | approvals recorded | `remove_item` R7 |
| 439 | order not found | `get_items` R1 |
| 444 | line_subtotal None → 0 | `_recalc_totals` R1 |
| 453 | order not found | `list_approvers` R1 |
| 458 | loop over approvers | `list_approvers` R2, R5 |
| 463 | member exists | `list_approvers` R4 |
| 471 | required_approvals not None | `approval_summary` R2 |
| 473 | approvers > 0 | `approval_summary` R3 |
| 475 | else 0 | `approval_summary` R4 |
| 477 | approved >= required | `approval_summary` R5 |
| 480 | met | `approvals_met` R1 |
| 485 | order not found | `add_approver` R1 |
| 489 | no member / not active | `add_approver` R2 |
| 497 | already approver | `add_approver` R3 |
| 512 | profile missing | `add_approver` R5 |
| 528 | approver not found | `remove_approver` R1 |
| 531 | profile missing | `remove_approver` R3 |
| 547 | not an approver | `set_approval` R1 |
| 552 | order not found | `set_approval` R2 |
| 553 | approve and not approvable | `set_approval` R4 |
| 556 | gap reason None fallback | `set_approval` R4 |
| 558 | withdraw and completed | `set_approval` R5 |
| 564, 568–569 | approved vs withdrawn values / event | `set_approval` R6, R7 |
| 600 | performed_by truthy | `list_events` R3 |
| 609 | template not found | `create_expense_order_from_template` R1 |
| 610 | template inactive | `create_expense_order_from_template` R2 |
| 618 | template category empty → other | `create_expense_order_from_template` R3 |
| 620 | expense_date override or today | `create_expense_order_from_template` R3 |
| 622 | description override or template | `create_expense_order_from_template` R3 |
| 632 | items sorted by line number | `create_expense_order_from_template` R4 |
| 638 | not requires_approval | `create_expense_order_from_template` R5 |
| 641 | auto_approve | `create_expense_order_from_template` R6 |
| 649 | default approver set and not creator | `create_expense_order_from_template` R7 |
| 653 | existing approver (always absent — only the creator exists at this point; unreachable) | `create_expense_order_from_template` R7 |
| 654 | add_approver errors | `create_expense_order_from_template` R8 |

## Gap log
G1 (expense_order_manager.cases.md gap G1) — Contradiction — `update_expense_order` R8 rewritten: changing only `required_approvals` logs an `updated` event (tracked field per `_collect_field_changes` R1) but never resets approvals; no event only for empty/unchanged payloads.
G2 (expense_order_manager.cases.md gap G2) — Intent — `update_expense_order` R2: explicit `description: null` is treated as blank → 400 `Description is required` (R12), not a clear; covered by BUG-753 with today's behavior (200, unchanged). (best-practice default, delegated by reviewer)
G3 (expense_order_manager.cases.md gap G3) — Intent — `update_expense_order` R3: after BUG-753 an explicit `null` counts as a present field, so an all-null payload on a completed or voided order → 400; only an empty payload passes. Today-note added (200, only `updated_by` written). (best-practice default, delegated by reviewer)
G4 (expense_order_manager.cases.md gap G4) — Fact — `expense_order_financial_snapshot` R8: week check precedes month check; worked month-crossing example added (today 2026-03-30 → 04-02 due this week, 04-06 no bucket).
G5 (expense_order_manager.cases.md gap G5) — Fact — `list_expense_orders_for_hub` R11 Today-note extended with backslash behavior (Postgres default LIKE escape): `Acme\Ltd` misses `Acme\Ltd`, finds `AcmeLtd`; trailing `\` matches nothing normal.
G6 (expense_order_manager.cases.md gap G6) — Test mechanics — Externals line names patch targets `app.managers.expense_order_manager.utcnow` and `app.dao.expense_order.utcnow`; note added that column-default timestamps (`created_at`, `assigned_at`) cannot be patched and are asserted by real-clock window or set explicitly.
G7 (expense_order_manager.cases.md gap G7) — Fact — Notes: profile-missing branches are unreachable with real FKs (approver/member `user_id` CASCADE, event `performed_by` SET NULL); fallbacks are defensive, no case required; reachable `list_events` variant described.
G8 (expense_order_manager.cases.md gap G8) — Fact — `delete_expense_order` R4: completed check runs first, so completed + invoiced → R2's 400 `Cannot delete a completed expense order`.
G9 (expense_order_manager.cases.md gap G9) — Intent — `create_expense_order_from_template` R3: whitespace-only description override is used as given and rejected with 400 `Description is required` (matches today; no bug). (best-practice default, delegated by reviewer)
G10 (expense_order_manager.cases.md gap G10) — Intent — `set_approval` R4: incomplete-line detail stated under BUG-758 with today's fallback text; after the fix the `'Order is not ready for approval'` fallback is unreachable defensive code kept in place, no case required. (best-practice default, delegated by reviewer)
