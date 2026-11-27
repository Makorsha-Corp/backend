# Spec — `app/services/expense_order_service.py`

> **Status:** APPROVED (2026-11-21, apply-review; OQ-EOS-1 answered by the owner as OQ-62 → BUG-3069; BUG-3062…3068 decided by Claude under the reviewer's delegation (2026-11-21))
> **Source commit:** e48a092

> **Apply-review 2026-11-21:** OQ-62 applied (`void_expense_order` V6a, BUG-3069). House-rule line H1 (BUG-3062) and precedent matches P1–P3 (BUG-3063…3065) confirmed, and Q1–Q3 (BUG-3066…3068) and Q4–Q5 (intended) decided, by Claude under the reviewer's delegation (2026-11-21). P4 is the existing BUG-1193. Bug IDs are final; the coordinator logs them in `docs/testing/bugs.md`.

> **Review round 2026-11-21 (describe, under the reviewer's delegation of 2026-11-21).** House-rule lines and precedent matches are pre-filled. Every new question that is not a genuinely new money, stock, order-workflow or security question was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. One question is money and order workflow and is not covered by any existing answer: **OQ-EOS-1** (provisional number, to be renumbered when parked in `docs/testing/owner-questions.md`; the same question is open for the work order service as `work_order_manager.spec.md` FU-1 (b), so one owner answer can serve both). Bug IDs are provisional, from block BUG-3062 … 3081; nothing is logged in `docs/testing/bugs.md` yet.
>
> **Already decided elsewhere, cited, not asked again:** every manager rule and bug of `tests/unit/managers/expense_order_manager.spec.md` (row locks BUG-741…744, voided orders read-only BUG-754, approvers frozen on completed orders BUG-756, "no approvers" = 1 required BUG-755, nulls clear fields BUG-753, delete refused with a linked invoice BUG-742, delete leaves an audit row and needs the deleter BUG-1193 — the service half of that fix is stated here, no new ID); the invoice manager's rules (`account_invoice_manager.spec.md`): amount = sum of lines and no client amount on create (BUG-627), confirm needs a line (BUG-628), account checks on a draft's account change (BUG-629), completed-order freeze O1 / F1–F7 (BUG-2730), delete of a draft with payment history refused (BUG-639); the invoice page can't finalize an expense order's invoice (OQ-60 → BUG-2969) and voiding it there unlinks the order (BUG-2966, `account_invoice_service.spec.md`); notification texts and recipients (`approval_notification_service.spec.md`, N1–N12, routed to `docs/future/notifications.md`); hub figures (BUG-2714…2719, OQ-42/43/44, expense order DAO spec).
>
> **Production:** not touched by this module. **Projects:** not touched.
>
> **Verified by running** (my own script `v1_eos.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2desc\expense_order\`, one outer transaction on `marker_test`, session as the unit `db` fixture, rolled back, nothing persisted): with two approvers, after one approves and the other (pending) is removed, the summary is `(1, 1, True)` but no invoice exists, and "complete" answers 400 `No invoice linked — set an account so a draft invoice can be created, then try again` although the order has an account; an order with `required_approvals = 0` gets its draft at once, voiding it unlinks it, then `create_invoice_for_expense_order` on the **voided** order succeeds and "complete" then completes the voided order with a **confirmed 50.00** payable invoice; voiding an order whose invoice was confirmed on the invoice page leaves that invoice `confirmed`, 20.00, with the order's `invoice_id` NULL; void note `"   "` is stored as typed; voiding an approved order with no invoice keeps its approval.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| H1 | Complete, void and "create invoice" check the order and then act without locking it | bug — BUG-3062 | house rule HR-10 (confirmed under the delegation) |
| P1 | The auto-drafted invoice's date is the server's local date | bug — BUG-3063 | precedent BUG-2716 / BUG-1334 (confirmed under the delegation) |
| P2 | A blank (spaces only) void reason is accepted | bug — BUG-3064 | precedent BUG-605 / 626 / 2918 (confirmed under the delegation) |
| P3 | A voided order can get a new invoice and then be completed | bug — BUG-3065 | precedent BUG-754 (confirmed under the delegation) |
| P4 | Delete does not pass who deleted the order | bug — BUG-1193 (existing) | owner 2026-11-01 |
| Q1 | Removing a pending approver can complete the approvals, but the draft invoice is not made | bug — BUG-3066 | delegation |
| Q2 | Voiding clears approvals only when the order had an invoice | bug — BUG-3067 | delegation |
| Q3 | (after BUG-753) clearing the order's account leaves the draft invoice on the old account | bug — BUG-3068 | delegation |
| Q4 | Withdrawing an approval (or a header/line edit that wipes approvals) leaves the draft invoice in place | intended | delegation |
| Q5 | "Invoice not auto-created: no account" is logged again on every edit | intended | delegation |
| OQ-EOS-1 | **OWNER** — voiding an order whose invoice was already finalized leaves a payable bill with no order | bug — BUG-3069 | owner (OQ-62, 2026-11-21) |

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-10** `complete_expense_order` C1, `void_expense_order` V1, `create_invoice_for_expense_order` I1 — each reads the order, checks its state (completed, voided, approvals met, invoice linked) and then confirms, deletes or creates an invoice, with a plain read. The manager methods that lock the order (BUG-741…744) are not on these paths. A race does real harm: a line added while "complete" runs changes the order after its invoice was finalized (money); two "create invoice" clicks make two draft invoices, one orphaned (duplicate side effect); a completion and a void at the same time give a completed **and** voided order. Intended: each of the three reads the order row `SELECT … FOR UPDATE` before its first check; the loser sees the new state and gets the normal error (for "complete", the early return of an already-completed order, C2). 🐞 BUG-3062
**Answer:** bug — per HR-10 (house rule)
**Resolution:** BUG-3062, pattern `hr-10-unlocked-state-transition`, confirmed under the reviewer's delegation (2026-11-21). Rules: `complete_expense_order` C1, `void_expense_order` V1, `create_invoice_for_expense_order` I1.

Checked and **not** violated: **HR-1/2/3** — no names stored (the void reason is P2, by precedent). **HR-4** — orders have no soft delete; the invoice is read by id and workspace (BaseDAO scope). **HR-5/6/7/8** — paging, order and search are the manager's (BUG-745…748); the endpoint enforces `1 ≤ limit ≤ 100`; `has_more` is computed from the true total. **HR-9** — `updated_by` is written by completion only, which always changes fields. **HR-11–14** — no external system or batch. **HR-15** — the service does no arithmetic on money (fallback `0` / `1` only, S-rules). **HR-16** — every read takes the caller's `workspace_id`; an invoice id pointing into another workspace (legacy data, BUG-751) is not found and treated as "no invoice" (sync) or 400 `Linked invoice not found` (complete), and its id is never shown.

**Permission checks:** none in the service. Every endpoint only needs an active member of the workspace: any member can complete, void, delete, create the invoice, add or remove any approver (also one who already approved). Noted for `docs/future/permissions.md`, not a question here.

### Precedent matches — confirm all with ok

### P1. The auto-drafted invoice's date is the server's local date — 🐞 BUG-3063 (precedent)
**Background:** expense numbers' year (BUG-2710) and the default expense date (BUG-2716) were ruled to come from the UTC clock (`utcnow()`, BUG-1334), not the machine's local clock.
**What happens today:** the draft invoice made for an order gets `invoice_date = date.today()`, the local date of the machine running the API.
**Example:** a server set to Dhaka time drafts an invoice at 01:30 on 2 March local time; `utcnow()` is still 1 March, but the invoice is dated 2 March.
**Rules affected:** `_create_draft_invoice` D3
**Answer:** bug — per BUG-2716 / BUG-1334 precedent: `invoice_date = utcnow().date()` (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3063, pattern `local-clock-instead-of-utc`. Rule: `_create_draft_invoice` D3.

### P2. A blank void reason is accepted — 🐞 BUG-3064 (precedent)
**Background:** `ExpenseOrderVoidRequest.void_note` is a plain `str`: no minimum length, not trimmed. The reason is stored on the order and written into the `eo_voided` log entry.
**What happens today:** `""` or `"   "` is accepted and stored as typed (verified); the log reads `… voided. Reason:    `.
**Example:** a user voids EXP-2026-014 and leaves the reason empty; later nobody can tell why it was voided.
**Rules affected:** `void_expense_order` V10
**Answer:** bug — per BUG-605 / BUG-626 / BUG-2918 precedent: `void_note` is trimmed and must not be blank (422 at the schema), nothing written (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3064, pattern `blank-name-accepted`; fix in `app/schemas/expense_order.py` (`ExpenseOrderVoidRequest`). Rule: `void_expense_order` V10.

### P3. A voided order can get a new invoice and then be completed — 🐞 BUG-3065 (precedent)
**Background:** BUG-754 made voided orders read-only in the manager (every edit, line change, approver add and approval → 400 `Expense order is voided`). Two service paths do not go through those manager guards: "create invoice" and "complete". Voiding unlinks the order's invoice. An order made from a template that waives approval has `required_approvals = 0`, so its approvals stay "met" after the void.
**What happens today:** on such a voided order, "create invoice" makes a new draft payable invoice, and "complete" then confirms it and marks the voided order complete (verified: a voided order completed with a confirmed 50.00 invoice).
**Example:** "Monthly rent" order EXP-2026-020 (approval waived by its template, 25,000 taka) is voided as a duplicate. Someone clicks "Create invoice", then "Complete": accounting now has a finalized 25,000 taka bill for the duplicate, and the order shows both voided and completed.
**Rules affected:** `create_invoice_for_expense_order` I3, `complete_expense_order` C3
**Answer:** bug — per BUG-754 precedent: both refuse a voided order with 400 `Expense order is voided`, checked right after the order is read (after the lock of H1), nothing written (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3065, pattern `missing-state-guard`. Rules: `create_invoice_for_expense_order` I3, `complete_expense_order` C3.

### P4. Delete does not pass who deleted the order — 🐞 BUG-1193 (existing, owner 2026-11-01)
**Background:** BUG-1193 (owner) requires a deleted expense order to leave one `workspace_audit_logs` row naming the deleter; its fix "also touches `ExpenseOrderService.delete_expense_order` and `DELETE /expense-orders/{id}/`" (manager spec `delete_expense_order` R5c).
**What happens today:** the service takes no user and calls the manager without one; the endpoint has no current user.
**Example:** Rahim deletes EXP-2026-041; nothing records that it was Rahim.
**Rules affected:** `delete_expense_order` X1, X2
**Answer:** bug — per BUG-1193 (owner 2026-11-01): the service takes `user_id` and passes it to the manager (precedent — confirmed: ok)
**Resolution:** existing BUG-1193, no new ID. Rule: `delete_expense_order` X2.

### New questions

### Q1. Removing a pending approver can complete the approvals, but the draft invoice is not made — 🐞 BUG-3066
**Background:** an order's draft payable invoice is made automatically the moment its approvals are met (on approve, on any edit). Without an explicit requirement, "met" means every assigned approver approved, so removing the one approver who has not approved makes the approvals met. "Complete" needs a linked invoice.
**What happens today:** removing an approver does not run the invoice step. The approvals show "1 of 1 — met", no invoice exists, and "Complete" answers 400 `No invoice linked — set an account so a draft invoice can be created, then try again` although the order has an account (verified). The invoice appears only after some unrelated edit.
**Example:** EXP-2026-031 (rent, 18,000 taka, account "Karim Properties") has approvers Abid (approved) and Nadia (pending). Nadia leaves; the manager removes her as approver. The order now reads fully approved, but clicking "Complete" says to set an account, which is already set.
**Rules affected:** `remove_approver` A6
**Answer:** bug — removing an approver runs the same invoice step as approving (`_sync_or_create_invoice`): when approvals become met, an order with an account and lines gets its draft invoice and the "draft" notice (decided by Claude under the reviewer's delegation, 2026-11-21: the workflow is already decided — the draft appears when approvals are met — this only closes a path that skips it)
**Resolution:** BUG-3066, pattern `missing-follow-up-sync`. Rule: `remove_approver` A7.

### Q2. Voiding clears approvals only when the order had an invoice — 🐞 BUG-3067
**Background:** voiding an order that has a linked invoice clears every approval (`approvals_reset`, "Cleared approvals — expense order voided"). Voiding one without an invoice leaves the approvals as they were.
**What happens today:** two voided orders look different: one shows "0 of 2 approved", the other "2 of 2 approved" (verified: approval kept). A voided order is read-only either way (BUG-754).
**Example:** EXP-2026-050 and EXP-2026-051 were both approved by two people and voided the same day; only 050 had a draft invoice. 050 shows no approvals, 051 still shows both.
**Rules affected:** `void_expense_order` V7, V8
**Answer:** bug — every void clears the approvals the same way (reason `Cleared approvals — expense order voided`), invoice or not; who approved stays in the activity log (decided by Claude under the reviewer's delegation, 2026-11-21: consistency; no money moves and a voided order can do nothing either way)
**Resolution:** BUG-3067, pattern `inconsistent-sibling-guard`. Rules: `void_expense_order` V7, V8.

### Q3. Clearing the order's account leaves the draft invoice on the old account — 🐞 BUG-3068
**Background:** while a draft invoice is linked, every edit copies the order's account, due date and description onto it. An account *change* is copied; a *cleared* account (`null`) is skipped because there is no account to copy, and an invoice must have one. Today `null` is ignored by the manager, so this cannot happen yet; BUG-753 makes `null` clear the field.
**What happens today (after BUG-753):** the order shows no account; its draft invoice is still payable to the old account, and "Complete" would finalize it to that account.
**Example:** EXP-2026-060 (electricity, 7,500 taka) is drafted to "DESCO". A user clears the account to choose later. Completing then finalizes a 7,500 taka bill to DESCO, though the order names no supplier.
**Rules affected:** `_resync_draft_invoice` R5a
**Answer:** bug — while an invoice that is not voided is linked, clearing the order's account is refused with 400 `An invoice is linked to this order — choose another account instead of clearing it`, nothing written; changing to another account works as today (decided by Claude under the reviewer's delegation, 2026-11-21: keeps "the invoice's account is the order's account", which the sync already enforces for changes; the nearest owner answer, OQ-56, refuses account edits on an invoiced work order outright, and this is the milder form)
**Resolution:** BUG-3068, pattern `stale-cross-field-value`. Rule: `_resync_draft_invoice` R5a (the check runs in the order edit, before anything is applied; reachable once BUG-753 is fixed).

### Q4. Withdrawing an approval leaves the draft invoice in place — ✅ intended
**Background:** the draft invoice is made when approvals are met. Later, an approver may withdraw, or an edit may wipe the approvals.
**What happens today:** the draft stays linked and keeps following the order's lines; "Complete" still requires approvals met before it finalizes the draft.
**Example:** EXP-2026-070's draft (12,000 taka) exists; Abid withdraws his approval. The draft stays; "Complete" answers 400 `Required approvals are not met` until he approves again.
**Rules affected:** `unapprove_as_me` A9, `update_expense_order` U3, `add_item` L2
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-21: a draft is not a bill — drafts do not count as open balances (BUG-634) and can't be finalized from the invoice page (BUG-2969); deleting and re-making it on every approval change would only churn invoice ids)
**Resolution:** no bug. Rules unchanged: `unapprove_as_me` A9 ✅, `update_expense_order` U3 ✅, `add_item` L2 ✅.

### Q5. "Invoice not auto-created: no account" is logged again on every edit — ✅ intended
**Background:** when approvals are met but the order has no account, the invoice step logs `invoice_autocreate_skipped` instead of drafting.
**What happens today:** each later edit, approval or template run logs it again while the order stays without an account (most visible with waived approvals, where edits do not un-meet them).
**Example:** a waived-approval order with no account gets three line edits; its log shows "Approvals met but no account set …" three times.
**Rules affected:** `_sync_or_create_invoice` Y5
**Answer:** intended (decided by Claude under the reviewer's delegation, 2026-11-21: each entry is a reminder tied to a real action; no money or state changes)
**Resolution:** no bug. Rule unchanged: `_sync_or_create_invoice` Y5 ✅.

### OQ-EOS-1. Voiding an order whose invoice was already finalized leaves a payable bill with no order — OWNER (money, order workflow) — 🐞 BUG-3069
**Background:** an expense order's invoice is normally finalized only when the order is completed, and a completed order cannot be voided. Before the OQ-60 fix (BUG-2969) an accountant could also finalize it early on the invoice page, so existing data can hold not-completed orders with a finalized invoice. Voiding the order deletes a **draft** invoice; any other invoice is just unlinked.
**What happens today:** the order is voided and its `invoice_id` cleared; the finalized invoice stays finalized and payable, now tied to no order (verified: invoice still `confirmed`, 20.00). Payments already made stay on it.
**Example:** EXP-2026-080, office repair 40,000 taka, had its invoice finalized early on the invoice page. The order is then voided because the repair was cancelled. Accounting still shows a 40,000 taka bill due to the contractor, and nothing on it says the order was cancelled.
**Rules affected:** `void_expense_order` V6
**Suggested answer:** (a) refuse the void.
**Options for the owner:**
- **(a) Refuse the void — recommended.** Voiding the order is stopped with the message "This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order." Nothing changes until someone deals with the bill on purpose. In the example, the 40,000 taka bill stays exactly as it is; the accountant voids it on the invoice page (which cancels any payment recorded on it and frees the order), and then the order can be voided. Nobody can lose track of a real bill by cancelling the order, and the person who voids money is the one who sees it.
- **(b) Voiding the order also voids the bill.** One click cancels both: the 40,000 taka bill becomes voided and any payment recorded on it is cancelled with it (say 10,000 taka paid — that payment record is cancelled too, though the money really left the bank and must be sorted out by hand). Quick, but a person cancelling an order can silently cancel a bill and its payments without opening accounting.
- **(c) Keep today's behaviour.** The order is cancelled and the 40,000 taka bill stays payable with no order behind it. Someone must notice it in accounting and void it separately; until then it counts as money owed.
**Rules affected if answered:** `void_expense_order` V6 (and the same answer can be applied to `void_work_order`, `work_order_manager.spec.md` FU-1 (b)).
**Answer:** owner, 2026-11-21 (OQ-62): option (a) — refuse the void with "This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order."
**Resolution:** BUG-3069, pattern `linked-record-not-updated`. V6 is split: an invoice already voided, or not found in this workspace, stays untouched as today (V6); a `confirmed` invoice refuses the whole void with 400 (V6a). Once the invoice is voided on the invoice page, BUG-2966 unlinks the order and the void then runs with no invoice. Rules: `void_expense_order` V6, V6a.

## Overview
`ExpenseOrderService` is the transaction layer for expense orders (direct costs such as rent or utilities, no stock). Around `ExpenseOrderManager` it commits or rolls back, and it adds what spans modules: the order's **payable invoice** (drafted automatically once approvals are met and kept in step with the order while it is a draft; finalized when the order is completed; deleted when the order is voided), **completion** and **voiding** (implemented here, not in the manager), and **approval notifications** (`approval_notification_service`). Callers: the endpoints in `app/api/v1/endpoints/expense_orders.py` only. Invariants it is meant to protect: a completed order has a confirmed invoice that matches its lines; a draft invoice mirrors the order's lines, account, due date and description; a voided order has no draft invoice and can do nothing more.

**Callables:** 27 specified · 1 not specified
**Externals to mock:** `utcnow` — patch `app.services.expense_order_service.utcnow` (`completed_at`, `voided_at`, `items_updated_at`), plus the manager's targets listed in its spec when a test depends on them. `date.today()` (invoice date, D3) reads the system clock and is not mocked. Notifications are **not** mocked: they are `notifications` rows written in the same transaction (`approval_notification_service.spec.md` Overview).
**Integration-only behavior:** none.

### Transaction contract
Every write method here follows **TC1–TC6** of `tests/unit/services/base_service.spec.md` (repeated from `department_service.spec.md`, unchanged): manager call(s), invoice / notification steps, `_commit_transaction`, `db.refresh` of the returned row, all in one `try`; any exception rolls the session back and is re-raised as the same object. Departures, stated in the callable: `delete_expense_order`, `remove_approver` return `None` (no refresh); `remove_item` returns the deleted line without a refresh (TC2 does not apply; its attributes stay readable); `complete_expense_order` on an already-completed order returns it without commit or rollback (C2). Reads (`get_expense_order`, `list_*`, `get_*`, `approval_summary_for`, hub stats) follow TC6. Because notifications and invoice steps run inside the `try`, an error there (e.g. 403 `Invoices are not allowed for this account` from the invoice manager) undoes the whole order change (TC3).

**Facts for the test designer**
- Import: `from app.services.expense_order_service import ExpenseOrderService, expense_order_service`. `ExpenseOrderService()` takes no arguments; `.manager` is the `expense_order_manager` singleton, `.account_invoice_manager` the `account_invoice_manager` singleton.
- The invoice is linked through `expense_orders.invoice_id` (FK, `ON DELETE SET NULL`). The invoice carries `order_type = "expense_order"`, `order_id = <order id>`, `invoice_type = "payable"`.
- Invoice events are `invoice_events` rows; order events are `expense_order_events` rows (`event_type`, `description`, `metadata_json`, `performed_by`).
- Notification rows: `notifications` (`recipient_user_id`, `notification_type`, `entity_type = "expense_order"`, `entity_id`, `source_type`, `source_id`, `preview`). Recipients must be **active** members, so approvers and creators need `workspace_members` rows with `status = "active"`.
- An account that can be invoiced: `Account(is_active=True, is_deleted=False, allow_invoices=True)` of the same workspace.
- A "completed" order has `completed_at` set; "voided" has `voided = True`.

**Notes for the test designer**
- (G2) The three notification functions are imported by name into this module: patch `app.services.expense_order_service.notify_invoice_action`, `…notify_section_confirm_needed`, `…handle_add_approver` (e.g. with `side_effect=RuntimeError` for TC3). Without a patch they write real `notifications` rows.
- Session and commits as in `base_service.spec.md` Notes: under the `db` fixture `commit()` releases a savepoint; assert "committed" with a test-level `db.rollback()` and a re-select.
- To make approvals met without approving: `update_expense_order(..., ExpenseOrderUpdate(required_approvals=0))` (an order created by `create_expense_order` has its creator as the only approver).
- An invoice confirmed "on the invoice page" (OQ-EOS-1, legacy) is made by calling `account_invoice_manager.confirm_invoice` directly on the order's draft.
- Row-lock cases (H1): capture SQL with a `before_cursor_execute` listener and look for `FOR UPDATE` on `expense_orders` before the first state check, as the manager tests do.

## Not specified
- `ExpenseOrderService.__init__` — wires the two managers, no logic.

---

## `ExpenseOrderService.create_expense_order(db, eo_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/`)

**Purpose:** Create an order and save it.

**Returns:** the new order, committed and refreshed.

**Rules:**
- **E1.** The order is created per `ExpenseOrderManager.create_expense_order` (all its rules and errors, including the creator added as approver) and committed (TC1–TC4).
- **E2.** No invoice step runs: a new plain order has no lines, so no invoice is drafted, even when approvals would count as met.
- **E3.** No notification is written.

**Errors:** the manager's, unchanged (TC3). **Side effects:** as the manager; commit.

---

## `ExpenseOrderService.update_expense_order(db, eo_id, eo_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /expense-orders/{id}/`)

**Purpose:** Edit the order's details, tell the creator when approvals were wiped, keep the invoice in step, save.

**Returns:** the order, committed and refreshed.

**Rules:**
- **U1.** The edit follows `ExpenseOrderManager.update_expense_order` (all its rules and errors; approvals are wiped only when a detail actually changes, BUG-740).
- **U2.** When the manager wiped approvals (`_approvals_reset` true), one `section_confirm` notification goes to the order's creator (if an active member, also when the creator made the edit) with preview `Approvals were reset — order details changed; re-approve when ready`, per `notify_section_confirm_needed` R2–R4. No notice goes to the approvers. When approvals were not wiped, no notification.
- **U3.** Then the invoice step runs per `_sync_or_create_invoice` (Y1–Y7): a linked draft is brought in step; with no invoice, one is drafted when approvals are met (e.g. `required_approvals` lowered to the number already approved, or to 0). A draft stays linked when the edit wipes approvals (Q4, intended).
- **U4.** Any error of U2 or U3 (e.g. the invoice manager refusing — the inactive / `allow_invoices` examples are [BUG-629] per `_resync_draft_invoice` R4b; a deleted account refuses today — the order's new account: 400 `Cannot assign invoice to inactive account`, 403 `Invoices are not allowed for this account`) rolls back the order edit too (TC3).

**Errors:** the manager's; those of `_resync_draft_invoice` / `_create_draft_invoice`. **Side effects:** order row, events, approver rows; 0–1 `section_confirm` notification; invoice changes per Y; commit.

---

## `ExpenseOrderService.get_expense_order(db, eo_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /expense-orders/{id}/`)

**Rules:**
- **G1.** Returns the order per `ExpenseOrderManager.get_expense_order` (voided and completed included; another workspace's id → 404 `Expense order with ID <id> not found`). TC6.

---

## `ExpenseOrderService.list_expense_orders(db, workspace_id, expense_category=None, account_id=None, invoice_id=None, skip=0, limit=100, **hub_filters)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /expense-orders/`)

**Rules:**
- **L-1.** Returns exactly what `list_expense_orders_page` returns for the same workspace, `skip`, `limit` and filters (the three named filters plus any of `date_from`, `date_to`, `status_ids`, `invoice_filter`, `search`, `exclude_complete`, `exclude_voided` passed by keyword). Its own default `limit` is 100 (the page's is 50); the endpoint always passes `limit` (default 50, `1 ≤ limit ≤ 100`, `skip ≥ 0`).
- **L-2.** An unknown keyword filter raises `TypeError` (not reachable from the endpoint, which passes exactly the ten names).

---

## `ExpenseOrderService._hub_filter_kwargs(*, expense_category=None, account_id=None, invoice_id=None, date_from=None, date_to=None, status_ids=None, invoice_filter=None, search=None, exclude_complete=False, exclude_voided=False)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `list_expense_orders_page`, `get_expense_order_hub_stats`)

**Returns:** a dict with exactly the ten keys above.

**Rules:**
- **K1.** Every value is passed through unchanged, except `invoice_filter`.
- **K2.** `invoice_filter` `None`, `""` or `"all"` → `None` (no invoice filter). Any other value (e.g. `"linked"`, `"All"`, `" all"`) is passed as given; what the manager does with it is the manager's rule (`list_expense_orders_for_hub`).

---

## `ExpenseOrderService.list_expense_orders_page(db, workspace_id, *, skip=0, limit=50, ...filters)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `list_expense_orders`)

**Returns:** `ExpenseOrderListResponse(items, total, skip, limit, has_more)`.

**Rules:**
- **P-1.** Filters are normalised per `_hub_filter_kwargs`; `total` = `ExpenseOrderManager.count_expense_orders_for_hub` and `items` = `list_expense_orders_for_hub(skip, limit)` with those same filters (filtering, order, search escaping and workspace scope are the manager's rules).
- **P-2.** `skip` and `limit` are echoed as given.
- **P-3.** `has_more` = `skip + len(items) < total`. Boundaries: 120 matching, skip 0, limit 50 → true; skip 100, limit 50 (20 items) → false; skip beyond the total (0 items) → false; no match → `total = 0`, `items = []`, false.
- **P-4.** TC6: no commit, no rollback.

---

## `ExpenseOrderService.get_expense_order_hub_stats(db, workspace_id, *, ...filters)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (`GET /expense-orders/stats/`)

**Returns:** `ExpenseOrderHubStatsResponse`.

**Rules:**
- **H-1.** Filters are normalised per `_hub_filter_kwargs` and the same filters feed all three manager reads.
- **H-2.** `total_count`, `total_value`, `open_count`, `open_value`, `not_invoiced_count` are the five values of `ExpenseOrderManager.expense_order_hub_stats`, in that order (what they count is the manager's / DAO's rule, including BUG-2717).
- **H-3.** `recent_orders` = at most 10 orders from `list_expense_orders_recent_for_hub(limit=10)`, in its order (BUG-746), each mapped by `order_hub_stats_helpers.expense_order_to_recent_summary`.
- **H-3a.** Each recent summary is an `OrderHubRecentSummary` (`app/schemas/order_hub.py`) with exactly: `id` = order id, `order_number` = `expense_number`, `status_id = 0`, `status_name = None`, `created_at`, `updated_at`, `account_id`, `invoice_id`, `total_amount`, `expense_category`, `expense_date`, `due_date` from the order, `source_location_type = None`, `destination_location_type = None`. The mapper is `expense_order_to_recent_summary` in `app/services/order_hub_stats_helpers.py`, imported **inside** the method (patch it at `app.services.order_hub_stats_helpers.expense_order_to_recent_summary`). The response class is `app.schemas.expense_order.ExpenseOrderHubStatsResponse`. (G4)
- **H-4.** `financial_snapshot` copies the manager's `expense_order_financial_snapshot` without changing any number or order: `category_breakdown` and `stage_pipeline` as financial buckets; `open_by_account` as account buckets; `due_timeline` buckets with `key`, `label`, `count`, `total_value` and their `samples`; `unpaid_pipeline` buckets with `key`, `label`, `count`, `outstanding_value` and their `samples` (BUG-2718, BUG-2719 are the DAO's). An empty list stays empty.
- **H-4a.** Bucket fields (`app/schemas/order_hub.py`): category / stage bucket `key`, `label`, `count`, `total_value`; `open_by_account` bucket `account_id`, `account_name` (may be `None`), `count`, `total_value`; due-timeline bucket `key`, `label`, `count`, `total_value`, `samples`; unpaid-pipeline bucket `key`, `label`, `count`, `outstanding_value`, `samples`; sample `id`, `order_number`, `total_value` (may be `None`), `sublabel` (may be `None`). `account_name` is copied too. A manager row carrying a key the schema lacks, or missing a required one, fails with `pydantic.ValidationError` (TC6: no rollback). (G4)
- **H-5.** TC6.

---

## `ExpenseOrderService.delete_expense_order(db, eo_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /expense-orders/{id}/`)

**Returns:** `None`.

**Rules:**
- **X1.** The order is deleted per `ExpenseOrderManager.delete_expense_order` (404 missing / other workspace; 400 completed; 400 `Void the expense order instead` when an invoice is linked, BUG-742; audit row, BUG-1193) and committed; refusals roll back (TC3).
- **X2.** [BUG-1193] The service takes the deleter as `user_id` and passes it to the manager, so the audit row names the person who deleted the order; the endpoint passes the current user. *(Today: the service has no `user_id` parameter and calls the manager without one; the endpoint has no current user.)*
- **X3.** No invoice step and no notification.

**Errors:** the manager's, unchanged. **Side effects:** rows deleted (manager); commit.

---

## `ExpenseOrderService.complete_expense_order(db, eo_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/{id}/complete/`)

**Purpose:** Finalize the order's invoice and mark the order complete.

**Returns:** the order, committed and refreshed (or unchanged, C2).

**Rules:** checks run in the order C1, C3, C2, C4, C5, C6, C7 (G10).
- **C1.** [BUG-3062] The order is read per `get_expense_order` (404 missing / other workspace) with a row lock (`FOR UPDATE`) before any check. *(Today: plain read, no lock.)*
- **C1a.** [BUG-3062] The lock is a plain `FOR UPDATE` on the one-table read of `expense_orders` (`SELECT … FROM expense_orders WHERE id = … AND workspace_id = … LIMIT 1 FOR UPDATE`; the read joins nothing and the model has no joined eager load, so `OF expense_orders` is not required — the BUG-029 / BUG-643 rule asks for `FOR UPDATE OF <table>` only when the read joins). `FOR UPDATE OF expense_orders` is equally correct and passes; `NOWAIT` and `SKIP LOCKED` are not allowed (the loser waits, then sees the new state). (G1)
- **C2.** Already completed (`completed_at` set) → returned as it is, 200: no check, no write, no event, no notification, and neither commit nor rollback (changes pending in the session stay pending). A second "complete" is therefore harmless.
- **C3.** [BUG-3065] Voided → 400 `Expense order is voided`, nothing written. Checked right after the locked read, **before** C2: an order that is both voided and completed (only reachable through today's BUG-3065 path or older data) gets this 400, not C2's unchanged 200 (G10, decided by Claude under the reviewer's delegation (2026-11-21)). *(Today: not checked; a voided order with an invoice and met approvals is completed — verified.)*
- **C4.** Approvals not met (`approvals_met`, BUG-755: no approvers and no explicit requirement = not met) → 400 `Required approvals are not met`, nothing written.
- **C5.** No invoice linked → 400 `No invoice linked — set an account so a draft invoice can be created, then try again`, nothing written.
- **C6.** The linked invoice is not found in this workspace (another workspace's invoice, legacy data per BUG-751) → 400 `Linked invoice not found`, nothing written; no id is shown.
- **C7.** The linked invoice is `voided` → 400 `Linked invoice was voided — cannot complete this order`, nothing written. (After BUG-2966 a void on the invoice page unlinks the order, so this is reached only by older data.)
- **C8.** The invoice is `draft` → it is confirmed per `AccountInvoiceManager.confirm_invoice` (amount = sum of its lines, status `confirmed`, event `confirmed`; a draft with no lines → 400 `Add at least one line item before confirming`, BUG-628, and nothing is saved), then one `invoice_action` notification per recipient of `notify_invoice_action` with action `confirmed` (preview `confirmed|Invoice confirmed on EXP-<order id> — order locked`; pending approvers, every approver when `required > 0`, and the creator; active members only).
- **C9.** The invoice is already `confirmed` (legacy: confirmed on the invoice page before BUG-2969) → it is left as it is and no invoice notification is written; the order is still completed (C10).
- **C10.** The order gets `completed_at = utcnow()`, `completed_by = user_id`, `updated_by = user_id`, and one event `order_completed`, description `Invoice confirmed and expense order marked complete`, `performed_by = user_id`, no metadata (same text in the C9 case); committed. From then on its invoice is frozen (`account_invoice_manager.spec.md` O1, F2).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| C1 | HTTPException 404 | `Expense order with ID <id> not found` |
| C3 | HTTPException 400 | `Expense order is voided` — BUG-3065 |
| C4 | HTTPException 400 | `Required approvals are not met` |
| C5 | HTTPException 400 | `No invoice linked — set an account so a draft invoice can be created, then try again` |
| C6 | HTTPException 400 | `Linked invoice not found` |
| C7 | HTTPException 400 | `Linked invoice was voided — cannot complete this order` |
| C8 | from `confirm_invoice` | e.g. 400 `Add at least one line item before confirming` |

**Side effects:** invoice confirmed (C8); order row; one event; notifications (C8); commit.

---

## `ExpenseOrderService.void_expense_order(db, eo_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/{id}/void/`, body `ExpenseOrderVoidRequest`)

**Purpose:** Cancel an order that is not completed and remove its draft invoice.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| void_note | str | required by the schema; [BUG-3064] trimmed and not blank (422) *(today: any string, `""` and spaces included)* |

**Returns:** the order, committed and refreshed.

**Rules (checks in this order):**
- **V1.** [BUG-3062] Order read per `get_expense_order` (404) with a row lock (`FOR UPDATE`) before the checks. *(Today: no lock.)*
- **V1a.** [BUG-3062] The lock is a plain `FOR UPDATE` on the one-table read of `expense_orders` (`SELECT … FROM expense_orders WHERE id = … AND workspace_id = … LIMIT 1 FOR UPDATE`; the read joins nothing and the model has no joined eager load, so `OF expense_orders` is not required — the BUG-029 / BUG-643 rule asks for `FOR UPDATE OF <table>` only when the read joins). `FOR UPDATE OF expense_orders` is equally correct and passes; `NOWAIT` and `SKIP LOCKED` are not allowed (the loser waits, then sees the new state). (G1)
- **V2.** Already voided → 400 `Expense order is already voided`, nothing written.
- **V3.** Completed → 400 `Cannot void a completed expense order`, nothing written.
- **V4.** With a linked invoice: the invoice is read in this workspace.
- **V5.** That invoice is a `draft` → deleted per `AccountInvoiceManager.delete_invoice` (its lines and events go with it; a draft with payment history → 400 `Invoice has payment history — confirm and void it instead`, BUG-639, and the whole void is undone).
- **V6.** That invoice is already `voided`, or is not found in this workspace → it is not touched; the order is still voided and unlinked (V7).
- **V6a.** [BUG-3069] That invoice is `confirmed` (finalized on the invoice page before BUG-2969) → 400 `This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order.`; nothing written: the order stays not voided and keeps its `invoice_id` and approvals, the invoice and its payments are unchanged, no event. Checked after V3, before anything is deleted or cleared. *(Today: the order is voided and unlinked, and the invoice stays `confirmed` and payable with no order — verified.)*
- **V7.** [BUG-3070] With a linked invoice that V5 deleted or V6 left alone: approvals cleared per `reset_approvals` with reason `Cleared approvals — expense order voided` (one `approvals_reset` event when at least one was approved); `invoice_id` set to `NULL`; event `invoice_voided`, description `Invoice unlinked — expense order <expense_number> voided`, metadata `{"invoice_id": <old id>}`, `performed_by = user_id`. *(Today: when V5 deleted the draft, the id is read after the delete's flush has nulled `invoice_id`, so the metadata is `{"invoice_id": null}`; with an invoice V6 left alone the old id is kept.)*
- **V8.** [BUG-3067] Without a linked invoice, approvals are cleared the same way as V7 (same reason and event); no `invoice_voided` event. *(Today: approvals are kept — verified.)*
- **V9.** The order gets `voided = True`, `void_note` as given, `voided_at = utcnow()`, `voided_by = user_id`; event `eo_voided`, description `Expense order <expense_number> voided. Reason: <void_note>`, metadata `{"void_note": <void_note>}`, `performed_by = user_id`, logged after V7's events; committed.
- **V10.** [BUG-3064] A blank or spaces-only `void_note` is rejected with 422 before the service runs; a valid one is stored trimmed. *(Today: stored as typed.)*
- **V11.** No notification is written (approvers and creator are not told).
- **V12.** `updated_by` is not written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| V1 | HTTPException 404 | `Expense order with ID <id> not found` |
| V2 | HTTPException 400 | `Expense order is already voided` |
| V3 | HTTPException 400 | `Cannot void a completed expense order` |
| V5 | from `delete_invoice` | e.g. 400 `Invoice has payment history — confirm and void it instead` |
| V6a | HTTPException 400 | `This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order.` — BUG-3069 |
| V10 | 422 (schema) | — BUG-3064 |

**Side effects:** invoice deleted (V5); approver rows and events; order row; commit.

---

## `ExpenseOrderService.add_item(db, eo_id, item_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/{id}/items/`)

**Returns:** the new line, committed and refreshed.

**Rules:**
- **L1.** The line is added per `ExpenseOrderManager.add_item` (404 / 400 completed / 400 voided, totals, `item_added` event, approvals wiped when any were recorded).
- **L2.** The order's `items_updated_at` = `utcnow()`. Then the invoice step runs per `_sync_or_create_invoice`: a linked draft gets the new line set; with no invoice, a draft is made only if approvals are still met (in practice only with `required_approvals = 0`, since the edit wipes recorded approvals).
- **L3.** No `section_confirm` notification is written when the line edit wipes approvals (unlike U2).

**Errors:** the manager's; the invoice step's. **Side effects:** line, totals, events, approvers; `items_updated_at`; invoice per Y; commit.

---

## `ExpenseOrderService.update_item(db, item_id, item_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /expense-orders/items/{item_id}/`)

**Rules:**
- **L4.** The line is edited per `ExpenseOrderManager.update_item` (404 line, 404 order, 400 completed/voided, subtotal, totals, event and approval wipe only on a real change, BUG-740).
- **L5.** The line's order gets `items_updated_at = utcnow()` — also when nothing changed — and the invoice step runs as L2, for the line's own order. No notification (as L3).

**Returns:** the line, committed and refreshed.

---

## `ExpenseOrderService.remove_item(db, item_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /expense-orders/items/{item_id}/`)

**Rules:**
- **L6.** The line is removed per `ExpenseOrderManager.remove_item`; the order's `items_updated_at = utcnow()`; invoice step as L2 (a linked draft loses the line; removing the last line leaves a draft with no lines, worth 0.00). No notification.
- **L6a.** A missing line, or one of another workspace, → 404 `Expense order item not found` (manager `remove_item` R1); its order missing → 404 `Expense order with ID <id> not found`. Nothing written, rolled back. (G6)
- **L7.** Returns the deleted line object, not refreshed (its `expense_order_id`, `line_number` still readable); committed.

---

## `ExpenseOrderService.get_items(db, eo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /expense-orders/{id}/items/`)

- **L8.** Returns `ExpenseOrderManager.get_items` (404; lines by `line_number`, BUG-2713). TC6.

---

## `ExpenseOrderService._invoice_item_dicts(eo_items)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `_create_draft_invoice`, `_resync_draft_invoice`)

**Returns:** one dict per order line, in the given order.

**Rules:**
- **S1.** `line_number` = position in the list, 1…N (not the order line's own `line_number`: lines 1, 3, 4 become 1, 2, 3).
- **S2.** `description` = the line's description; empty or `None` → `Expense item <line id>`.
- **S3.** `item_id = None`, `source_order_item_id` = the line's id, `source_order_item_type = "eo_item"`, `unit` as stored (may be `None`).
- **S4.** `quantity` as stored; `0` or `None` → `Decimal(1)`. (After BUG-362 a line's quantity is always > 0, so this fallback is reachable only by older rows: a 0-quantity line becomes quantity 1 on the invoice with its stored subtotal.)
- **S5.** `unit_price` and `line_subtotal` as stored; `None` → `Decimal(0)` (a line without a price is a 0.00 invoice line). No rounding and no recomputation: the invoice line's subtotal is the order line's.
- **S6.** Empty list → `[]`.

---

## `ExpenseOrderService._create_draft_invoice(db, eo, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `_sync_or_create_invoice`, `create_invoice_for_expense_order`)

**Purpose:** Make the order's draft payable invoice, link it and fill its lines.

**Returns:** the order (with `invoice_id` set), flushed, not committed.

**Rules:**
- **D1.** No account on the order → 422 `Set an account on the expense order before creating an invoice` (per `resolve_invoice_account_id`), nothing written.
- **D2.** The invoice is created per `AccountInvoiceManager.create_invoice` as a `payable` draft for the order's account with `order_type = "expense_order"`, `order_id` = order id, `due_date` = the order's, `description` = `Auto-created from expense order <expense_number>`, `notes` = the order's description, `allow_payments = True`, no invoice / vendor numbers, no payment lock reason. [BUG-627] No `invoice_amount` is sent; the draft starts at 0.00 and follows its lines. *(Today: `invoice_amount = 0.00` is sent; after the BUG-627 schema change that would be a 422, so the fix must drop it here too.)*
- **D2a.** `create_invoice` is called by keyword (`session=db, invoice_data=<AccountInvoiceCreate>, workspace_id=…, user_id=…`); the invoice's `created_by` = the acting `user_id` (create_invoice R5), also when the draft is made by the approver's approval or a template run. (G5, G8)
- **D3.** [BUG-3063] `invoice_date` = `utcnow().date()`. *(Today: `date.today()`, the server's local date.)*
- **D4.** Account refusals of `create_invoice` pass through unchanged: deleted account 400 `Cannot create invoice for deleted account`, inactive 400 `Cannot create invoice for inactive account`, `allow_invoices` false 403 `Invoices are not allowed for this account`.
- **D5.** Any 404 from `create_invoice` (account missing or of another workspace — older data, BUG-750) becomes 422 `Cannot create invoice: selected account was not found in this workspace` (the original as its cause); no id is shown. Other errors pass through unchanged.
- **D6.** The order's `invoice_id` = the new invoice; its lines are set per `sync_items_from_list` from `_invoice_item_dicts` of the order's lines (amount = sum of the lines; event `items_synced` on the invoice). An order with no lines gives a draft with no lines, 0.00.
- **D7.** One order event `invoice_created`, description `Invoice #<invoice id> created from expense order`, metadata `{"invoice_id": <id>}`, `performed_by = user_id`.
- **D8.** No notification here (the callers write it).

**Errors:** D1, D4, D5. **Side effects:** invoice row, its `created` and `items_synced` events and lines; order `invoice_id`; one order event; flushed.

---

## `ExpenseOrderService._resync_draft_invoice(db, eo, invoice, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `_sync_or_create_invoice`)

**Purpose:** Keep a linked draft invoice in step with the order.

**Rules:**
- **R1.** The invoice's lines are replaced per `sync_items_from_list` by `_invoice_item_dicts` of the order's current lines (one `items_synced` invoice event every time, also when nothing changed).
- **R2.** Due date: when the invoice's `due_date` differs from the order's, it is set to the order's (also to `NULL` once BUG-753 lets the order's be cleared).
- **R2a.** Clearing the invoice's due date works today: `update_invoice` on a draft applies every sent field with `model_dump(exclude_unset=True)` and writes `None` (verified in the code: the DAO gets a dict, so `None` is set). So `_resync_draft_invoice` with an order whose `due_date` is `None` and an invoice with a due date sets the invoice's to `NULL` today; R2 needs no tag. Through the API the order's due date can't be cleared until BUG-753, so set it to `None` on the row directly. (G9)
- **R3.** Notes: when the order has a non-empty description that differs from the invoice's `notes`, `notes` = the description. An empty order description never clears the notes.
- **R4.** Account: when the order has an account that differs from the invoice's, the invoice moves to it, with the checks of `update_invoice` R10 (deleted 400, inactive 400, `allow_invoices` false 403 — the whole order edit is undone). The deleted-account refusal holds today (R4a).
- **R4b.** [BUG-629] The inactive (400 `Cannot assign invoice to inactive account`) and `allow_invoices = False` (403 `Invoices are not allowed for this account`) refusals of R4 apply to the expense order's draft, and the whole order edit is undone (U4). *(Today: the draft branch of `update_invoice` checks only existence and `is_deleted`, so the draft moves to the inactive / non-invoicing account and the edit is saved — executor DISCREPANCY-1, EOS-U-07, R-08, R-09.)* BUG-629 is the same code path (`AccountInvoiceManager.update_invoice`, draft account change), reached here through `_resync_draft_invoice`; no new ID.
- **R4a.** A deleted account is one with `is_deleted = True` (`deleted_at` / `deleted_by` are not read by any check). Moving a draft to it → 400 `Cannot assign invoice to deleted account` (update_invoice R10, checked before the active / `allow_invoices` checks); creating a draft for it (D4) → 400 `Cannot create invoice for deleted account`. (G7)
- **R5.** The header changes of R2–R4 go to `AccountInvoiceManager.update_invoice` in one call (its `item_manually_updated` event lists them); with none, `update_invoice` is not called and no such event is written.
- **R5a.** [BUG-3068] While an invoice that is not voided is linked, clearing the order's account is refused with 400 `An invoice is linked to this order — choose another account instead of clearing it`, nothing written (the check belongs with the order edit, before anything is applied). *(Today: unreachable, because `null` is ignored (BUG-753); after BUG-753 the invoice would silently keep the old account.)*

---

## `ExpenseOrderService._sync_or_create_invoice(db, eo_id, workspace_id, user_id)`
**Shape:** helper · **Persistence:** writes (flush only) · **Visibility:** internal (used by: `update_expense_order`, `add_item`, `update_item`, `remove_item`, `approve_as_me`, `create_expense_order_from_template`; [BUG-3066] `remove_approver`)

**Purpose:** After a change, keep the draft invoice in step, or make it once approvals are met.

**Rules:**
- **Y1.** The order is re-read per `get_expense_order` (404 if missing).
- **Y2.** With a linked invoice found in this workspace whose status is `draft` → `_resync_draft_invoice`; nothing else.
- **Y3.** With a linked invoice that is `confirmed` or `voided`, or not found in this workspace → nothing happens (no draft is made, no event).
- **Y4.** No linked invoice and approvals not met → nothing happens.
- **Y5.** No linked invoice, approvals met, no account → one order event `invoice_autocreate_skipped`, description `Approvals met but no account set — set an account to generate the invoice`, `performed_by = user_id`; no invoice. Logged again on every call in that state (Q5, intended).
- **Y6.** No linked invoice, approvals met, account set, no lines → nothing happens (no event).
- **Y7.** No linked invoice, approvals met, account set, at least one line → a draft per `_create_draft_invoice`, then one `invoice_action` notification per recipient of `notify_invoice_action` with action `draft` (preview `draft|Linked payable invoice is in draft — confirm when details look correct`).

---

## `ExpenseOrderService.create_invoice_for_expense_order(db, eo_id, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/{id}/create-invoice`)

**Purpose:** Draft the order's invoice by hand (e.g. after an account was set).

**Returns:** the order, committed and refreshed.

**Rules:** checks run in the order I1, I3, I2, I4 (G10).
- **I1.** [BUG-3062] Order read per `get_expense_order` (404) with a row lock (`FOR UPDATE`). *(Today: no lock; two clicks at once make two drafts and the order keeps only the second.)*
- **I1a.** [BUG-3062] The lock is a plain `FOR UPDATE` on the one-table read of `expense_orders` (`SELECT … FROM expense_orders WHERE id = … AND workspace_id = … LIMIT 1 FOR UPDATE`; the read joins nothing and the model has no joined eager load, so `OF expense_orders` is not required — the BUG-029 / BUG-643 rule asks for `FOR UPDATE OF <table>` only when the read joins). `FOR UPDATE OF expense_orders` is equally correct and passes; `NOWAIT` and `SKIP LOCKED` are not allowed (the loser waits, then sees the new state). (G1)
- **I2.** An invoice already linked (any status) → 409 `Invoice already exists for this expense order`, nothing written.
- **I3.** [BUG-3065] Voided → 400 `Expense order is voided`, nothing written. Checked right after the locked read, **before** I2: a voided order that still has an invoice linked (older data only — every void unlinks, V7) gets this 400, not I2's 409 (G10, decided by Claude under the reviewer's delegation (2026-11-21)). *(Today: not checked; a voided order with met approvals gets a new draft — verified.)*
- **I4.** Approvals not met → 400 `Required approvals are not met`.
- **I5.** Otherwise a draft per `_create_draft_invoice` (D1: no account → 422; an order with no lines gets a 0.00 draft with no lines, which "complete" will refuse per BUG-628), then the `draft` notification as Y7; committed.
- **I6.** A completed order always has an invoice linked (C5), so it is refused by I2.

**Errors:** I1 404; I2 409; I3 400; I4 400; D1/D4/D5.

---

## `ExpenseOrderService.list_approvers(db, eo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /expense-orders/{id}/approvers/`)

- **A1.** Returns `ExpenseOrderManager.list_approvers` (404; `(approver, profile, position)` by `assigned_at`, BUG-1200). TC6.

## `ExpenseOrderService.approval_summary_for(db, eo_id, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (same endpoint)

- **A2.** Order read per `get_expense_order` (404 missing / other workspace); returns `(approved_count, required, met)` per `ExpenseOrderManager.approval_summary` (BUG-755). TC6.

---

## `ExpenseOrderService.add_approver(db, eo_id, user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/{id}/approvers/`)

**Returns:** the approver row, committed and refreshed.

**Rules:**
- **A3.** The approver is added per `ExpenseOrderManager.add_approver` (404; 400 completed / voided, BUG-754/756; 400 not an active member; 409 duplicate).
- **A4.** Notifications per `handle_add_approver` (actor = `assigned_by`): the new approver gets `approval_assigned`; if the order is ready for approval, every other pending approver gets `approval_pending`; if not ready, the creator gets `section_confirm` with the gap text.
- **A4a.** The creator's `section_confirm` preview on a not-ready order is the text of `approval_notification_service.spec.md` `_section_gap_preview` R3: the manager's `approvability_gap_reason` when it gives one — e.g. an order with category, date, description and no lines → `Add at least one expense line before approvals can proceed` (verified as the same text `set_approval` answers) — else `Complete remaining details before approvals can proceed` (today's text for a line problem; BUG-758 changes it). (G3)
- **A5.** No invoice step: a draft that exists stays (adding an approver can make approvals no longer met; see Q4).

---

## `ExpenseOrderService.remove_approver(db, eo_id, user_id, workspace_id, performed_by)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /expense-orders/{id}/approvers/{user_id}/`)

**Returns:** `None`.

**Rules:**
- **A6.** The approver is removed per `ExpenseOrderManager.remove_approver` (404 `Approver not found`; 400 completed, BUG-756) and committed.
- **A7.** [BUG-3066] Then the invoice step runs per `_sync_or_create_invoice` (Y1–Y7): when the removal makes approvals met, an order with an account and lines gets its draft invoice and the `draft` notification. *(Today: no invoice step; the order reads "met" with no invoice and "complete" says to set an account — verified.)*
- **A8.** No other notification is written.

---

## `ExpenseOrderService.approve_as_me(db, eo_id, user_id, workspace_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/{id}/approvers/me/approve/`)

**Returns:** the approver row, committed and refreshed.

**Rules:**
- **A9a.** The approval is recorded per `ExpenseOrderManager.set_approval(approved=True)` (403 not an approver; 400 voided; 400 not ready with the gap reason; no-op when already approved, BUG-757).
- **A9b.** Then the invoice step per `_sync_or_create_invoice`: the approval that makes approvals met drafts the invoice (Y7). Approving a **completed** order is allowed by the manager (its R3); the step then finds the confirmed invoice and does nothing (Y3).

---

## `ExpenseOrderService.unapprove_as_me(db, eo_id, user_id, workspace_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`DELETE /expense-orders/{id}/approvers/me/approve/`)

**Rules:**
- **A9.** The approval is withdrawn per `set_approval(approved=False)` (403; 400 `Cannot withdraw approval — order is complete`; no-op when not approved) and committed. No invoice step: a linked draft stays (Q4, intended). No notification.

**Returns:** the approver row, committed and refreshed.

---

## `ExpenseOrderService.list_events(db, eo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /expense-orders/{id}/events/`)

- **N1.** Returns `ExpenseOrderManager.list_events` (404; newest first; `(event, profile)`). TC6.

---

## `ExpenseOrderService.create_expense_order_from_template(db, template_id, overrides, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /expense-orders/from-template/{template_id}/`)

**Returns:** the new order, committed and refreshed.

**Rules:**
- **T1.** The order is created per `ExpenseOrderManager.create_expense_order_from_template` (404 template; 400 inactive; lines copied; approval waived / auto-approved / default approver, BUG-759).
- **T2.** Then the invoice step per `_sync_or_create_invoice`: a template that waives approval (`required_approvals = 0`) with an account and at least one line gives the new order its draft invoice and the `draft` notification at once; with no account, the `invoice_autocreate_skipped` event (Y5); with approval required, nothing.
- **T3.** No approver notification is written for the template's default approver (unlike `add_approver`).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 45–52 | create: try / commit / except | E1–E3; TC1–TC4 |
| 62–72 | `_approvals_reset` true / false | U2 |
| 73 | sync after update | U3, U4 |
| 81–82 | get | G1 |
| 92–101 | list → page, `**hub_filters` | L-1, L-2 |
| 124 | `invoice_filter` falsy / `"all"` / other | K2 |
| 162–172 | count, list, `has_more` | P-1…P-3 |
| 212–263 | stats, recent, snapshot mapping; empty lists | H-1…H-4 |
| 266–271 | delete try / except; no `user_id` | X1, X2 |
| 277 | complete: read (no lock) | C1 |
| 278–279 | already completed → return | C2 |
| — | voided not checked | C3 |
| 281–282 | approvals not met | C4 |
| 283–287 | no invoice | C5 |
| 289–291 | invoice not found | C6 |
| 292–293 | invoice voided | C7 |
| 295–302 | invoice draft → confirm + notify; else skip | C8, C9 |
| 304–314 | stamps, event, commit | C10 |
| 324 | void: read (no lock) | V1 |
| 326–327 | already voided | V2 |
| 328–329 | completed | V3 |
| 331 | invoice linked / not | V4, V7, V8 |
| 333–334 | invoice found and draft → delete; confirmed → (intended) refuse; else untouched | V5, V6, V6a |
| 335–345 | reset approvals, unlink, event | V7 |
| 347–356 | void fields, event | V9, V10, V12 |
| 370–381 | add_item, `items_updated_at`, sync | L1–L3 |
| 388–399 | update_item | L4, L5 |
| 405–415 | remove_item, no refresh | L6, L7 |
| 417–418 | get_items | L8 |
| 424 | description falsy → fallback | S2 |
| 428 | quantity falsy → 1 | S4 |
| 430–431 | price / subtotal falsy → 0 | S5 |
| 421–434 | enumerate; empty list | S1, S3, S6 |
| 440 | no account → 422 | D1 |
| 442–456 | invoice fields, `invoice_amount`, `date.today()` | D2, D3 |
| 465–471 | 404 → 422; other HTTPException re-raised | D4, D5 |
| 473–486 | link, sync items, event | D6, D7 |
| 492–495 | resync items | R1 |
| 498–499 | due date differs | R2 |
| 500–501 | description truthy and differs | R3 |
| 502–503 | account truthy and differs | R4, R5a |
| 504–509 | any header change → update_invoice | R5 |
| 516 | re-read order | Y1 |
| 518–522 | invoice linked: draft → resync; else return | Y2, Y3 |
| 524–525 | approvals not met | Y4 |
| 526–531 | no account → event | Y5 |
| 532–534 | no lines | Y6 |
| 535–539 | create + notify | Y7 |
| 545 | read (no lock) | I1 |
| 547–551 | invoice exists → 409 | I2 |
| — | voided not checked | I3 |
| 552–556 | approvals not met | I4 |
| 558–571 | create, notify, commit | I5, I6 |
| 577–580 | list_approvers | A1 |
| 585–586 | approval summary | A2 |
| 592–611 | add approver, notify | A3–A5 |
| 617–623 | remove approver (no sync) | A6–A8 |
| 629–638 | approve, sync | A9a, A9b |
| 644–652 | unapprove | A9 |
| 657–658 | events | N1 |
| 666–675 | from template, sync | T1–T3 |
| every `except Exception` | rollback, re-raise | TC3, TC4 |

## Gap log
G1 (expense_order_service.cases.md gap 1) — fact — lock clause stated: plain `FOR UPDATE` on the one-table `expense_orders` read, `OF expense_orders` also correct, no `NOWAIT` / `SKIP LOCKED`. Rules C1a, V1a, I1a.
G2 (gap 2) — fact — notification patch targets in Notes for the test designer.
G3 (gap 3) — fact — creator's gap-text preview. Rule A4a.
G4 (gap 4) — fact — modules of the response class and recent-summary mapper; recent-summary and bucket fields. Rules H-3a, H-4a.
G5 (gap 5) — fact — drafted invoice `created_by` = acting user. Rule D2a.
G6 (gap 6) — fact — `remove_item` 404 details. Rule L6a.
G7 (gap 7) — fact — deleted account = `is_deleted = True`; both details. Rule R4a.
G8 (gap 8) — fact — `create_invoice` called by keyword. Rule D2a.
G9 (gap 9) — fact — clearing the invoice due date to `NULL` works today; R2 stays untagged. Rule R2a.
G10 (gap 10) — contradiction — the voided check runs right after the locked read, before the already-completed return (C3 before C2) and before the 409 (I3 before I2), as the P3 resolution says; decided by Claude under the reviewer's delegation (2026-11-21). The listed order was not a separate bug: today there is no voided check at all, and the order is part of BUG-3065's intended rule. Rules C3, I3 and the check-order lines.
G11 (executor notes, EOS-V-03) — fact — `void_expense_order` V7 tagged [BUG-3070] with a *Today* note (the `invoice_voided` metadata carries `invoice_id: null` after the draft is deleted). Row already in bugs.md; decided by Claude under the reviewer's delegation (2026-11-22).
G12 (executor notes DISCREPANCY-1, EOS-U-07 / R-08 / R-09) — fact — BUG-629 covers expense drafts: the refusals come from `AccountInvoiceManager.update_invoice`'s draft account change, which is BUG-629's code path. New rule `_resync_draft_invoice` R4b [BUG-629]; R4 keeps the deleted-account part (passes today); U4's examples point at R4b. No new ID; decided by Claude under the reviewer's delegation (2026-11-22).
