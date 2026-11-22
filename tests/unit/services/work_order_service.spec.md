# Spec — `app/services/work_order_service.py`

> **Status:** APPROVED (2026-11-22; apply-review — owner answered OQ-WOS-1 as OQ-65, every other item decided under the reviewer's delegation of 2026-11-21)
> **Source commit:** e48a092

> **Review round 2026-11-21 (describe, under the reviewer's delegation of 2026-11-21).** House-rule lines and precedent matches are pre-filled. Every new question that is not a genuinely new money, stock, order-workflow or security question was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. One question is new money and goes to the owner: **OQ-WOS-1** (provisional number, to be renumbered when parked in `docs/testing/owner-questions.md`). Bug IDs come from block BUG-3222 … 3241 (3222–3228 used).
>
> **Apply-review 2026-11-22.** The owner answered OQ-WOS-1 with option (a), recorded as **OQ-65** in `docs/testing/owner-questions.md` → BUG-3228. Every pre-filled answer (house rules, precedents, Q1, Q2, OQ-62) is confirmed as written; bugs BUG-3222 … 3228 are logged in `docs/testing/bugs.md`. No `(proposed)` rule remains.
>
> **Already decided elsewhere, cited, not asked again:** every rule and bug of `tests/unit/managers/work_order_manager.spec.md` (APPROVED 2026-11-21), in particular: row locks BUG-2916 and its G9 placement (`finalize_completion` R18: the completion lock lives in `WorkOrderService.complete_work_order`); deleted orders found by `get_work_order` BUG-1279; cost / account frozen while an invoice is linked OQ-56 → BUG-2929; machine removal OQ-57 → BUG-2930; approvals frozen once started OQ-58 → BUG-2931; replaced part at zero value OQ-59 (intended); blank void note BUG-2918; deleting a draft must handle its invoice Q2 → BUG-2923 (the fix is placed here); FU-1 (a)–(f) of that spec. **OQ-62** (owner 2026-11-21, asked as OQ-EOS-1, same rule for work orders): voiding an order whose invoice is already finalized is refused, "This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order." The invoice manager (`account_invoice_manager.spec.md`): amount = sum of lines, no client amount on create BUG-627; confirm needs a line BUG-628; order link checked BUG-625 (a voided or deleted work order → 404); completed-order freeze O1 / F1–F7 (BUG-2730, BUG-2731); delete of a draft with payment history refused BUG-639. The invoice service (`account_invoice_service.spec.md`): a work order's invoice is finalized only by completing the order (OQ-60 → BUG-2969, K10); voiding it on the invoice page unlinks the order (BUG-2966, X8); deleting it there unlinks it (BUG-2732, D5); "resync items" rebuilds the one line this service makes (BUG-2964, S7). Notification texts and recipients: `approval_notification_service.spec.md` (N1–N12, routed to `docs/future/notifications.md`). Expense-order precedents: `expense_order_service.spec.md` BUG-3062 (service-level locks), BUG-3063 (invoice date), BUG-3065 (invoice for a voided order).
>
> **Deferred areas.** **Production:** not touched by this module; no rules. **Projects (revisit after launch):** the service has no project logic of its own; an order's project component is handled entirely by the manager (rules tagged there). Nothing here is logged as a bug for projects.
>
> **Verified by running** (my own script `v_wos.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3desc\wo\`, one outer transaction on `marker_test`, session `join_transaction_mode="create_savepoint"`, rolled back, nothing persisted): voiding a 500.00 order and then "create invoice" makes a new 500.00 **draft** payable invoice for the **voided** order; an order with an account and no cost gets a 0.00 draft invoice whose `payment_status` is already `paid`, and completing it finalizes a **confirmed 0.00, paid** invoice; deleting a draft order leaves its 2,000.00 draft invoice linked (`invoice_id` kept); voiding an order whose 40,000.00 invoice was confirmed on the invoice page voids the order, **keeps** `invoice_id` and leaves the invoice `confirmed` and payable; "complete as planned" on an `IN_PROGRESS` order with an account and no invoice answers `No invoice linked — create an invoice for this external work before completing` rather than the draft-state error; a second "complete" returns the completed order; the auto-created invoice is `payable`, `order_type = "work_order"`, `order_id` = the order, amount = cost, `due_date` = end date, `notes` = description, description `Auto-created from work order WO-2026-007`, one line (title, `1.00`, cost, `wo_labor`); the creator (who was also the actor) gets one `invoice_action` notification with the `draft|…` preview; the response carries `assignee_user_ids` matched from `assigned_to`. **Read, not run:** sheet bundles, approver paths, items, template and sheet entry (the manager's, verified in its spec). **Not run:** HTTP; two concurrent transactions; intended behaviour of the bugs.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| H1 | "Create invoice", "void" and "complete as planned" read the order and act on its invoice without locking it | bug — BUG-3222 | house rule HR-10 (confirmed under the delegation) |
| H2 | "Complete" checks `IN_PROGRESS` and confirms the invoice without locking the order | bug — BUG-2916 (existing) | manager G9 (Claude, delegated 2026-11-21) |
| P1 | A voided or completed order can get a new invoice | bug — BUG-3225 | precedent BUG-3065 / manager FU-1 (a) (confirmed under the delegation) |
| P2 | The auto-created invoice's date is the server's local date | bug — BUG-3226 | precedent BUG-3063 / BUG-1334 (confirmed under the delegation) |
| P3 | Deleting future recurring drafts (and the sheet's re-plan) leaves their draft invoices linked | bug — BUG-3227 | precedent BUG-2923 (confirmed under the delegation) |
| P4 | Deleting a draft leaves its draft invoice linked | bug — BUG-2923 (existing) | manager Q2 (Claude, delegated 2026-11-19); fix placed here |
| P5 | The service still sends `invoice_amount = 0.00` when it creates the invoice | bug — BUG-627 (existing) | owner (invoice manager Q1) |
| Q1 | "Complete as planned" on an order that is not a draft can answer with an invoice error instead of "must be in draft" | bug — BUG-3223 | delegation |
| Q2 | Voiding a completed order with a leftover draft invoice: which error wins | folded into BUG-3224 | delegation |
| OQ-62 | Voiding an order whose invoice is already finalized leaves the order voided and the bill payable | bug — BUG-3224 | **owner** (OQ-62, 2026-11-21) |
| OQ-65 | An order with an account but no cost gets a 0.00 invoice that shows "paid", and completing it finalizes it | bug — BUG-3228 | **owner** (OQ-65, asked as OQ-WOS-1, 2026-11-22) |

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-10** `create_invoice_for_work_order` I1, `void_work_order` V1, `complete_work_order_as_planned` P1 — each reads the order with a plain read, checks its invoice and then creates, deletes or confirms an invoice. The manager's locks (BUG-2916: `void_work_order` R10, `complete_as_planned` R11) come **after** the service has already acted on the invoice, and "create invoice" has none at all. A race does real harm: two "create invoice" clicks make two draft invoices and the order keeps only the second (the first stays on the account's list, orphaned); a void and a "create invoice" at the same time leave a voided order with a fresh draft bill; two "complete as planned" both get past the completed check. Intended: each reads the order row `SELECT … FOR UPDATE` at its first read, before any check; the loser sees the new state and gets the normal error (for "complete as planned", the early return of an already-completed order, P2). 🐞 BUG-3222
**Answer:** bug — per HR-10 (house rule)
**Resolution:** BUG-3222, pattern `hr-10-unlocked-state-transition` (as BUG-3062 for expense orders). Rules: `create_invoice_for_work_order` I1, `void_work_order` V1, `complete_work_order_as_planned` P1.
- **HR-10** `complete_work_order` C1 — reads the order, checks `IN_PROGRESS`, confirms the invoice and completes, with no lock. Already logged and placed: manager spec `finalize_completion` R18 (G9, decided by Claude under the reviewer's delegation, 2026-11-21) puts this lock here, under **BUG-2916**. No new ID.
**Answer:** bug — per HR-10 (house rule; existing BUG-2916)

Checked and **not** violated: **HR-1/2/3** — no names stored here (the void reason is BUG-2918, manager's). **HR-4** — a soft-deleted order is still reached through `get_work_order` (BUG-1279, manager's; every rule below that reads the order inherits it, no new ID); the invoice is read by id and workspace (BaseDAO scope). **HR-5/6/7/8** — filtering, order and search are the manager's / DAO's (BUG-2670, BUG-2672 … 2675, BUG-1200, BUG-1272); the endpoints enforce `limit` 1…1000 (list) and 1…100 (sheet); `has_more` uses the true total. **HR-9** — the service writes no audit stamp of its own. **HR-11–14** — no external system or batch. **HR-15** — no money arithmetic: the invoice line copies `cost` (or 0) unchanged. **HR-16** — every read takes the caller's `workspace_id`; a linked invoice of another workspace (legacy) is "not found": "complete" answers 400 `Linked invoice not found` without the id, "void" leaves it untouched; an account 404 from the invoice manager is reworded without the id (I7). The enrichment reads profile names from the global `profiles` table by the order's own `started_by` / `completed_by` ids, which the manager sets to workspace members only.

**Permission checks:** none in the service. Every endpoint needs only an active member of the workspace: any member can complete, complete-as-planned, void, delete, create the invoice, and add or remove any approver. Only approving / withdrawing checks that the caller is an approver (manager `set_approval` R1). Noted for `docs/future/permissions.md`, not a question here.

### Precedent matches — confirm all with ok

### P1. A voided or completed order can get a new invoice — 🐞 BUG-3225 (precedent)
**Background:** voided and completed work orders are read-only in the manager (`_is_locked`: no edit, no line change, no approver change). "Create invoice" does not go through those guards: it checks only that no invoice is linked and that the order has an account. Voiding deletes a draft invoice and clears the link. A completed order's invoice is frozen (O1, F2/F4: a draft of a completed order can't be deleted) and a work order's invoice can be finalized only by completing the order (OQ-60, BUG-2969).
**What happens today:** "Create invoice" on a voided order makes a new draft payable invoice for it (verified: 500.00 draft on a `VOIDED` order). On a completed order whose invoice was unlinked (older data), it makes a draft that can then never be finalized, deleted or voided.
**Example:** WO-2026-031, outside repair by "Karim Engineering" for 5,000 taka, is voided as a duplicate. Someone clicks "Create invoice": accounting now shows a 5,000 taka draft bill to Karim Engineering for a cancelled job. After BUG-625 the invoice manager would refuse it, but the service would report it as "selected account was not found", which is wrong.
**Rules affected:** `create_invoice_for_work_order` I3
**Answer:** bug — per BUG-3065 precedent and manager FU-1 (a): a voided order → 400 `Work order is voided`, a completed order → 400 `Work order is completed` (the manager's wording for locked orders), checked right after the order is read (after the lock of H1) and before the "invoice already exists" check, nothing written (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3225, pattern `missing-state-guard`. Rule: `create_invoice_for_work_order` I3.

### P2. The auto-created invoice's date is the server's local date — 🐞 BUG-3226 (precedent)
**Background:** dates the system stamps were ruled to come from the UTC clock (`utcnow()`, BUG-1334); the expense order service's auto-drafted invoice got the same fix (BUG-3063).
**What happens today:** the invoice gets `invoice_date = date.today()`, the local date of the machine running the API.
**Example:** on a server set to Dhaka time, an invoice made at 01:30 on 2 March is dated 2 March while `utcnow()` is still 1 March.
**Rules affected:** `create_invoice_for_work_order` I6
**Answer:** bug — per BUG-3063 / BUG-1334 precedent: `invoice_date = utcnow().date()` (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21))
**Resolution:** BUG-3226, pattern `local-clock-instead-of-utc`. Rule: `create_invoice_for_work_order` I6.

### P3. Deleting future recurring drafts leaves their draft invoices linked — 🐞 BUG-3227 (precedent)
**Background:** BUG-2923 (manager Q2) decided that deleting a draft work order does what voiding does to its invoice: a linked draft invoice is deleted and unlinked with an `invoice_voided` event; a linked invoice that is not a draft refuses the delete. Two other paths soft-delete drafts in bulk: "delete future drafts" of a recurring program (`bulk_delete_future_recurrence_drafts`) and the sheet entry's re-plan of a recurring template (manager `sync_recurrence_drafts_for_machine`, called from `sheet_entry`). A recurring template can carry an account, so its drafts can get invoices.
**What happens today:** both paths soft-delete the drafts and never look at their invoices; a draft invoice stays on the account's list for an order nobody can see.
**Example:** the monthly "Compressor service by Karim Engineering" (3,000 taka) has drafts for June–December; someone made the June draft's invoice early. The planner deletes the future drafts: the 3,000 taka June draft bill stays and can still be confirmed and paid.
**Rules affected:** `bulk_delete_future_recurrence_drafts` B3, `sheet_entry` SE3
**Answer:** bug — per BUG-2923 precedent: each draft deleted by these paths has its linked draft invoice deleted and `invoice_id` cleared, with the same `invoice_voided` event as `delete_work_order` X3; if any of the drafts has a linked invoice that is not a draft (confirmed or voided-but-linked legacy data), the whole call is refused with 400 `Work order <number> has a confirmed invoice — void the invoice first`, nothing deleted (precedent — confirmed: ok, decided by Claude under the reviewer's delegation (2026-11-21): a bulk housekeeping action must not silently leave bills behind, and a partial delete would be invisible to the planner)
**Resolution:** BUG-3227, pattern `delete-ignores-dependents` (as BUG-2923). The fix lives with each bulk path: the service for `bulk_delete_future_recurrence_drafts`, the manager's `sync_recurrence_drafts_for_machine` for the sheet path (stated here as the outcome of `sheet_entry`). Rules: `bulk_delete_future_recurrence_drafts` B3, `sheet_entry` SE3.

### P4. Deleting a draft leaves its draft invoice linked — 🐞 BUG-2923 (existing, manager Q2)
**Background / Example:** manager spec Q2 (verified again here: a deleted draft keeps its 2,000.00 draft invoice).
**Rules affected:** `delete_work_order` X2, X3
**Answer:** bug — per BUG-2923 (decided 2026-11-19 under the delegation, manager spec APPROVED): fix placed in `WorkOrderService.delete_work_order` (precedent — confirmed: ok)
**Resolution:** existing BUG-2923, no new ID. Event description chosen here (decided by Claude under the reviewer's delegation, 2026-11-21): `Invoice unlinked — work order <number> deleted`, mirroring the void path's `… voided`. Rules: `delete_work_order` X2, X3.

### P5. The service still sends `invoice_amount = 0.00` — 🐞 BUG-627 (existing)
**Background:** BUG-627 removes `invoice_amount` from `AccountInvoiceCreate`; a request that still carries it is refused with 422.
**What happens today:** the service builds `AccountInvoiceCreate(invoice_amount=Decimal("0.00"), …)`. After the BUG-627 schema change this call would fail, so the fix must drop it here too (as `expense_order_service.spec.md` D2).
**Rules affected:** `create_invoice_for_work_order` I6
**Answer:** bug — per BUG-627 (owner): no `invoice_amount` is sent; the draft starts at 0.00 and follows its line (precedent — confirmed: ok)
**Resolution:** existing BUG-627, no new ID. Rule: `create_invoice_for_work_order` I6.

### New questions

### Q1. "Complete as planned" on an order that is not a draft can answer with an invoice error — 🐞 BUG-3223
**Background:** "complete as planned" is for a draft whose planned day has passed: it starts and completes it in one step. The manager refuses anything that is not a draft (`Work order must be in draft to complete as planned`). The service first handles the invoice of an order with an account (no invoice → 400, voided → 400, draft → confirm), and only then calls the manager.
**What happens today:** on an `IN_PROGRESS` (or voided) order with an account and no invoice, the user is told `No invoice linked — create an invoice for this external work before completing` (verified). Following that advice, they create an invoice — and are then told the order must be a draft. With a draft invoice, it is confirmed and the confirm is rolled back again by the manager's refusal.
**Example:** WO-2026-044 was started yesterday. A supervisor clicks "Complete as planned" by mistake and is asked to create an invoice; they do, and get "must be in draft". The right button was "Complete".
**Rules affected:** `complete_work_order_as_planned` P3
**Answer:** bug — right after the already-completed return (P2), an order that is not `DRAFT` → 400 `Work order must be in draft to complete as planned`, before any invoice check, nothing written; the manager's other checks keep their place (decided by Claude under the reviewer's delegation, 2026-11-21: same order as "complete", which checks the state first; error precedence only, no money moves because everything is rolled back today)
**Resolution:** BUG-3223, pattern `misleading-error`. Rule: `complete_work_order_as_planned` P3.

### Q2. Voiding a completed order with a leftover draft invoice: which error wins — folded into BUG-3224
**Background:** a completed order cannot be voided (manager `void_work_order` R2). The service deletes a linked **draft** invoice before calling the manager. A completed order normally has a confirmed invoice; a leftover draft is possible only on older data (an order without an account but with an invoice). After BUG-2730 the invoice manager refuses to delete a completed order's draft with `Invoice is locked — the linked work order is completed. …`.
**What happens today:** the draft is deleted, then the manager answers `Cannot void a completed work order` and everything is rolled back. After BUG-2730 the user would instead see the invoice-lock message.
**Example:** an old completed order WO-2025-210 with a leftover draft: "Void" should say the order is completed, not talk about credit notes.
**Rules affected:** `void_work_order` V2
**Answer:** bug — the order's state is checked before any invoice step: completed → 400 `Cannot void a completed work order`, already voided → 400 `Work order is already voided` (decided by Claude under the reviewer's delegation, 2026-11-21: error precedence only; it is part of the same restructuring as the OQ-62 fix, so it carries BUG-3224)
**Resolution:** part of BUG-3224. Rule: `void_work_order` V2.

### Owner questions

### OQ-62 (applied). Voiding an order whose invoice is already finalized — 🐞 BUG-3224 (owner, 2026-11-21)
**Background:** a work order's invoice is normally finalized only when the order is completed, and a completed order cannot be voided. Before the OQ-60 fix (BUG-2969) an accountant could finalize it early on the invoice page, so existing data can hold not-completed orders with a finalized invoice. Voiding deletes a **draft** invoice; any other invoice is left as it is, **and stays linked**.
**What happens today:** the order is voided; it keeps `invoice_id`; the invoice stays `confirmed` and payable (verified: 40,000.00 confirmed, still linked to the voided order). Payments already made stay on it.
**Example:** WO-2026-080, outside overhaul by "Karim Engineering" for 40,000 taka, had its invoice finalized early. The job is cancelled and the order voided. Accounting still shows a 40,000 taka bill due to Karim Engineering.
**Rules affected:** `void_work_order` V5a
**Answer:** owner, 2026-11-21 (OQ-62, asked as expense order OQ-EOS-1, same rule for work orders; `work_order_manager.spec.md` FU-1 (b)): refuse the void with "This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order."
**Resolution:** BUG-3224, pattern `linked-record-not-updated` (as BUG-3069). Rules: `void_work_order` V2 (state first, Q2), V5a.

### OQ-65 (applied; asked as OQ-WOS-1). An order with an account but no cost gets a 0.00 invoice that shows "paid", and completing it finalizes it — 🐞 BUG-3228 (owner, 2026-11-22)
**Background:** a work order for outside work names an account (the contractor) and a cost. "Create invoice" makes a draft payable invoice with one line: the order's title, quantity 1, at the order's cost — or at 0.00 when no cost is set. An invoice of 0.00 with nothing paid counts as `paid` (0 paid of 0 owed). Once the invoice exists, the cost can't be changed any more (OQ-56) until the draft invoice is deleted. "Complete" then finalizes the draft as it is.
**What happens today:** an order with an account and no cost gets a 0.00 draft invoice that already shows "paid"; completing the order finalizes a 0.00 "paid" bill (verified). Nobody is asked for the price.
**Example:** WO-2026-090, "Rewind motor — Karim Engineering", is created without a cost because the quote has not come in. Someone clicks "Create invoice" and later "Complete". The books show a finalized 0.00 bill to Karim Engineering marked paid; when Karim's 12,000 taka invoice arrives there is nothing to pay it against, and the 12,000 taka never shows as owed.
**Rules affected:** `create_invoice_for_work_order` I4a
**Suggested answer:** (a) refuse when the cost is empty or zero.
**Options for the owner:**
- **(a) Refuse "Create invoice" until the order has a cost above zero — recommended.** "Create invoice" says "Set the work order's cost before creating an invoice." (like the existing "Set an account …" message), and nothing is made. In the example the supervisor enters 12,000 taka when Karim's quote arrives, then creates the invoice; the books show 12,000 taka owed to Karim from that moment. Free outside work (e.g. under warranty) simply gets no invoice: leave the account off the order, and "Complete" doesn't ask for one.
- **(b) Refuse only an empty cost; allow an explicit 0.00.** Same as (a) when the cost was never filled in. But someone who types 0 on purpose (warranty job done by Karim at no charge) still gets a 0.00 bill, finalized at completion and shown as paid, as a record that the job was billed at nothing.
- **(c) Keep today's behaviour.** A 0.00 "paid" draft is made whenever the cost is missing. To fix it someone must delete the draft invoice, enter the 12,000 taka cost, and create the invoice again — if they notice before completing; after completion the 0.00 bill is frozen and the 12,000 taka must be recorded some other way.
**Answer:** owner, 2026-11-22 (OQ-65): option (a) — "Create invoice" is refused until the order's cost is above 0, with "Set the work order's cost before creating an invoice." Free outside work has no account and gets no invoice.
**Resolution:** BUG-3228, pattern `missing-required-money-input` (as BUG-2787). Rule: `create_invoice_for_work_order` I4a. Decided by Claude under the reviewer's delegation (2026-11-21), within the owner's answer: status **422**, like the sibling account check I4 (both are "fill in the order first" refusals); checked after I4, so an order with neither account nor cost is told about the account first; a negative cost is refused the same way ("above 0"); completion (C7 / P4) gets no new check — once I4a holds, a new draft always carries a cost above 0 and the cost is frozen while it is linked (OQ-56, BUG-2929), so a 0.00 draft can only be legacy data and is finalized as today.

## Overview
`WorkOrderService` is the transaction layer for work orders. Around `WorkOrderManager` it commits or rolls back, and it adds what spans modules: the order's **payable invoice** for outside work (made by hand with "Create invoice", finalized when the order is completed, deleted when the order is voided), the **invoice step of completion** (both "complete" and "complete as planned"), and **notifications** (`approval_notification_service`: approvals reset on edit, new approver, invoice drafted / confirmed). It also builds the API's order responses (assignees, completers, people's names) and the planning sheet's bundles. Callers: the endpoints in `app/api/v1/endpoints/work_orders.py` only (`_to_work_order_response(s)` is called from there too). Invariants it is meant to protect: an order with an account is completed only with a finalized invoice; a voided order has no draft invoice; one invoice per order.

**Callables:** 29 specified · 3 not specified · 92 rules
**Externals to mock:** none of its own. `date.today()` (invoice date, I6) reads the system clock and is not mocked today (BUG-3226 moves it to `utcnow`; intended patch target `app.services.work_order_service.utcnow`, Facts); the manager's targets (`app.managers.work_order_manager.utcnow`, `settings`) per its spec when a test depends on them. Notifications are **not** mocked: they are `notifications` rows written in the same transaction (`approval_notification_service.spec.md` Overview).
**Integration-only behavior:** the races of BUG-3222 / BUG-2916 (two concurrent transactions); the row lock itself is observable in a unit test (SQL capture, see Notes).

### Transaction contract
Every write method here follows **TC1–TC6** of `tests/unit/services/base_service.spec.md` (repeated from `department_service.spec.md`, unchanged): manager call(s), invoice / notification steps, `_commit_transaction`, `db.refresh` of the returned row, all in one `try`; any exception rolls the session back and is re-raised as the same object. Departures, stated in the callable: `remove_approver` returns `None` (no refresh); `remove_item` returns the soft-deleted line without a refresh; `bulk_delete_future_recurrence_drafts` returns a response object built from the deleted ids (no refresh); `complete_work_order` and `complete_work_order_as_planned` on an already-completed order return it without commit or rollback (C2, P2). Reads (`get_work_order`, `list_*`, `get_items`, `approval_summary_for`, sheet reads, the response mappers) follow TC6. Because notifications and invoice steps run inside the `try`, an error there undoes the whole order change (TC3).

**Facts for the test designer**
- Import: `from app.services.work_order_service import WorkOrderService, work_order_service`. `WorkOrderService()` takes no arguments; `.manager` is the `work_order_manager` singleton, `.account_invoice_manager` the `account_invoice_manager` singleton.
- The invoice is linked through `work_orders.invoice_id` (FK to `account_invoices`, `ON DELETE SET NULL`). The invoice carries `order_type = "work_order"`, `order_id` = the order's id, `invoice_type = "payable"`. Invoice lines: `invoice_items`; invoice events: `invoice_events`; order events: `work_order_events` (`event_type`, `description`, `metadata_json`, `performed_by`).
- Order status values (plain text): `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `VOIDED`. Invoice status: `draft`, `confirmed`, `voided`.
- Notification rows: `notifications` (`recipient_user_id`, `notification_type`, `entity_type = "work_order"`, `entity_id` = the order's id, `source_type`, `source_id`, `preview`). Recipients must be **active** members (`workspace_members.status = "active"`). `work_orders.created_by` is nullable; with `None` the creator gets nothing.
- An account that can be invoiced: `Account(workspace_id, name, is_active=True, is_deleted=False, allow_invoices=True)`.
- `notify_invoice_action` previews: action `draft` → `draft|Linked payable invoice is in draft — confirm when details look correct`; action `confirmed` → `confirmed|Invoice confirmed on WO-<order id> — order locked` (`<order id>` is the database id, not the number). Recipients: pending approvers; every approver when `required` > 0; the creator; each once, active members only (`notify_invoice_action` R2–R5).

- **L1. Lock clause (C1, P1, V1, I1; gap 1, decided by the coordinator 2026-11-22).** The locked read is the same single-table read as `get_work_order` (`work_orders` by `id` and `workspace_id`; `WorkOrder` has no eager-loaded relationship — `items` is `lazy="dynamic"` — so the statement joins nothing). Intended clause: a plain `FOR UPDATE` at the end of that `SELECT … FROM work_orders …`. `FOR UPDATE OF work_orders` is equivalent on this single-table read and also conforms. `NOWAIT` and `SKIP LOCKED` never appear (a waiting loser must see the new state, HR-10). If the read ever gains a join or eager load, the clause must become `FOR UPDATE OF work_orders` (BUG-029 rule).
- **Patch targets (gap 2).** `notify_section_confirm_needed`, `handle_add_approver` and `notify_invoice_action` are imported by name at module level from `app.services.approval_notification_service`, so `app.services.work_order_service.<name>` is the patch target for a failing notification (U5, A4, I10).
- **Clock (gap 3).** Today the module imports `date` from `datetime` and calls `date.today()` (I6); it does not import `utcnow`. The BUG-3226 fix imports `utcnow` from `app.utils.time` into this module, so the intended patch target is `app.services.work_order_service.utcnow` (use `create=True` until the fix lands).
- **`_WorkOrderEnrichment` (gap 4).** Importable as `from app.services.work_order_service import _WorkOrderEnrichment`. A `@dataclass(frozen=True)` with exactly three fields, in this order: `assignee_map: dict[int, list[int]]`, `completer_map: dict[int, list[int]]`, `profile_names: dict[int, str | None]`; positional or keyword construction both work.
- **`work_orders.cost` (gap 6).** `Numeric(15, 2)`, nullable, no check constraint (checked on marker_test, read-only, rolled back): `-5.00` can be stored directly, so I4a's negative case can insert it.
- **Constraints (executor round, 2026-11-22; Gap log G9).** `work_orders.work_order_type_id` (FK `work_order_types`, `ON DELETE RESTRICT`), `factory_id` and `title` are **NOT NULL**: an order without a type or a factory cannot be stored, so no card may build one. A "not ready for approval" order is built with a whitespace-only title (`title="   "`, stored as typed when inserted directly), which gives the gap text `Work order setup is incomplete`. The stock table is `inventory` (model `Inventory`), not `inventories`.

**Notes for the test designer**
- Session and commits as in `base_service.spec.md` Notes: under the `db` fixture `commit()` releases a savepoint; assert "committed" with a test-level `db.rollback()` and a re-select.
- Stock is not needed for most cases: create orders with `uses_inventory=False` (no lines), as the verification script did.
- An invoice confirmed "on the invoice page" (legacy, before BUG-2969) is made by calling `account_invoice_manager.confirm_invoice` directly on the order's draft.
- Row-lock cases (H1, H2): capture SQL with a `before_cursor_execute` listener and look for `FOR UPDATE` (optionally `OF work_orders`, never `NOWAIT` / `SKIP LOCKED`) on the `work_orders` read before the first state check, as the manager tests do (L1).
- A "completed order with no invoice" for I3 / I2: build it directly (set `status = "COMPLETED"`), since "complete" requires an invoice when the order has an account.

## Not specified
- `WorkOrderService.__init__` — wires the two managers, no logic.
- `_WorkOrderEnrichment` — frozen dataclass holding the three maps of `_load_work_order_enrichment`; no logic.
- `work_order_service` — module-level singleton.

---

## `WorkOrderService._load_work_order_enrichment(db, orders)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `_to_work_order_response`, `_to_work_order_responses`)

**Purpose:** Fetch, for a batch of orders, their planned workers, their recorded completers and the names of the people who started / completed them.

**Returns:** `_WorkOrderEnrichment(assignee_map, completer_map, profile_names)`.

**Rules:**
- **W1.** An empty list → three empty maps; nothing is read.
- **W2.** `assignee_map` has a key for every given order: the profile ids of its `work_order_assignees` rows in the order's own workspace, in row-id order; `[]` when it has none. Orders of several workspaces are read per workspace, each with its own workspace id (only reachable from code, the endpoints pass one workspace's orders).
- **W3.** `completer_map` is the same for `work_order_completers` rows.
- **W4.** `profile_names` maps profile id → `name` for every order's `started_by` (when set) and for its `completed_by` only when `completed_by_names` is empty or `None`. Ids without a profile row are absent from the map. No profile is read when no such id exists.

---

## `WorkOrderService._to_work_order_response(db, wo, *, enrichment=None)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** public in practice (used by: every endpoint returning one order, through `_wo_response`; `_to_work_order_responses`)

**Returns:** a `WorkOrderResponse`.

**Rules:**
- **W5.** Without `enrichment`, it is loaded for this one order per `_load_work_order_enrichment`.
- **W6.** Every column of the order is copied (`WorkOrderResponse.model_validate`), plus `work_order_type_name` (the type's name; the type is always there: `work_orders.work_order_type_id` is NOT NULL and the FK is `ON DELETE RESTRICT`; a **soft-deleted** type still gives its name, since the relationship ignores `is_deleted` — intended, the order keeps its history, decided by Claude under the reviewer's delegation (2026-11-22); `None` only for an unsaved order object with no type) and the computed `calendar_date` (planned date, else the day of `created_at`).
- **W7.** `assignee_user_ids` / `completer_user_ids` = the order's lists from the enrichment, `[]` when the order is not in the maps.
- **W8.** `started_by_name` = the name of the `started_by` profile when `started_by` is set (`None` when that profile is missing); `None` when not started.
- **W9.** `completed_by_name` = `completed_by_names` when that text is non-empty; else, when `completed_by` is set, that profile's name (or `None`); else `None`. `completed_by_names` itself is copied as stored.
- **W10.** Pure mapping: nothing is written, committed or rolled back (TC6).

---

## `WorkOrderService._to_work_order_responses(db, orders)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** public in practice (used by: `GET /work-orders/`, `list_sheet_bundles`)

**Rules:**
- **W11.** An empty list → `[]`, nothing read.
- **W12.** Otherwise the enrichment is loaded once for all orders and each order is mapped per `_to_work_order_response` W6–W9, in the given order.

---

## `WorkOrderService.create_work_order(db, wo_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /work-orders/`)

**Returns:** the new order, committed and refreshed.

**Rules:**
- **E1.** The order is created per `WorkOrderManager.create_work_order` (all its rules and errors: factory / type / account / machine checks, number, events, approval stamp) and committed (TC1–TC4).
- **E2.** No invoice is made and no notification is written, even when the order has an account and a cost.

---

## `WorkOrderService.create_work_order_from_template(db, template_id, overrides, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /work-orders/from-template/{template_id}/`)

**Returns:** the new order, committed and refreshed.

**Rules:**
- **T1.** The order is created per `WorkOrderManager.create_work_order_from_template` (404 template; 400 inactive; lines; approvers; BUG-1206, BUG-2922) and committed (TC1–TC4).
- **T2.** No invoice, and no notification — not even to the approvers copied from the template (unlike `add_approver` A4).

---

## `WorkOrderService.update_work_order(db, wo_id, wo_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /work-orders/{id}/`)

**Returns:** the order, committed and refreshed.

**Rules:**
- **U1.** The edit follows `WorkOrderManager.update_work_order` (all its rules and errors, including BUG-2929 cost / account refused while an invoice is linked, BUG-2930, BUG-2931, BUG-2915).
- **U2.** When the manager cleared recorded approvals (`_approvals_reset` true), one `section_confirm` notification goes to the order's creator, per `notify_section_confirm_needed` R1–R4: preview `Approvals were reset — order details changed; re-approve when ready`, source `section` / order id, actor `user_id`; also when the creator made the edit; nothing when `created_by` is `None` or the creator is not an active member. No notice goes to the approvers.
- **U3.** When approvals were not cleared (`_approvals_reset` false or missing), no notification.
- **U4.** No invoice step: a linked draft invoice is not updated by an edit (cost and account can't change while it is linked, BUG-2929; title, description and dates are not copied to it).
- **U4a.** ✅ (manager `update_work_order` R3 / Q6, Gap log G8) A `title` in the request is dropped: the stored title is unchanged by the edit (outside a draft's type / target change, manager R15). The other fields of the same request (description, dates, …) are saved as usual.
- **U5.** An error of U2 rolls back the order edit too (TC3).

---

## `WorkOrderService.get_work_order(db, wo_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /work-orders/{id}/`)

- **G1.** Returns the order per `WorkOrderManager.get_work_order` (another workspace's id → 404 `Work order with ID <id> not found`; voided and completed included; [BUG-1279] a soft-deleted order → the same 404, *today returned*). TC6.

---

## `WorkOrderService.list_work_orders(db, workspace_id, work_order_type_id=None, wo_status=None, priority=None, factory_id=None, machine_id=None, work_order_template_id=None, planned_date_from=None, planned_date_to=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /work-orders/`, which maps the result per `_to_work_order_responses`)

- **L1.** Returns exactly `WorkOrderManager.list_work_orders` with the same arguments (live rows, filters, order: the manager's / DAO's rules). Own default `limit` 100; the endpoint enforces `0 ≤ skip`, `1 ≤ limit ≤ 1000`. TC6.

---

## `WorkOrderService.bulk_delete_future_recurrence_drafts(db, *, workspace_id, user_id, work_order_template_id, machine_id, after_date=None)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (`POST /work-orders/bulk-delete-future-drafts/`)

**Returns:** `BulkDeleteFutureRecurrenceDraftsResponse(deleted_count, deleted_ids)`, built after the commit; nothing is refreshed.

**Rules:**
- **B1.** The drafts are soft-deleted per `WorkOrderManager.bulk_delete_future_recurrence_drafts` (cutoff, BUG-2925; planned-date, id order) and committed.
- **B2.** `deleted_ids` = the manager's list in its order; `deleted_count` = its length. None found → `0`, `[]`, and the (empty) commit still happens.
- **B3.** [BUG-3227] (P3) For each deleted draft with a linked invoice: a `draft` invoice found in the workspace is deleted per `AccountInvoiceManager.delete_invoice`, the order's `invoice_id` cleared, and one event `invoice_voided`, description `Invoice unlinked — work order <number> deleted`, metadata `{"invoice_id": <old id>}`, `performed_by = user_id`. If any of them has a linked invoice found in the workspace that is not a draft → 400 `Work order <number> has a confirmed invoice — void the invoice first` (the first such draft in B2's order), nothing deleted. A linked id **not found in the workspace** (legacy, another workspace's invoice, HR-16) is left alone as invalid data: it is neither deleted, nor read, nor a reason to refuse; the draft is deleted anyway, its `invoice_id` stays as stored, and no `invoice_voided` event is written for it — as X3 (gap 5, decided by the coordinator 2026-11-22). The same holds for SE3. *(Today: invoices are never looked at; draft invoices stay linked to deleted drafts.)*
- **B4.** No notification.

---

## `WorkOrderService.sheet_entry(db, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /work-orders/sheet-entry/`)

**Returns:** the new order, committed and refreshed.

**Rules:**
- **SE1.** The order is created per `WorkOrderManager.sheet_entry` (machine / type checks, lines, approvers, template link and recurrence; BUG-2928, BUG-1206) and committed; any refusal, including one from the recurrence step, saves nothing (TC3).
- **SE2.** No invoice and no notification (also not to approvers named in the entry).
- **SE3.** [BUG-3227] (P3) When the entry re-plans a recurring template and drafts outside the new range are soft-deleted (manager `sync_recurrence_drafts_for_machine` R1), their invoices are handled as B3 (draft deleted and unlinked with the event; a non-draft invoice refuses the whole entry with the B3 message). The fix belongs in the manager. *(Today: their invoices are not looked at.)*

---

## `WorkOrderService.list_sheet_bundles(db, workspace_id, factory_id=None, machine_id=None, planned_date_from=None, planned_date_to=None, status=None, status_scope=None, work_order_type_id=None, priority=None, exclude_completed=False, search=None, skip=0, limit=50)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /work-orders/sheet/`)

**Returns:** `WorkOrderSheetListResponse(items, total, skip, limit, has_more)`.

**Rules:**
- **SB1.** `total` = `WorkOrderManager.count_sheet_orders` and the page = `list_sheet_orders(skip, limit)`, both with the same filters (what they match, their order and search escaping are the manager's / DAO's rules, BUG-2672 … 2674).
- **SB2.** One bundle per order of the page, in the page's order: `order` = the order mapped per `_to_work_order_responses` (one enrichment for the page); `items` = its live lines per `WorkOrderManager.get_items` (id order), each as `WorkOrderItemResponse`; `approvers` = a `WorkOrderApproversList` with two fields, `approvers` (the list) and `summary`, so a bundle `b` is read as `b.approvers.approvers[0]` and `b.approvers.summary`; `b.approvers.approvers` = its approver rows per `list_approvers`, each with `user_name` / `user_email` from the profile (`None` without one), `user_position` from the membership, `approver_slot`, `approved`, `approved_at`, `assigned_by`, `assigned_at`; `b.approvers.summary` = `approval_summary` of the order (`approved_count`, `required`, `met`; BUG-1204).
- **SB3.** `skip` and `limit` are echoed as given; `has_more` = `skip + len(items) < total`. Boundaries: 60 matching, skip 0, limit 50 → true; skip 50 (10 items) → false; skip beyond the total → `items = []`, false; no match → `total = 0`, `[]`, false.
- **SB4.** TC6: no commit, no rollback.

---

## `WorkOrderService.sheet_daily_counts(db, workspace_id, factory_id=None, machine_id=None, planned_date_from=None, planned_date_to=None, status=None, work_order_type_id=None, priority=None)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (`GET /work-orders/sheet/daily-counts/`)

- **SD1.** `WorkOrderSheetDailyCountsResponse(counts=…)` with exactly the map of `WorkOrderManager.sheet_daily_counts` (ISO date → count; `{}` when none; BUG-2675). TC6.

---

## `WorkOrderService.delete_work_order(db, wo_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (`DELETE /work-orders/{id}/`)

**Returns:** the soft-deleted order, committed and refreshed.

**Rules:**
- **X1.** The order is soft-deleted per `WorkOrderManager.delete_work_order` (404; 400 already deleted; 400 non-draft in production; consumed stock and machine status untouched outside production, Q7 there) and committed.
- **X2.** [BUG-2923] (P4) A linked invoice found in the workspace that is a `draft` is deleted per `AccountInvoiceManager.delete_invoice` (lines and events go with it; payment history → 400 `Invoice has payment history — confirm and void it instead`, BUG-639, and nothing is saved), the order's `invoice_id` is cleared, and one event `invoice_voided`, description `Invoice unlinked — work order <number> deleted`, metadata `{"invoice_id": <old id>}`, `performed_by = user_id`. Runs after the manager's checks (404, already deleted, production) pass. The id in the metadata is read before the invoice is deleted (BUG-3229 applies to this new path too: the fix must not repeat V4's order). *(Today: the invoice stays linked, verified.)*
- **X3.** [BUG-2923] A linked invoice found in the workspace that is not a draft (`confirmed`, or `voided` and still linked — legacy) → 400 `This work order has a confirmed invoice — void the invoice first`, nothing written. A linked id not found in the workspace (legacy, HR-16) → left alone, the delete goes ahead. *(Today: deleted, invoice kept.)*
- **X4.** No notification.

---

## `WorkOrderService.start_work_order(db, wo_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /work-orders/{id}/start/`)

**Returns:** the order, committed and refreshed.

**Rules:**
- **S1.** Started per `WorkOrderManager.start_work_order` (draft only; approvals met; stock consumed; machine to maintenance; lock BUG-2916) and committed; a failing line (e.g. insufficient stock) saves nothing (TC3).
- **S2.** No invoice step (an order with an account may start without an invoice; "complete" asks for it) and no notification.

---

## `WorkOrderService.complete_work_order(db, wo_id, workspace_id, user_id, completion_notes=None, machine_status=None, completed_by=None, completed_by_names=None, completed_by_user_ids=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /work-orders/{id}/complete/`, body `WorkOrderCompleteRequest`: `machine_status` `IDLE` | `OFF` | null)

**Purpose:** Finalize the invoice of outside work and complete a started order.

**Returns:** the order, committed and refreshed (or unchanged, C2).

**Rules (checks in this order):**
- **C1.** [BUG-2916] (H2; manager `finalize_completion` R18, G9) The order is read per `get_work_order` (404 missing / other workspace) with a row lock (`FOR UPDATE`) before any check. Exact clause per **L1** (Facts). *(Today: plain read, no lock.)*
- **C2.** Already `COMPLETED` → returned as it is, 200: no check, no write, no event, no notification, neither commit nor rollback (changes pending in the session stay pending). A second "complete" is harmless (manager FU-1 (c)).
- **C3.** Not `IN_PROGRESS` (`DRAFT`, `VOIDED`) → 400 `Work order must be in progress before it can be completed`, nothing written.
- **C4.** With an account (`account_id` not `None`) and no linked invoice → 400 `No invoice linked — create an invoice for this external work before completing`, nothing written.
- **C5.** With an account, the linked invoice not found in this workspace (legacy, HR-16) → 400 `Linked invoice not found`, nothing written; no id shown.
- **C6.** With an account, the linked invoice `voided` → 400 `Linked invoice was voided — cannot complete this order`, nothing written. (After BUG-2966 a void on the invoice page unlinks the order, so C4 answers instead; C6 is reached by older data.)
- **C7.** With an account, the invoice `draft` → confirmed (no cost check here, OQ-65 resolution: a legacy 0.00 draft is confirmed as any other) per `AccountInvoiceManager.confirm_invoice` (amount = sum of its lines, status `confirmed`, event `confirmed`; no lines → 400 `Add at least one line item before confirming`, BUG-628, nothing saved), then the `invoice_action` notifications of `notify_invoice_action` with action `confirmed` (Facts). From then on the invoice is frozen (O1, F2).
- **C8.** With an account, the invoice already `confirmed` (legacy: finalized on the invoice page before BUG-2969) → left as it is, no invoice notification; the order is still completed.
- **C9.** Without an account, the invoice is not looked at, also when one is linked (legacy only: after BUG-2929 an account can't be cleared while an invoice is linked). No invoice notification.
- **C10.** The order is completed per `WorkOrderManager.finalize_completion` with `completion_notes`, `machine_status`, `completed_by_user_id = completed_by`, `completed_by_names`, `completed_by_user_ids`, performer `user_id` (workers, stock at completion, machine status, `completed` event — the manager's rules); committed. A refusal there (e.g. an unknown worker) undoes the invoice confirm and its notifications (TC3).
- **C11.** `machine_status`: `None` or `""` → not given (the machine returns to its status before start, manager R7); a `MachineEventTypeEnum` value (`IDLE`, `OFF`; `RUNNING`, `MAINTENANCE` from code only) → that status; any other text → `ValueError`, nothing saved (the endpoint admits only `IDLE` / `OFF`).
- **C12.** Approvals are not checked here (they were checked at start and are frozen since, BUG-2931).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| C1 | HTTPException 404 | `Work order with ID <id> not found` |
| C3 | HTTPException 400 | `Work order must be in progress before it can be completed` |
| C4 | HTTPException 400 | `No invoice linked — create an invoice for this external work before completing` |
| C5 | HTTPException 400 | `Linked invoice not found` |
| C6 | HTTPException 400 | `Linked invoice was voided — cannot complete this order` |
| C7 | from `confirm_invoice` | e.g. 400 `Add at least one line item before confirming` |
| C10 | from `finalize_completion` | the manager's |
| C11 | `ValueError` | — |

**Side effects:** invoice confirmed (C7); notifications (C7); order, completers, stock, machine, events (manager); commit.

---

## `WorkOrderService.complete_work_order_as_planned(db, wo_id, workspace_id, user_id, completion_notes=None, machine_status=None, completed_by=None, completed_by_names=None, completed_by_user_ids=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /work-orders/{id}/complete-as-planned/`, body `WorkOrderCompleteAsPlannedRequest`)

**Purpose:** Start and complete a past-due draft in one step, back-dated to its planned day, finalizing its invoice.

**Returns:** the order, committed and refreshed (or unchanged, P2).

**Rules (checks in this order):**
- **P1.** [BUG-3222] (H1) The order is read per `get_work_order` (404) with a row lock (`FOR UPDATE`) before any check; this lock also serves the manager's `complete_as_planned` R11. Exact clause per **L1** (Facts). *(Today: plain read; the manager's lock would come after the invoice was already confirmed.)*
- **P2.** Already `COMPLETED` → returned as it is, 200, as C2 (no check, no write, no commit, no rollback).
- **P3.** [BUG-3223] (Q1) Not `DRAFT` → 400 `Work order must be in draft to complete as planned`, nothing written, before any invoice check. *(Today: the invoice checks P4 run first, so an `IN_PROGRESS` or voided order with an account and no invoice answers the P4 message (verified); with a draft invoice it is confirmed and then rolled back by the manager's same 400.)*
- **P4.** With an account: the invoice checks and the confirm of a draft, with its `confirmed` notifications, exactly as C4–C8 (same messages).
- **P5.** Without an account: as C9.
- **P6.** Then `WorkOrderManager.complete_as_planned` with the same arguments as C10 (planned date set, not in the future, approvals met — in that order; start side effects; back-dated to noon of the planned day); committed. A refusal there (no planned date, future date, approvals not met) undoes the invoice confirm and notifications (TC3); today the invoice errors of P4 therefore win over those refusals (error precedence only).
- **P7.** `machine_status` as C11.

**Errors:** P1 404; P3 400; P4 as C4–C7; the manager's (`Work order must have a planned date`, `Complete as planned is only allowed when the planned date is today or in the past`, `Assigned approvers must approve before work can be completed`); `ValueError` P7.

**Side effects:** as `complete_work_order`, plus the start side effects (manager).

---

## `WorkOrderService.void_work_order(db, wo_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /work-orders/{id}/void/`, body `WorkOrderVoidRequest`)

**Purpose:** Cancel an order that is not completed, return its consumed stock and remove its draft invoice.

**Returns:** the order, committed and refreshed.

**Rules (checks in this order):**
- **V1.** [BUG-3222] (H1) The order is read per `get_work_order` (404) with a row lock (`FOR UPDATE`) before any check; this lock also serves the manager's `void_work_order` R10. Exact clause per **L1** (Facts). *(Today: plain read; the invoice step runs before the manager's lock.)*
- **V2.** [BUG-3224] (Q2) The order's state is checked before any invoice step: `COMPLETED` → 400 `Cannot void a completed work order`; `VOIDED` → 400 `Work order is already voided`; nothing written. *(Today: these are the manager's checks after the invoice step; the outcome is the same 400 with everything rolled back, but after BUG-2730 a leftover draft on a completed order would answer the invoice-lock message instead.)*
- **V3.** No linked invoice → straight to V6.
- **V4.** The linked invoice is a `draft` (found in this workspace) → deleted per `AccountInvoiceManager.delete_invoice` (lines and events go with it; payment history → 400 `Invoice has payment history — confirm and void it instead`, BUG-639, nothing saved); the order's `invoice_id` = `NULL`, flushed; one event `invoice_voided`, description `Invoice unlinked — work order <work_order_number> voided`, `performed_by = user_id` (metadata: V4a).
- **V4a.** [BUG-3229] The `invoice_voided` event's metadata is `{"invoice_id": <id of the deleted invoice>}`: the id is read before the invoice is deleted. *(Today: `{"invoice_id": null}` — the id is read after `delete_invoice`, and the FK `ON DELETE SET NULL` has already cleared `wo.invoice_id`; verified by the executor, WOS-V-03.)* Decided by Claude under the reviewer's delegation (2026-11-22); twin of BUG-3185 / BUG-3070.
- **V5.** The linked invoice is `voided`, or is not found in this workspace (legacy) → not touched, and the order keeps `invoice_id`; the void goes ahead.
- **V5a.** [BUG-3224] (owner, OQ-62) The linked invoice is `confirmed` → 400 `This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order.`; nothing written: the order stays as it was (status, `invoice_id`, approvals, consumed stock), the invoice and its payments are unchanged, no event. Checked after V2. Once the invoice is voided on the invoice page, BUG-2966 unlinks the order and the void then runs as V3. *(Today: the order is voided, keeps `invoice_id`, and the invoice stays `confirmed` and payable — verified.)*
- **V6.** The order is voided per `WorkOrderManager.void_work_order` (consumed stock returned, machine status restored, approvals cleared, `VOIDED`, `voided_at`, `voided_by`, `void_note`, event `voided` after V4's event; [BUG-2918] blank note refused) and committed.
- **V7.** No notification is written.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| V1 | HTTPException 404 | `Work order with ID <id> not found` |
| V2 | HTTPException 400 | `Cannot void a completed work order` / `Work order is already voided` |
| V4 | from `delete_invoice` | e.g. 400 `Invoice has payment history — confirm and void it instead` |
| V5a | HTTPException 400 | `This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order.` — BUG-3224 |
| V6 | the manager's | e.g. 422 blank note (BUG-2918) |

**Side effects:** invoice deleted (V4); order row, events, stock, machine, approvers (manager); commit.

---

## `WorkOrderService.create_invoice_for_work_order(db, wo_id, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /work-orders/{id}/create-invoice/`)

**Purpose:** Make the draft payable invoice for outside work, from the order's account and cost.

**Returns:** the order (with `invoice_id` set), committed and refreshed.

**Rules (in this order):**
- **I1.** [BUG-3222] (H1) The order is read per `get_work_order` (404 missing / other workspace; BUG-1279 deleted) with a row lock (`FOR UPDATE`). Exact clause per **L1** (Facts). *(Today: no lock; two clicks at once make two drafts and the order keeps only the second.)*
- **I2.** An invoice already linked (any status) → 409 `Invoice already exists for this work order`, nothing written.
- **I3.** [BUG-3225] (P1) A `VOIDED` order → 400 `Work order is voided`; a `COMPLETED` order → 400 `Work order is completed`; nothing written; checked right after I1, before I2. *(Today: not checked; a voided order gets a new draft — verified.)* `DRAFT` and `IN_PROGRESS` orders may get an invoice.
- **I4.** No account (`None` or `0`) → 422 `Set an account on the work order before creating an invoice` (manager `resolve_invoice_account_id`), nothing written.
- **I4a.** [BUG-3228] (owner, OQ-65) The order's `cost` is `None`, `0` or below 0 → 422 `Set the work order's cost before creating an invoice`, nothing written (no invoice, no event, no notification; `invoice_id` stays `NULL`). Checked after I4. A cost above 0 (e.g. `0.01`) passes. `-5.00` is storable (no check constraint, Facts gap 6). *(Today: accepted; the invoice gets one 0.00 line, amount 0.00, `payment_status` `paid` — verified.)*
- **I5.** Approvals are not required.
- **I6.** The invoice is created per `AccountInvoiceManager.create_invoice` as a `payable` draft for the order's account with `order_type = "work_order"`, `order_id` = the order's id, `due_date` = the order's `end_date` (`NULL` when unset), `description` = `Auto-created from work order <work_order_number>`, `notes` = the order's `description`, `allow_payments = True`, no invoice / vendor numbers, no payment-lock reason. [BUG-3226] (P2) `invoice_date` = `utcnow().date()` *(today: `date.today()`, server local)*. [BUG-627] (P5) No `invoice_amount` is sent *(today: `0.00` is sent; after the BUG-627 schema change that is a 422, so the fix must drop it here too)*.
- **I7.** Account refusals of `create_invoice` pass through unchanged: deleted 400 `Cannot create invoice for deleted account`, inactive 400 `Cannot create invoice for inactive account`, `allow_invoices` false 403 `Invoices are not allowed for this account`. Any **404** from it (account missing or of another workspace — legacy; or, after BUG-625, the order itself, which I3 and BUG-1279 make unreachable) becomes 422 `Cannot create invoice: selected account was not found in this workspace` (the original as its cause); no id is shown. Other errors pass through unchanged.
- **I8.** The order's `invoice_id` = the new invoice (flushed); the invoice's lines are set per `sync_items_from_list` to exactly one line: `line_number 1`, `description` = the order's title, `item_id None`, `source_order_item_id None`, `source_order_item_type "wo_labor"`, `quantity 1`, `unit None`, `unit_price` = `line_subtotal` = the order's `cost` (always above 0 once BUG-3228 is fixed; *today* 0 when `None` or 0), no rounding (amount = that line; event `items_synced`). Verified: cost 750.50 → line `1.00 × 750.50`, amount 750.50.
- **I9.** One order event `invoice_created`, description `Invoice #<invoice id> created from work order`, metadata `{"invoice_id": <id>}`, `performed_by = user_id`.
- **I10.** Then the `invoice_action` notifications of `notify_invoice_action` with action `draft` (Facts; verified: the creator, also the actor, gets one); committed.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| I1 | HTTPException 404 | `Work order with ID <id> not found` |
| I2 | HTTPException 409 | `Invoice already exists for this work order` |
| I3 | HTTPException 400 | `Work order is voided` / `Work order is completed` — BUG-3225 |
| I4 | HTTPException 422 | `Set an account on the work order before creating an invoice` |
| I4a | HTTPException 422 | `Set the work order's cost before creating an invoice` — BUG-3228 |
| I7 | 400 / 403 pass-through; 404 → 422 | `Cannot create invoice: selected account was not found in this workspace` |

**Side effects:** invoice row, its `created` and `items_synced` events and line; order `invoice_id`; one order event; notifications; commit.

---

## `WorkOrderService.list_approvers(db, wo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /work-orders/{id}/approvers/`)

- **A1.** Returns `WorkOrderManager.list_approvers` (404; `(approver, profile, position)` tuples, approver DAO order, BUG-1200). TC6.

## `WorkOrderService.approval_summary_for(db, wo_id, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (same endpoint)

- **A2.** The order per `get_work_order` (404 missing / other workspace); returns `(approved_count, required, met)` per `WorkOrderManager.approval_summary` (BUG-1204). TC6.

---

## `WorkOrderService.add_approver(db, wo_id, user_id, workspace_id, assigned_by, approver_slot=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /work-orders/{id}/approvers/`)

**Returns:** the approver row, committed and refreshed.

**Rules:**
- **A3.** The approver is added per `WorkOrderManager.add_approver` (404; 400 completed / voided; [BUG-2931] 400 in progress; 400 not an active member; 409 duplicate; approval stamp recomputed).
- **A4.** Then notifications per `handle_add_approver` with actor `assigned_by`, the new approver's row id and the order re-read per `get_work_order`: the new approver gets `approval_assigned`; if the order is ready for approval every other pending approver gets `approval_pending`; if not ready the creator gets `section_confirm` with the gap text (`approvability_gap_reason`: blank title → `Work order setup is incomplete`; else no factory → `Set a factory before approvals can proceed`; `factory_id` is NOT NULL, so only the blank-title gap can be stored — Facts). An error there undoes the approver (TC3).

## `WorkOrderService.remove_approver(db, wo_id, user_id, workspace_id, performed_by)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (`DELETE /work-orders/{id}/approvers/{user_id}/`)

**Returns:** `None`.

- **A5.** The approver is removed per `WorkOrderManager.remove_approver` (404 `Approver not found`; 400 locked; [BUG-2931] 400 in progress; BUG-1204; stamp recomputed with actor `performed_by`) and committed. No notification, even when the removal makes approvals met.

## `WorkOrderService.approve_as_me(db, wo_id, user_id, workspace_id)` · `unapprove_as_me(db, wo_id, user_id, workspace_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST` / `DELETE /work-orders/{id}/approvers/me/approve/`)

**Returns:** the caller's approver row, committed and refreshed.

- **A6.** Approve = `WorkOrderManager.set_approval(approved=True)`, withdraw = `approved=False` (403 not an approver; 400 locked; [BUG-2931] 400 in progress; [BUG-2917] no-op when unchanged; lock BUG-2916), committed.
- **A7.** No invoice step and no notification, also when the approval makes the order ready to start.

---

## `WorkOrderService.list_events(db, wo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /work-orders/{id}/events/`)

- **N1.** Returns `WorkOrderManager.list_events` (404; `(event, profile or None)`, newest first). TC6.

---

## `WorkOrderService.add_item(db, item_in, workspace_id, user_id)` · `update_item(db, item_id, item_in, workspace_id, user_id)`
**Shape:** create / update · **Persistence:** writes · **Visibility:** public (`POST /work-orders/{id}/items/`, `PUT /work-orders/{id}/items/{item_id}/`)

**Returns:** the line, committed and refreshed.

- **M1.** The line is added / edited per `WorkOrderManager.add_item` / `update_item` (all their rules: guards, stock consumption on a started order, approval reset on a draft, BUG-2912 … 2916, BUG-2927) and committed; a stock refusal saves nothing (TC3).
- **M2.** No invoice step (the invoice line is the order's cost, not its parts) and no notification, also when the edit clears recorded approvals (unlike U2).

## `WorkOrderService.remove_item(db, item_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (`DELETE /work-orders/{id}/items/{item_id}/`)

- **M3.** The line is soft-deleted per `WorkOrderManager.remove_item` (stock returned on a started order; approvals reset on a draft) and committed; no notification, no invoice step.
- **M4.** Returns the line object without a refresh (`is_deleted = True`, `deleted_by`, `work_order_id` readable).

## `WorkOrderService.get_items(db, wo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /work-orders/{id}/items/`)

- **M5.** Returns `WorkOrderManager.get_items` (404; live lines in id order; BUG-1273). TC6.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 70–71 | no orders → empty enrichment | W1 |
| 77–89 | group by workspace; assignee / completer maps; missing order → `[]` | W2, W3 |
| 92–96 | `started_by` set; `completed_by` set and names empty | W4 |
| 99–101 | any profile id → read names | W4 |
| 116–117 | enrichment given / not | W5 |
| 119–123 | copy, lists from maps (`.get(..., [])`) | W6, W7 |
| 124–125 | `started_by` set | W8 |
| 126–129 | names truthy / `completed_by` set / neither | W9 |
| 135–136 | empty list | W11 |
| 137–141 | one enrichment, map each | W12 |
| 147–154 | create try / commit / refresh / except | E1, E2; TC1–TC4 |
| 160–169 | from template | T1, T2 |
| 176 | manager update | U1, U4 |
| 177–182 | `_approvals_reset` true / false / missing | U2, U3, U5 |
| 190–191 | get | G1 |
| 205–212 | list | L1 |
| 224–240 | bulk delete, response, no refresh | B1, B2, B4; (fix) B3 |
| 246–253 | sheet entry | SE1, SE2; (fix) SE3 |
| 270–295 | count, page | SB1 |
| 296–328 | per order: items, approvers (profile or None), summary | SB2 |
| 329–335 | `has_more` | SB3, SB4 |
| 349–360 | daily counts | SD1 |
| 362–370 | delete (no invoice step) | X1, X4; (fix) X2, X3 |
| 373–381 | start | S1, S2 |
| 392 | complete: read (no lock) | C1 |
| 393–394 | completed → return | C2 |
| 395–396 | not in progress | C3 |
| 398 | account set / not | C4–C9 |
| 399–403 | no invoice | C4 |
| 404–406 | invoice not found | C5 |
| 407–408 | invoice voided | C6 |
| 409–416 | invoice draft → confirm + notify; else skip | C7, C8 |
| 418–428 | finalize, `machine_status` truthy → enum | C10, C11, C12 |
| 442 | as planned: read (no lock) | P1 |
| 443–444 | completed → return | P2 |
| — | not-draft check before invoice (fix) | P3 |
| 446–464 | account / invoice checks, confirm, notify | P4, P5 |
| 466–476 | manager complete_as_planned | P6, P7 |
| 483 | void: read (no lock) | V1 |
| — | state checks before invoice (fix) | V2 |
| 484 | invoice linked / not | V3 |
| 485–486 | found and draft → delete; else untouched; confirmed → (fix) refuse | V4, V5, V5a |
| 487–495 | unlink, flush, event (id read after the delete) | V4, V4a |
| 497–499 | manager void, commit | V6, V7 |
| 508 | create invoice: read (no lock) | I1 |
| — | voided / completed not checked (fix) | I3 |
| 509–510 | invoice exists → 409 | I2 |
| 511 | no account → 422 | I4 |
| 513–527 | invoice fields, `invoice_amount`, `date.today()` | I6, I5, I4a |
| 528–538 | 404 → 422; other HTTPException re-raised | I7 |
| 540–557 | link, one line, `cost or 0` | I8 |
| 559–567 | event, notify | I9, I10 |
| 576–579 | list approvers | A1 |
| 581–583 | summary | A2 |
| 589–604 | add approver, re-read, notify | A3, A4 |
| 606–612 | remove approver, no return | A5 |
| 614–632 | approve / unapprove | A6, A7 |
| 635–636 | events | N1 |
| 639–657 | add / update item | M1, M2 |
| 659–666 | remove item, no refresh | M3, M4 |
| 668–669 | get items | M5 |
| every `except Exception` | rollback, re-raise | TC3, TC4 |

## Gap log
- G1 (work_order_service.cases.md gap 1) — Contradiction / intent, decided by the coordinator (2026-11-22) — Facts **L1** gives the exact clause: plain `FOR UPDATE` on the single-table `work_orders` read, `FOR UPDATE OF work_orders` equivalent and accepted, never `NOWAIT` / `SKIP LOCKED`; C1, P1, V1, I1 point to L1; the Notes' SQL-capture bullet widened to match.
- G2 (gap 2) — Fact — the three notification functions are module-level imports; patch target `app.services.work_order_service.<name>` (Facts).
- G3 (gap 3) — Fact — `utcnow` is not imported today (`date.today()`); the fix imports it from `app.utils.time`; patch target `app.services.work_order_service.utcnow`, `create=True` until then (Facts, Externals line).
- G4 (gap 4) — Fact — `_WorkOrderEnrichment` is importable from the module; frozen dataclass, fields `assignee_map`, `completer_map`, `profile_names` in that order (Facts).
- G5 (gap 5) — Intent, decided by the coordinator (2026-11-22), HR-16 — B3 (and SE3): another workspace's linked invoice is left alone as invalid data, the draft still deleted, `invoice_id` kept, no event, no refusal — as X3.
- G6 (gap 6) — Fact — `work_orders.cost` has no check constraint (marker_test, read-only); `-5.00` storable; I4a notes it.
- G7 (executor DISCREPANCY-7, 2026-11-22) — **Bug found by the executor, decided by Claude under the reviewer's delegation (2026-11-22)** — new V4a tagged BUG-3229 (void event metadata loses the invoice id; twin of BUG-3185); X2 states the same read order for the BUG-2923 fix; Branch map row 487–495 points to V4a.
- G8 (executor DISCREPANCY-3) — **Contradiction with the approved manager spec** — new U4a: `title` in an edit is always dropped (manager `update_work_order` R3, Q6), so the stored title stays; U4 unchanged.
- G9 (executor DISCREPANCY-2, -6; coordinator constraint facts) — **Fact** — Facts "Constraints": `work_order_type_id`, `factory_id`, `title` NOT NULL; table `inventory`. W6 restated (type always present; a soft-deleted type still gives its name, decided under delegation 2026-11-22). A4 names the two gap texts and that only the blank-title one is storable.
- G10 (executor DISCREPANCY-4) — **Fact** — SB2 now shows the nesting: `b.approvers` is a `WorkOrderApproversList(approvers, summary)`, read as `b.approvers.approvers[0]` / `b.approvers.summary`.
