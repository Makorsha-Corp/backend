# Spec — `app/managers/work_order_manager.py`

> **Status:** APPROVED (2026-11-21, apply-review; fill-gaps 2026-11-21, 15 gaps closed, see Gap log)
> **Source commit:** e48a092

> **Review round 2026-11-19 (describe, under the reviewer's delegation of 2026-11-19).** Every item that is not money, stock quantities, order workflow or security was decided by Claude under the delegation and is marked so; none of them is the owner's own answer. House-rule lines and precedent matches were pre-filled.
>
> **Apply-review 2026-11-21.** The owner answered OQ-W1 … OQ-W4 in chat on 2026-11-21 (recorded as OQ-56 … OQ-59 in `docs/testing/owner-questions.md`). House-rule lines, precedent matches and delegated decisions stand as confirmed. Bugs BUG-2912 … BUG-2931 (this spec's block) are final and logged in `docs/testing/bugs.md`.

> **Owner decisions applied, not asked again:** (1) OQ-10 (owner 2026-11-04, BUG-1884): when the order's project component is not in the order's workspace, no component log entry is written and the step goes on. (2) The invoice freeze (owner 2026-11-14, BUG-2730 … BUG-2736): a completed work order's invoice is frozen; this manager already refuses every edit, line change and void of a completed order, so the freeze needs nothing new here (`AccountInvoiceManager` F2 reads `status = "COMPLETED"`). (3) Machine O4 / BUG-975 (owner 2026-10-30): open work orders follow a moved machine to its new factory, lines and approvals unchanged; O5: a work order on a deleted machine is refused at start. (4) BUG-1201 / BUG-1204 / BUG-1206 (owner 2026-11-01), BUG-1883 (OQ-6), OQ-21 (BUG-2346), OQ-14 / OQ-15 (calendar only). (5) HR-15: money rounds half up.

> **Deferred areas.** **Production deferred:** this module does not touch production batches, formulas or lines. **Projects (revisit after launch):** rules that concern a project component (the component as a target, its title, its activity-log entries) describe today's behaviour and carry the tag *revisit after launch*; no bug is logged for them, except BUG-1884, an existing owner decision.

> **Verified PASS collaborators, referenced not restated:** `tests/unit/dao/work_order.spec.md`, `work_order_item.spec.md`, `work_order_approver.spec.md`, `work_order_assignee.spec.md`, `work_order_completer.spec.md`, `work_order_event.spec.md`; `tests/unit/managers/inventory_movements.spec.md` (`post_stock_out`, `post_stock_in`, `item_name`), `machine_manager.spec.md` (`create_machine_event`), `machine_activity_manager.spec.md` (`log_event`, `get_latest_status`, `status_from_activity`), `project_component_activity_manager.spec.md` (`log_event`), `work_order_template_manager.spec.md` (`get_template`, `get_items`, `get_approvers`, `generate_drafts_for_anchored_range`); `tests/unit/utils/work_order_workers.spec.md`, `work_order_recurrence.spec.md`, `order_catalog_items.spec.md`.

> **Verified by running** (my own scripts `v_wo.py`, `v_wo7.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\ordersdesc\work_order\`, one outer transaction on `marker_test`, each case in a savepoint, all rolled back, nothing committed): a new order is stamped `auto_approved`; a machine of another factory than the order's is accepted; a cost of `-5` is stored; a no-op update stamps `updated_by`; a title typed at create is replaced by the derived title when the draft's machine changes; an `INSTALL` line on a draft whose machine is then removed is consumed at start and installed nowhere at completion (storage 10 → 8, no machine row); a `2.5` inventory line is accepted on a draft and refused at start; a `0` line starts; a `-2` line starts and **raises** storage from 10 to 12; consume 3 → adjust to 4 → void gives costs 2.50 / 7.50 → 2.50 / 10.00 and status `VOIDED`, void note `"  "` stored; an approval is withdrawn and an approver added on an `IN_PROGRESS` order; complete-as-planned in the future refused, in the past back-dated to noon (`started_at` = `completed_at`); a `REPLACE` line with nothing to remove logs `item_replace_degraded`; `end_date` before `planned_date` stored; `required_approvals = -1` gives `(0, -1, True)`; a soft-deleted order is returned by `get_work_order` and can be started; editing `description` in progress is refused with the four-field message. **Read, not run:** `WorkOrderService` (all callers), `approval_notification_service`, `attachment_manager` (`log_event`), the invoice path, recurrence seeding, the template path, the sheet path. **Not run:** HTTP; two concurrent transactions; intended behaviour of the bugs.

## Review
> All items answered (owner 2026-11-21 for OQ-W1 … OQ-W4; the rest by house rule, precedent or the reviewer's delegation of 2026-11-19).

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| OQ-W1 (OQ-56) | Cost and account can still change on a draft order after its invoice was made; the invoice keeps the old amount and account | bug — BUG-2929 (refuse while a non-voided invoice is linked) | **owner**, 2026-11-21 |
| OQ-W2 (OQ-57) | Removing the machine from a draft with Install / Replace / Borrow parts makes those parts vanish at completion | bug — BUG-2930 (refuse the change; another machine is fine) | **owner**, 2026-11-21 |
| OQ-W3 (OQ-58) | Approvers and approvals can still change after work has started | bug — BUG-2931 (frozen once started) | **owner**, 2026-11-21 |
| OQ-W4 (OQ-59) | A part removed by a Replace goes to damaged stock at zero value | intended | **owner**, 2026-11-21 |
| P1 | Line quantity ≤ 0, negative cost, negative required approvals accepted | bug — BUG-2912 | Claude, precedent BUG-362 / BUG-2364 |
| P2 | Quantity and cost with more than 2 decimals accepted | bug — BUG-2913 | Claude, precedent BUG-021 / BUG-2363 |
| P3 | A fractional quantity on a stock line is accepted until the order starts | bug — BUG-2914 | Claude, precedent BUG-725 |
| P4 | Repeating an approval re-stamps it and logs it again | bug — BUG-2917 | Claude, precedent BUG-757 |
| P5 | A blank void reason is accepted | bug — BUG-2918 | Claude, precedent BUG-605 / BUG-626 |
| P6 | Planned date, end date and cost cannot be cleared | bug — BUG-2919 | Claude, precedent BUG-942 / BUG-608 |
| P7 | A deleted factory, machine or account can be put on an order | bug — BUG-2920 | Claude, precedent BUG-2341 / BUG-2362 |
| P8 | A template whose approvers have all left gives an order approved at once | bug — BUG-2922 | Claude, precedent BUG-1204 / BUG-2346 |
| P9 | The recurrence bulk delete takes "today" from the server's local clock | bug — BUG-2925 | Claude, precedent BUG-2673 |
| Q1 | The order's machine may sit in another factory than the order | bug — BUG-2921 | Claude, delegated (follows owner O4) |
| Q2 | Deleting a draft leaves its draft invoice linked; voiding deletes it | bug — BUG-2923 | Claude, delegated |
| Q3 | The in-progress lock message names four fields; six are locked | bug — BUG-2924 | Claude, delegated |
| Q4 | An end date before the planned date is accepted | bug — BUG-2926 | Claude, delegated |
| Q5 | The planning sheet can place an inactive template | bug — BUG-2928 | Claude, delegated |
| Q6 | A title is not editable after creation, and a draft's typed title is replaced when its type or target changes | intended | Claude, delegated |
| Q7 | Outside production any order, not only drafts, can be deleted | intended | Claude, delegated |
| Q8 | `remove_item`'s second "completed or voided" check can never be reached | remove | Claude, delegated |
| Q9 | After completion a machine returns to the status it had before start, even `MAINTENANCE` | intended | Claude, delegated |

Decided by house rules: no-op updates stamp and reset approvals (BUG-2915, HR-9); unlocked state transitions (BUG-2916, HR-10); a line's source location may name another workspace's factory or machine (BUG-2927, HR-16). Existing bugs carried here as rules: BUG-1016, BUG-1040, BUG-1192, BUG-1204, BUG-1206, BUG-1228, BUG-1273, BUG-1279, BUG-1884.

### House-rule violations — applied automatically
> Overwrite an answer only if the house rule should NOT apply here.

- **HR-9** `update_work_order` R20, R21; `update_item` R10 — `updated_by` is written whenever the request carries a field, even when every value equals the stored one (verified). Worse, a draft's recorded approvals are cleared (and the service sends "re-approve" notifications) when a details field is **sent** with its current value, and `update_item` logs `item_updated` and clears approvals for a no-op line edit. Intended: nothing is written, no event, no approval reset, when no field changes value (BUG-740 precedent covers the approval-reset part).
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-2915 (pattern `audit-stamp-on-noop`). Rules: `update_work_order` R12, R20; `update_item` R10.
- **HR-10** `start_work_order` R9, `complete_as_planned` R11, `finalize_completion` R18, `void_work_order` R10, `set_approval` R9, `add_approver` R8, `remove_approver` R5 (added in fill-gaps, G15), `add_item` R14, `update_item` R11, `remove_item` R9 — every check-then-change on stock or approvals reads the order (and line) without a row lock. Two "start" or two "void" requests can both post stock; two completions (the service checks `IN_PROGRESS` before calling `finalize_completion`) can both install / return parts; a line edit can race a start. Intended: the work order row is read `FOR UPDATE` before the state check (and the line row in the item methods); the loser sees the new state and gets the method's normal wrong-state error.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2916 (pattern `hr-10-unlocked-state-transition`, as BUG-720 bundles seven methods). Rules as listed above.
- **HR-16** `add_item` R6a, `update_item` R7a — a line's `source_location_id` is stored unchecked on a draft: another workspace's factory or machine is accepted and refused only later, at start, by the stock posting (404). Intended: an inventory line whose source is not a live factory (`storage`) or live machine (`machine`) of the order's workspace is refused at add / update with 404 `Factory with ID <id> not found` / `Machine with ID <id> not found`, nothing written; `source_location_type` other than `storage` / `machine` → 400 `Unsupported source location type: <type>` (the wording of `post_stock_out` R4).
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2927 (pattern `cross-workspace-link-not-refused`). Rules: `add_item` R6a, `update_item` R7a.
- **HR-15** `_consume_item` R5, `_adjust_consumed_item_quantity` R6, R7 — `quantize(Decimal('0.01'))` rounds half to even. Already logged: **BUG-1040** names lines :762, :859, :860, :883 of this file. No new ID.
**Answer:** bug — per HR-15 (house rule; existing BUG-1040)
- **HR-4** `get_work_order` R2 — a soft-deleted order is returned (verified: it can even be started). Already logged: **BUG-1279**. `get_items` R3 (`include_deleted` unreachable): **BUG-1273**. No new ID.
**Answer:** bug — per HR-4 (house rule; existing BUG-1279, BUG-1273)
- **HR-16** `log_event` R2 — any work order id is stored. Already logged: **BUG-1192**. `create_work_order` R9 / `update_work_order` R14 / `add_item` R12 (foreign machine, component, item): **BUG-1016**. No new ID.
**Answer:** bug — per HR-16 (house rule; existing BUG-1192, BUG-1016)

Checked and **not** a new line here: **HR-1** — `title` is trimmed and never blank (a blank one is derived, `create_work_order` R4); description, assigned-to text and notes are free text, not names. **HR-2, HR-3** — no uniqueness on names; numbers are the DAO's (BUG-2676, BUG-2677). **HR-5, HR-6, HR-7, HR-8** — lists are the DAO's: order BUG-2670, BUG-1272, BUG-1200; sheet search BUG-2672; endpoint `limit` 1…1000. **HR-11 … HR-14** — no external system, no batch job (the notification calls are the service's). **HR-16** — the template link on a sheet entry is refused through `get_template` (`sheet_entry` R9); `replaced_item_id`, factory, type and account are checked in the workspace; approvers must be active members of it.

**Permission checks:** none in this manager. `set_approval` only checks that the caller is an approver of the order; everything else is open to any active member (endpoint dependency).

### Precedent matches — confirmed

### P1. Line quantity ≤ 0, negative cost and negative required approvals are accepted — 🐞 BUG-2912
**Background:** `WorkOrderItemCreate.quantity` (default 1) and `WorkOrderItemUpdate.quantity`, the sheet line `quantity`, `cost` on create / update / sheet entry, and `required_approvals` on update are plain numbers with no range.
**What happens today:** Verified: a stock line of `0` starts (a zero-quantity consumption row is written); a line of `-2` starts and **raises** storage stock from 10 to 12; a cost of `-5` is stored; `required_approvals = -1` makes the order "0 of -1, met".
**Example:** A technician types `-2` bolts by mistake on WO-2026-014 and starts it: the stores now show 2 more bolts than they hold.
**Rules affected:** `add_item` R5a, `update_item` R7b, `create_work_order` R3a, `update_work_order` R9a, `approval_summary` R3
**Answer:** bug — per BUG-362 / BUG-2364 precedent: line quantity must be > 0, cost ≥ 0, `required_approvals` null or ≥ 0 (0 is the designed explicit waiver, BUG-1204); anything else 422 in the schemas (`WorkOrderItemCreate`, `WorkOrderItemUpdate`, `WorkOrderSheetItemLine`, `WorkOrderCreate`, `WorkOrderUpdate`, `WorkOrderSheetEntryCreate`), nothing stored (precedent — confirmed 2026-11-21)

### P2. Quantity and cost with more than 2 decimals are accepted — 🐞 BUG-2913
**Background:** `quantity` and `cost` are `Numeric(15,2)` columns; Postgres rounds longer values on storing, after the manager has used the unrounded value in messages and checks.
**What happens today:** `quantity: 1.005` passes the schema and is stored `1.01` (or `1.00`); `cost: 99.999` is stored `100.00`; ≥ 10^13 fails at flush (500).
**Example:** A line of 0.004 litres is accepted and stored as `0.00`; the order then fails at start ("fractional quantity" is not raised for 0, it consumes nothing).
**Rules affected:** `add_item` R5a, `update_item` R7b, `create_work_order` R3a, `update_work_order` R9a
**Answer:** bug — per BUG-021 / BUG-2363 precedent: quantity and cost with more than 2 decimal places or more than 13 integer digits are refused with 422 (same schemas as P1) (precedent — confirmed 2026-11-21)

### P3. A fractional quantity on a stock line is accepted until the order starts — 🐞 BUG-2914
**Background:** Stock is consumed in whole units. A line that uses inventory is consumed at start (or at once when added to a started order); a fractional quantity then fails with 400.
**What happens today:** Verified: a `2.5` stock line is added to a draft; starting fails with `Item line <id> has a fractional quantity; inventory consumption requires whole units`, so the order cannot start until the line is edited.
**Example:** The sheet saves "Grease 2.5 kg" from storage; on the day, Start always fails.
**Rules affected:** `add_item` R5b, `update_item` R7c
**Answer:** bug — per BUG-725 precedent: a line with `uses_inventory = true` and a fractional quantity is refused when added or updated, with the same 400 text (`Item line … has a fractional quantity; inventory consumption requires whole units`, the id replaced by the item name for a new line: `<item name> has a fractional quantity; …`), nothing written; lines that do not use inventory may stay fractional (precedent — confirmed 2026-11-21)

### P4. Repeating an approval re-stamps it and logs it again — 🐞 BUG-2917
**Background:** Each approver row has `approved` and `approved_at`.
**What happens today:** `set_approval` always writes both and logs `approved` / `approval_withdrawn`, even when the row already has that value.
**Example:** Rahim approved on 1 March and clicks Approve again on 5 March: his approval now reads 5 March and the log shows two approvals.
**Rules affected:** `set_approval` R6
**Answer:** bug — per BUG-757 precedent: setting the value the approver already has is a no-op: no write, no event, row returned unchanged (precedent — confirmed 2026-11-21)

### P5. A blank void reason is accepted — 🐞 BUG-2918
**What happens today:** `WorkOrderVoidRequest.void_note` is a plain `str`; verified `"  "` is stored and logged as `Reason:   `.
**Example:** WO-2026-020 is voided with an empty reason box; the log reads "voided. Reason: ".
**Rules affected:** `void_work_order` R8
**Answer:** bug — per BUG-605 / BUG-626 precedent: `void_note` is trimmed and must not be blank (422 in `WorkOrderVoidRequest`) (precedent — confirmed 2026-11-21)

### P6. Planned date, end date and cost cannot be cleared — 🐞 BUG-2919
**Background:** The update drops every field sent as `null`, except `machine_id`, `project_component_id`, `account_id` and `required_approvals`, which the code re-adds on purpose.
**What happens today:** `{"end_date": null}`, `{"planned_date": null}` or `{"cost": null}` changes nothing and answers 200.
**Example:** A draft was planned for 10 March by mistake; the planner clears the date to leave it unscheduled — it stays on 10 March.
**Rules affected:** `update_work_order` R4
**Answer:** bug — per BUG-942 / BUG-608 precedent: an explicit `null` for `planned_date`, `end_date` or `cost` clears it (subject to the same locks: `cost` is locked in progress) (precedent — confirmed 2026-11-21)

### P7. A deleted factory, machine or account can be put on an order — 🐞 BUG-2920
**Background:** Factories, machines and accounts are soft-deleted. The lookups here are raw. A deleted work order type is already BUG-1228.
**What happens today:** `create_work_order`, `update_work_order` (account), `sheet_entry` and `create_work_order_from_template` (machine) accept deleted rows. An order on a deleted machine then fails at start (`Cannot create event for a deleted machine`, machine O5).
**Example:** Machine "Old press" was deleted last month; a sheet entry for it is saved as a draft that can never be started.
**Rules affected:** `create_work_order` R1a, R3, `update_work_order` R11, `create_work_order_from_template` R2, `sheet_entry` R1
**Answer:** bug — per BUG-2341 / BUG-2362 precedent: a soft-deleted factory, machine or account is treated as not found (the call site's existing 404 text), nothing written; existing orders keep theirs (precedent — confirmed 2026-11-21)

### P8. A template whose approvers have all left gives an order approved at once — 🐞 BUG-2922
**Background:** OQ-21 (BUG-2346) stops a template that requires approval from having no approvers. But approvers copied to the order must be active members; inactive ones are skipped one by one. The approver DAO spec's FU-5 asked this spec to carry the case.
**What happens today:** If every approver of a "requires approval" template has left the workspace, the new order has none: 0 of 0, met, stamped `Ready to start — no approval required`.
**Example:** Template "Monthly boiler check" requires Karim's approval; Karim left. Next month's draft can be started by anyone with no approval.
**Rules affected:** `create_work_order_from_template` R9
**Answer:** bug — per BUG-1204 / BUG-2346 precedent: when the template requires approval and no approver could be copied, the order is not approved until an approver is added and approves (e.g. `required_approvals = 1`), and the event `approvals_needed` "Template approvers are no longer members — add an approver" is logged (precedent — confirmed 2026-11-21)

### P9. The recurrence bulk delete takes "today" from the server's local clock — 🐞 BUG-2925
**What happens today:** With no `after_date`, the cutoff is `date.today()` (server local time).
**Example:** At 01:00 in Dhaka (19:00 UTC the day before) the cutoff is already the next day in local time on a Dhaka server, and drafts dated "today" (UTC) are kept or deleted depending on the server's zone.
**Rules affected:** `bulk_delete_future_recurrence_drafts` R1
**Answer:** bug — per BUG-2673 precedent: the cutoff is `utcnow().date()` (precedent — confirmed 2026-11-21)

### Owner questions — answered by the owner, 2026-11-21

### OQ-W1 (OQ-56). Cost and account can still change after the order's invoice was made — the invoice keeps the old figures — 🐞 BUG-2929
**Module / kind:** `update_work_order` (money). Reached through `PUT /work-orders/{id}/`.
**Background:** A work order for an outside customer or supplier has an `account` and a `cost`. "Create invoice" makes a draft invoice for that account with one line at the order's cost at that moment. Cost and account are locked once work starts, but not on a draft. The invoice is confirmed only when the order is completed (or by hand on the invoice page).
**What happens today:** On a draft order with an invoice, cost and account can still be edited. The invoice keeps the old amount and stays on the old account; completing the order confirms that old invoice.
**Example:** WO-2026-031 for "Rahman Traders" costs 5,000; the invoice is made for 5,000. The price is renegotiated to 4,200 and the order edited. On completion the invoice is confirmed at 5,000 to Rahman Traders, although the order says 4,200.
**Rules affected:** `update_work_order` R12a
**Recommended answer:** (a) bug — refuse.
**Options, in plain words:**
- **(a) Refuse the change (recommended).** While the order has an invoice that is not voided, cost and account cannot be changed: the user sees "This work order has an invoice. Delete the draft invoice first to change the cost or account." In the example, the user deletes the 5,000 draft invoice, sets 4,200, and creates a new invoice for 4,200. Simple and nothing can drift apart.
- **(b) Keep the draft invoice in step.** While the invoice is still a draft, changing the cost rewrites its line to the new amount and changing the account moves it to the new account; once the invoice is confirmed, the change is refused as in (a). In the example the invoice becomes 4,200 automatically. Less work for the user, but invoices change without anyone touching them.
- **(c) Keep today's behaviour.** The order and its invoice are separate; whoever changes the price must also fix the invoice. In the example the customer is billed 5,000 unless someone notices.
**Answer:** owner, 2026-11-21 (OQ-56): option (a) — bug, refuse the change while the order has an invoice that is not voided.
**Resolution:** a change of `cost` or `account_id` (a real change of value, HR-9) on an order whose linked invoice is not voided is refused with 400 `This work order has an invoice. Delete the draft invoice first to change the cost or account.`, nothing written. No invoice, or a voided one, → allowed as today. Rules: `update_work_order` R12a.

### OQ-W2 (OQ-57). Removing the machine from a draft with Install / Replace / Borrow parts makes those parts vanish at completion — 🐞 BUG-2930
**Module / kind:** `update_work_order`, `finalize_completion` (stock quantities).
**Background:** A part line can be Consume (used up), Install (taken from stores and fitted on the machine), Replace (fitted, and the old part taken off the machine) or Borrow (taken and given back at the end). Install / Replace / Borrow can only be added to an order that targets a machine. The stock leaves the source when work starts; the move onto the machine (or back, for Borrow) happens at completion, only if the order still has a machine.
**What happens today:** On a draft, the machine can be removed (or swapped for a project component) after such lines were added. Verified: 2 bolts on an Install line, machine removed, order started and completed → stores 10 → 8, and the bolts are on no machine. A borrowed tool is never given back.
**Example:** WO-2026-040 installs 2 bearings on "Lathe 3" and borrows a puller. The planner retargets it to "no machine" before starting. After completion the stores are short 2 bearings and the puller, and no machine shows the bearings.
**Rules affected:** `update_work_order` R13a; `finalize_completion` R10
**Recommended answer:** (a) bug — refuse the change.
**Options, in plain words:**
- **(a) Refuse the change (recommended).** While the order has Install, Replace or Borrow lines, its machine cannot be removed or swapped for a project component: "Remove the Install / Replace / Borrow parts first — they need a machine." Switching to another machine stays allowed (the parts go to the new machine). In the example the planner must first change those lines.
- **(b) Turn them into Consume.** Removing the machine silently changes those lines to Consume. In the example the bearings and puller are then booked as used up, which at least says what happened to the stock, but the puller is still lost.
- **(c) Keep today's behaviour.** The stock leaves the stores and is recorded nowhere.
**Answer:** owner, 2026-11-21 (OQ-57): option (a) — bug, refuse the change; switching to another machine stays allowed.
**Resolution:** while the order has a live `INSTALL`, `REPLACE` or `BORROW` line, an update that sets `machine_id` to `null`, or sets a `project_component_id` (which clears the machine), is refused with 400 `Remove the Install / Replace / Borrow parts first — they need a machine`, nothing written. A different non-null machine is accepted (the parts go to the new machine). `finalize_completion` R10 then cannot arise through the API. Rules: `update_work_order` R13a; `finalize_completion` R10.

### OQ-W3 (OQ-58). Approvers and approvals can still change after work has started — 🐞 BUG-2931
**Module / kind:** `add_approver`, `remove_approver`, `set_approval` (order workflow).
**Background:** Approvals only matter before start: Start (and "complete as planned") is refused until the approvals are met. After start, the order's "approved" stamp is not recomputed.
**What happens today:** Verified: on an `IN_PROGRESS` order an approver withdrew their approval and a new approver was added; both were accepted and logged. The order keeps its "approved" stamp, and the approvers panel now shows an approval missing on work that already started.
**Example:** WO-2026-050 was approved by Karim and started. A week later Karim clicks "Withdraw approval": the order's history now says it was never approved by him, while the work went ahead on his approval.
**Rules affected:** `add_approver` R2a, `remove_approver` R2a, `set_approval` R3a
**Recommended answer:** (a) bug — frozen once started.
**Options, in plain words:**
- **(a) Frozen once work starts (recommended).** After Start, approvers cannot be added or removed and approvals cannot be given or withdrawn: "Work has started — approvals can no longer change." The record shows exactly who approved before the work began. In the example, Karim's click is refused.
- **(b) Allow it, but only as a note.** Changes are still allowed and logged, and the screen marks them "after start". The record stays editable, so the history is less clear.
- **(c) Keep today's behaviour.** Anything goes; the approvals panel may disagree with what actually allowed the work to start.
**Answer:** owner, 2026-11-21 (OQ-58): option (a) — bug, approvals are frozen once work starts.
**Resolution:** on an `IN_PROGRESS` order, adding or removing an approver and approving or withdrawing are refused with 400 `Work has started — approvals can no longer change`, nothing written. As a direct consequence (decided by Claude, 2026-11-21: the approval count is part of the approval record the owner froze), `required_approvals` is no longer editable in progress either: it joins the same 400 in `update_work_order`. Rules: `add_approver` R2a, `remove_approver` R2a, `set_approval` R3a, `update_work_order` R7, R7a.

### OQ-W4 (OQ-59). A part taken off a machine by a Replace goes to damaged stock at zero value — ✅ intended
**Module / kind:** `_apply_item_completion` (stock value / money).
**Background:** On completion a Replace line takes the old part off the machine (at the machine's average cost for that part) and puts it into the factory's damaged stock, and fits the new part. Damaged stock has its own average cost.
**What happens today:** The removed part enters damaged stock at a unit cost of 0.00, so its value leaves the books when it comes off the machine; the damaged bucket's average cost drops.
**Example:** A belt worth 300.00 on "Lathe 3" is replaced. The old belt shows in damaged stock as 1 belt at 0.00; the 300.00 is gone from the machine and appears nowhere.
**Rules affected:** `_apply_item_completion` R6
**Recommended answer:** intended — a part that was replaced is worn out and worth nothing; damaged stock counts pieces, not value.
**Options, in plain words:**
- **(a) Zero value (recommended, today's behaviour).** The removed part is counted in damaged stock but valued at nothing. In the example, damaged stock shows 1 belt, value 0.00. Matches what a worn part is worth.
- **(b) Carry its value.** The removed part enters damaged stock at the machine's average cost (300.00), so the value moves with it and can be written off later on purpose. In the example damaged stock shows 1 belt worth 300.00.
**Answer:** owner, 2026-11-21 (OQ-59): intended — zero value, today's behaviour. No bug. Rules: `_apply_item_completion` R6 ✅.

### Decided under the reviewer's delegation (2026-11-19)

### Q1. The order's machine may sit in another factory than the order — 🐞 BUG-2921
**Background:** Every work order has a factory (where its stock comes from by default and where it is listed) and optionally a machine. The sheet and template paths take the factory from the machine. The owner decided (machine O4, BUG-975) that open orders follow their machine when it moves factory.
**What happens today:** `POST /work-orders/` with a machine of factory F2 and `factory_id` F1 is accepted (verified). Changing a draft's machine keeps the old factory.
**Example:** WO-2026-060 is for "Lathe 3" (Gazipur) but filed under Savar; it shows on the Savar sheet and its replaced parts go to Savar's damaged stock.
**Rules affected:** `create_work_order` R1b, `update_work_order` R13b
**Answer:** bug — on create, a machine whose factory is not `factory_id` is refused with 400 `Machine <name> belongs to another factory`, nothing written; on a draft update that changes the machine, the order's `factory_id` becomes the new machine's factory (and the `updated` event lists the change, label `Factory`), as BUG-975 moves it (decided by Claude under the reviewer's delegation, 2026-11-19: follows owner O4; not money or stock — the lines keep their sources, O4 SP-1)

### Q2. Deleting a draft leaves its draft invoice linked; voiding deletes it — 🐞 BUG-2923
**Background:** `WorkOrderService.void_work_order` deletes the order's draft invoice and logs `invoice_voided` before voiding. `delete_work_order` (here and in the service) does nothing with the invoice.
**What happens today:** A deleted draft keeps `invoice_id`; its draft invoice stays on the account's list and can be confirmed and paid for an order nobody can see.
**Example:** WO-2026-070 had a 2,000 draft invoice; the order is deleted. The invoice still waits on the account page and is confirmed by mistake.
**Rules affected:** `delete_work_order` R5
**Answer:** bug — deleting an order does what voiding does: a linked draft invoice is deleted and `invoice_id` cleared, with the same `invoice_voided` event; a linked invoice that is not a draft (confirmed by hand) refuses the delete with 400 `This work order has a confirmed invoice — void the invoice first`. Fix in `WorkOrderService.delete_work_order`, as the void path (decided by Claude under the reviewer's delegation, 2026-11-19: consistency with the sibling path; a draft invoice carries no money in totals, BUG-634)

### Q3. The in-progress lock message names four fields; six are locked — 🐞 BUG-2924
**What happens today:** Once started, type, description, priority, machine / component, cost and account are locked, but the message says `structural fields (target, type, cost, account) are locked` (verified with a description edit).
**Example:** A supervisor edits the description of a started order and is told only target, type, cost and account are locked.
**Rules affected:** `update_work_order` R8
**Answer:** bug — the message names every locked field: `Work order is in progress — type, description, priority, target, cost and account are locked`; the lock itself is unchanged (decided by Claude under the reviewer's delegation, 2026-11-19)

### Q4. An end date before the planned date is accepted — 🐞 BUG-2926
**What happens today:** Verified: planned 10 May, end 1 May stored. The calendar then shows an order ending before it starts.
**Example:** A two-day overhaul planned 10 May is given end date 1 May by a typo; the planning view draws nothing sensible.
**Rules affected:** `create_work_order` R3b, `update_work_order` R9b
**Answer:** bug — when both are set (on update: the merged values), `end_date` before `planned_date` is refused with 422 `End date cannot be before the planned date`, nothing written; equal dates allowed (decided by Claude under the reviewer's delegation, 2026-11-19)

### Q5. The planning sheet can place an inactive template — 🐞 BUG-2928
**Background:** "Create from template" refuses an inactive template (400 `Template is inactive`). The sheet entry only links the template and, for a recurring one, generates drafts (which then fail with the same 400).
**What happens today:** A sheet entry naming an inactive, non-recurring template is saved and linked to it.
**Example:** Template "Old greasing round" was switched off; a planner picks it on the sheet and the order is filed under it.
**Rules affected:** `sheet_entry` R9
**Answer:** bug — a sheet entry with an inactive template is refused with 400 `Template is inactive`, nothing written, as the from-template path (decided by Claude under the reviewer's delegation, 2026-11-19)

### Q6. A title is not editable after creation, and a draft's typed title is replaced when its type or target changes — ✅ intended
**What happens today:** `title` in `PUT /work-orders/{id}/` is dropped without a message. On a draft, changing type, machine or component rewrites the title to `<type> — <target>`, replacing a title typed at create (verified). The web app never edits the title.
**Example:** "Fix leaking seal" on Lathe 3 is moved to Lathe 4 and becomes "Repair — Lathe 4".
**Rules affected:** `update_work_order` R3, R15
**Answer:** intended — the title is the system's label of type and target; descriptions carry the user's words (decided by Claude under the reviewer's delegation, 2026-11-19)

### Q7. Outside production any order can be deleted — ✅ intended
**What happens today:** Only drafts can be deleted when `ENVIRONMENT == "production"` and `WORK_ORDER_ALLOW_DEV_DELETE` is false; otherwise any status, without undoing consumed stock or the machine status.
**Answer:** intended — a development / test switch; production stays drafts-only (decided by Claude under the reviewer's delegation, 2026-11-19). Note for the owner's notes: `WORK_ORDER_ALLOW_DEV_DELETE` must stay off on Railway.

### Q8. `remove_item`'s second "completed or voided" check can never be reached — 🗑️ remove
**What happens today:** `_guard_item_mutations` already refuses a completed or voided order (`Work order is completed`); the later check with `Cannot remove parts from a completed or voided work order` never runs.
**Answer:** remove — dead branch (`work_order_manager.py:1467-1471`) (decided by Claude under the reviewer's delegation, 2026-11-19). Not a bug, no ID.
**Resolution:** moved to Not specified; `remove_item` R2 deleted; listed in `docs/testing/dead-code-removal-checklist.md`.

### Q9. After completion a machine returns to the status it had before start — ✅ intended
**What happens today:** Start puts the machine in `MAINTENANCE` and remembers the status before. Completion (with no explicit choice) and void put it back to that status, or `IDLE` if there was none. A machine already in `MAINTENANCE` before start stays in it.
**Answer:** intended — the order undoes only what it did (decided by Claude under the reviewer's delegation, 2026-11-19).

## Follow-ups for other reviews
> Not rules of this manager. Whoever describes the named module must read this list first.

| # | Where | What |
|---|---|---|
| FU-1 | **Work order service** (`app/services/work_order_service.py`, no spec yet) | (a) `create_invoice_for_work_order` has no status check: a voided or completed order can get an invoice (a completed one is frozen at once by F2). (b) `void_work_order` deletes only a **draft** invoice; an invoice confirmed by hand stays confirmed and payable on a voided order. **Owner OQ-62 (2026-11-21, asked as expense order OQ-EOS-1, same rule for work orders):** voiding an order whose invoice is already finalized is refused (400) with "This order's invoice is already finalized. Void the invoice on the invoice page first, then void the order."; nothing changes. Expense orders: BUG-3069; the work order service spec logs its own bug for this when described. (c) `complete_work_order` returns a completed order unchanged (idempotent); `complete_work_order_as_planned` does too, before any check. (d) TC1–TC6 per `base_service.spec.md`; `remove_approver` returns nothing. (e) Q2 / BUG-2923 lands there. (f) Money items (a), (b) are for the owner when the service is described. |
| FU-2 | **Workspace manager** | BUG-1201 (approvers), BUG-1883 (assignees) remove a leaving member from open orders; this manager's reads are not changed by them. |
| FU-3 | **Machine manager** | BUG-975 needs a DAO read of a machine's open orders (work order DAO FU-3). |

## Overview
`WorkOrderManager` runs work orders: maintenance and other jobs on a machine, a project component (*revisit after launch*) or nothing in particular, in one factory. It creates them (directly, from a template, or from the planning sheet), edits them, keeps their part lines, approvers and activity log, and moves them through `DRAFT` → `IN_PROGRESS` → `COMPLETED`, or to `VOIDED`. Starting consumes stock and puts the machine into maintenance; completing fits / returns parts on the machine, restores the machine's status and records who did the work; voiding returns consumed stock. Caller: `WorkOrderService` (every public method), `WorkOrderTemplateManager` (draft generation → `create_work_order_from_template`), `approval_notification_service` (`get_work_order`, `approval_summary`, `is_approvable`, `approvability_gap_reason`), `AttachmentManager` (`log_event`). It flushes, never commits, takes no lock today (BUG-2916; intended locks per the HR-10 rules, G9, G15).

**Callables:** 57 specified · 1 not specified (`__init__`; plus inherited `BaseManager` methods and the singleton) · 277 rules (recounted at apply-review 2026-11-21: `update_work_order` R7a added, `remove_item` R2 removed)
**Externals to mock:** `utcnow` (`app.managers.work_order_manager.utcnow`; also used by the stock posting modules); `settings.ENVIRONMENT` / `settings.WORK_ORDER_ALLOW_DEV_DELETE` (`app.managers.work_order_manager.settings`); `date.today` in `bulk_delete_future_recurrence_drafts` (imported inside the function from `datetime`; pass `after_date` explicitly except in the default case). No notification, email or external call happens here.
**Integration-only behavior:** the races of BUG-2916 (two concurrent transactions).

**Status values** (`work_orders.status`, plain text): `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `VOIDED`. **Locked** = `COMPLETED` or `VOIDED`. **Details fields** (`DETAILS_FIELDS`): `work_order_type_id`, `description`, `priority`, `machine_id`, `project_component_id`, `cost`, `account_id`. **Logged fields** (`ORDER_UPDATE_LOG_FIELDS`, label in brackets): `work_order_type_id` (Work order type), `description` (Description), `priority` (Priority), `machine_id` (Machine), `project_component_id` (Project component), `planned_date` (Planned date), `end_date` (End date), `cost` (Cost), `account_id` (Account), `assigned_to` (Assigned to), `required_approvals` (Required approvals), `completion_notes` (Completion notes).

**Line action types:** `CONSUME` (default; stock out at start, nothing at completion), `INSTALL` (out of the source at start, into the order's machine at completion), `REPLACE` (as INSTALL, plus the replaced part off the machine into damaged stock), `BORROW` (out at start, back to the source at completion).

**Events** are `work_order_events` rows written by `log_event` (shape per `log_event` R1). Event types written here: `created`, `scheduled`, `auto_approved`, `approved`, `approval_revoked`, `approvals_reset`, `approver_added`, `approver_removed`, `approval_withdrawn`, `created_from_template`, `updated`, `workers_updated`, `schedule_updated`, `started`, `completed`, `voided`, `item_added`, `item_updated`, `item_quantity_adjusted`, `item_removed`, `item_voided`, `item_replace_degraded`.

**Notes for the test designer:**
- Import `from app.managers.work_order_manager import work_order_manager`. Parents: `make_workspace`, `make_profile` (`tests/unit/factories.py`); `WorkspaceMember(workspace_id, user_id, role, status="active")` for the acting user and approvers; `Factory(workspace_id, name, abbreviation)`, `Machine(workspace_id, name, factory_id)`, `WorkOrderType(workspace_id, name)`, `Item(workspace_id, name, name_normalized, unit)`. Seed storage stock with `post_stock_in(location_type='storage', …)`.
- **Single-transaction stock trap (verified):** stock buckets are re-synced from their newest ledger row by `performed_at`; rows written in one transaction share a timestamp and ties are not broken by id today (BUG-664). Several postings to one bucket in one test then read a stale quantity (consume 3, add 1, return 4 gave 14 from 10). Give each posting a distinct time (patch `utcnow` forward between steps) or assert on ledger rows, not on the bucket quantity, when a case posts more than once to one bucket.
- `create_work_order` always flushes an `auto_approved` event (R7); count events from after creation.
- Status and machine: `start_work_order` calls `create_machine_event`, which refuses a machine already in the target status — the manager checks first (`_set_machine_status` R2).
- `settings.ENVIRONMENT` defaults to `"development"`, so `delete_work_order` deletes any status unless patched to `"production"`.
- **Schemas (G1):** `WorkOrderCreate`, `WorkOrderUpdate`, `WorkOrderVoidRequest`, `WorkOrderSheetEntryCreate`, `WorkOrderSheetItemLine` are in `app.schemas.work_order`; `WorkOrderFromTemplateCreate` is in `app.schemas.work_order_template`; the item schemas (`WorkOrderItemCreate`, `WorkOrderItemUpdate`) in `app.schemas.work_order_item` (`quantity: Decimal`).
- **Number rendering (G3):** in every stock / activity text and machine-activity metadata of `_consume_item`, `_reverse_item_consumption`, `_adjust_consumed_item_quantity` and `_apply_item_completion`, quantities are Python `int`s and render without decimals (`3`, `Used 3 Bolt from storage …`); `<on hand>` in R5 of `_apply_item_completion` is the machine bucket's integer `qty`. In `update_item` R5 (`item_quantity_adjusted`) the text and the metadata strings are `str()` of `Decimal`s: `<old>` = the line's `quantity` as the session holds it (`3.00` once the row has been re-read from the database, e.g. after `db.expire(line)`; the value as constructed otherwise), `<new>` = the `Decimal` parsed from the request (`Decimal("4")` → `4`, `Decimal("4.00")` → `4.00`). Pin the text by expiring the line first and sending `Decimal("4")`: `Adjusted <name> from 3.00 to 4`, metadata `old_quantity "3.00"`, `new_quantity "4"`.
- **Insufficient stock texts (G14):** storage source → 400 `Insufficient stock (<available> available, <requested> requested)`; machine source → 400 `Insufficient machine stock (<available> available, <requested> requested)`; both numbers are integers (`Insufficient stock (2 available, 3 requested)`). A storage bucket that does not exist yet is created at 0 first, so it gives the same 400 with `0 available`.
- **Event order (G13):** `list_events` returns newest first (`created_at` desc, then `id` desc); with `utcnow` frozen, all events of one call share a time, so order is by `id`. Within one `update_work_order` call the rows are written in this order: `approvals_reset` (R12) → `updated` (R13) → per change `workers_updated` / `schedule_updated` (R13) → `approval_revoked` (final recompute, R18). Compare by `id` ascending.
- **Unit-cost scale (G10):** `inventory.avg_price`, `machine_item_ledgers.avg_price_after`, `work_order_items.unit_cost` / `total_cost` are all `Numeric(15, 2)`. A unit cost read from the database therefore has 2 decimals, and `unit_cost × whole qty` never needs rounding (see `_consume_item` R5a, `_adjust_consumed_item_quantity` R7a). Seeding `avg_price = 0.125` and reading it back in the same session without a re-read tests an in-memory value no stored row can hold — do not use it. The rounding of BUG-1040 is observable only through the division in `_adjust_consumed_item_quantity` R6 (example in R6a).
- **Template-path 409 (G5):** `work_order_template_approvers` has a unique constraint `uq_wo_template_approver (work_order_template_id, user_id)`, and a new order has no approvers before R7, so the 409 of `create_work_order_from_template` R8 cannot arise from stored data. Trigger it by patching `work_order_template_manager.get_approvers` as imported in `app.managers.work_order_manager` to return the same active member twice (simple objects with `user_id` and `approver_slot`). Intended: the second `add_approver` 409 propagates (BUG-1206).
- **Empty names (G6, G12):** `work_order_types.name` and `profiles.name` are `NOT NULL` with no check constraint, so an empty string `""` can be stored directly (schemas refuse it through the API). Use that to reach the `"Maintenance"` fallback (`create_work_order_from_template` R3a) and the `User #<id>` fallback of `_resolve_completion_workers` R4.

## Not specified
- `WorkOrderManager.__init__` — wires the DAOs, no logic.
- Inherited `BaseManager` methods — not used by this module's callers; base spec.
- `work_order_manager` — module-level singleton.
- `remove_item` second "completed or voided" check (`work_order_manager.py:1467-1471`) — dead code, to be removed (reviewer; Q8, decided under the delegation).

---

## `_is_locked(record)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `update_work_order`, `add_approver`, `remove_approver`, `set_approval`, `_guard_item_mutations`)
**Rules:**
- **R1.** `True` for status `COMPLETED` or `VOIDED`; `False` for `DRAFT`, `IN_PROGRESS` and any other text.

## `_has_recorded_approvals(session, wo_id, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `update_work_order`, `add_item`, `update_item`, `remove_item`)
**Rules:**
- **R1.** `True` when at least one approver row of the order (in that workspace) has `approved = True`; `False` with none, or none approved.

## `is_approvable(session, wo)`
**Shape:** validator · **Persistence:** pure · **Visibility:** public (used by: `set_approval`, `approval_notification_service`)
**Rules:**
- **R1.** `True` when the title is not blank after trimming and `factory_id` is not `None`; otherwise `False` (`None` title counts as blank).
- **R2.** Through the API both always hold (title is NOT NULL and never blank, `factory_id` NOT NULL), so `False` is reachable only with an in-memory object.

## `approvability_gap_reason(session, wo)`
**Shape:** validator · **Persistence:** pure · **Visibility:** public (used by: `set_approval`, `approval_notification_service`)
**Rules:**
- **R1.** Blank / `None` title → `Work order setup is incomplete` (checked first).
- **R2.** Otherwise `factory_id is None` → `Set a factory before approvals can proceed`.
- **R3.** Otherwise `None`.

## `_format_scalar_value(field, value)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `_collect_field_changes`)
**Rules:**
- **R1.** `None` → `—`.
- **R2.** A `date` (or `datetime`) → ISO text (`2026-03-10`).
- **R3.** A whole `Decimal` → integer text (`150.00` → `150`); otherwise normalised (`150.50` → `150.5`).
- **R4.** An enum (anything with `.value`) → its value as text (`HIGH`).
- **R5.** Anything else → `str(value)` trimmed; empty after trimming → `—`. `field` is not used.

## `_variance_vs_planned(planned_date, actual_dt)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `_schedule_metadata_for_actual`)
**Rules:**
- **R1.** Either missing → `None`.
- **R2.** `delta` = actual day − planned day in days (`datetime` → its date).
- **R3.** `delta = 0` → label `On plan`; otherwise `<n> day early|late` for 1, `<n> days early|late` for more (`early` when negative).
- **R4.** Returns `{"planned_date": iso, "variance_days": delta, "variance_label": label}`.

## `_schedule_metadata_for_actual(wo, actual_dt, *, actual_field)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal (used by: `start_work_order`, `complete_as_planned`, `finalize_completion`)
**Rules:**
- **R1.** Always `{actual_field: actual_dt ISO}`.
- **R2.** With a planned date, also `planned_date` and the three variance keys of `_variance_vs_planned`; without one, only R1.

## `_started_worker_metadata(session, wo, workspace_id, user_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `start_work_order`, `complete_as_planned`)
**Rules:**
- **R1.** Returns `assigned_to` (the order's text), `assignee_user_ids` (the order's assignee rows, row-id order, assignee DAO `get_user_ids_by_order`), `started_by_user_id = user_id`.

## `_collect_field_changes(session, record, update_dict)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `update_work_order`)
**Rules:**
- **R1.** Only the logged fields (Overview) present in `update_dict` are looked at, in the Overview's order; `title`, `updated_by` and others are ignored.
- **R2.** A field whose new value equals the stored one (Python `==`; `Decimal('150.00') == Decimal('150')`) gives no entry.
- **R3.** Each change is `{"field", "label", "from_value", "to_value"}`; values per `_format_scalar_value`, except `work_order_type_id`, shown by `_work_order_type_name`.

## `_work_order_type_name(session, type_id, workspace_id)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **R1.** `None` → `—`.
- **R2.** A type of that workspace (soft-deleted included) → its name; otherwise `#<id>`.

## `resolve_invoice_account_id(record)`
**Shape:** validator · **Persistence:** pure · **Visibility:** public (used by: `WorkOrderService.create_invoice_for_work_order`)
**Rules:**
- **R1.** A truthy `account_id` is returned.
- **R2.** `None` (or `0`) → 422 `Set an account on the work order before creating an invoice`.

## `_derive_default_title(session, workspace_id, *, work_order_type_id, factory_id, machine_id, project_component_id, type_name=None)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `create_work_order`, `update_work_order`)
**Rules:**
- **R1.** Type name = `type_name` if truthy; else the type of that workspace (deleted included), else `Work order`.
- **R2.** With a machine id: target = that machine's name in the workspace (deleted included), else `Machine #<id>`. A machine id wins over a component id.
- **R3.** Else with a component id: target = the component's name, else `Component #<id>` *(revisit after launch)*.
- **R4.** With a target → `<type> — <target>` (em dash, spaces).
- **R5.** Without: the factory's name in the workspace → `<type> — <factory>`; no such factory → `<type>` alone.

---

## `create_work_order(session, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderService.create_work_order` ← `POST /work-orders/`; `create_work_order_from_template`; `sheet_entry`)

**Purpose:** Create a draft work order with the next number.

**Inputs:** `data: WorkOrderCreate` — `work_order_type_id` (required), `title?`, `description?`, `priority` (default `MEDIUM`), `factory_id` (required), `machine_id?`, `project_component_id?`, `planned_date?`, `end_date?`, `uses_inventory` (default `true`), `cost?`, `account_id?`, `assigned_to?`. No range or length checks today.

**Returns:** the new `WorkOrder`, flushed.

**Rules:**
- **R1.** A factory not in the workspace (unknown or another workspace's) → 404 `Factory with ID <id> not found`; nothing written.
- **R1a.** [BUG-2920] (P7) A soft-deleted factory → the same 404. *(Today: accepted.)*
- **R1b.** [BUG-2921] (Q1) With `machine_id`, a machine whose `factory_id` is not `data.factory_id` → 400 `Machine <name> belongs to another factory`; nothing written. Checked after R2 and R3. *(Today: accepted, verified.)*
- **R2.** A type not in the workspace → 404 `Work order type with ID <id> not found`. [BUG-1228] A soft-deleted type → the same 404 *(today accepted)*. Order of checks: factory, type, account.
- **R3.** A given `account_id` not in the workspace → 404 `Account with ID <id> not found`. [BUG-2920] A soft-deleted account → the same 404 *(today accepted)*. `None` skips the check.
- **R3a.** [BUG-2912, BUG-2913] `cost` must be ≥ 0 with at most 2 decimals and 13 integer digits; otherwise 422 from `WorkOrderCreate`. *(Today: any value; `-5` stored, verified.)*
- **R3b.** [BUG-2926] (Q4) `end_date` before `planned_date` → 422 `End date cannot be before the planned date`. *(Today: stored, verified.)* (G8, decided by Claude under the reviewer's delegation, 2026-11-21) On create the check lives in `WorkOrderCreate` (a model validator), so building the schema raises `pydantic.ValidationError` with that message and the manager is never reached; on update (`update_work_order` R9b) the merged dates are checked in the manager, `HTTPException` 422 with the same detail.
- **R4.** `title` is trimmed; blank / `None` → derived per `_derive_default_title` with the type's name.
- **R5.** The row gets `workspace_id`, `work_order_number` = work order DAO `get_next_number` (`WO-<year>-<nnn>`), `created_by = user_id`, `status = DRAFT`, every other field as sent.
- **R6.** With a truthy `assigned_to`, assignees are matched from the text (`_sync_assignees_from_text`) and the `created` event's metadata is `{"assigned_to", "assignee_user_ids"}`; otherwise metadata `None`.
- **R7.** Events in order: `created` `Work order <number> created`; with a planned date, `scheduled` `Scheduled for <iso date>` (metadata `planned_date`); then the approval stamp per `_recompute_approval_status` — with no approvers and no `required_approvals` the order is 0 of 0, met: `approved_by = user_id`, `approved_at = utcnow()`, event `auto_approved` `Ready to start — no approval required` (verified).
- **R8.** `machine_id` and `project_component_id` may both be set; both are stored *(revisit after launch: the update makes them exclusive, the create does not)*.
- **R9.** [BUG-1016] A machine, or project component, not in the workspace → 404 `Machine with ID <id> not found` / `Project component with ID <id> not found`; nothing written. *(Today: stored unchecked.)* [BUG-2920] a soft-deleted machine → the same 404 *(today accepted)*.

**Errors:** 404 factory / type / account / machine / component as above; 400 R1b; 422 schema.
**Side effects:** one `work_orders` row; assignee rows; 2–3 events; flushed.

---

## `create_work_order_from_template(session, template_id, workspace_id, user_id, overrides)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderService.create_work_order_from_template` ← `POST /work-order-templates/{id}/create-work-order/`; `WorkOrderTemplateManager` draft generators)

**Purpose:** Make an order from a saved template for a given machine.

**Inputs:** `overrides: WorkOrderFromTemplateCreate` — `machine_id` (required), `title?`, `description?`, `assigned_to?`, `planned_date?`.

**Rules:**
- **R1.** Template per `WorkOrderTemplateManager.get_template` (another workspace / unknown → 404 `Work order template with ID <id> not found`); an inactive template → 400 `Template is inactive`.
- **R2.** A machine not in the workspace → 404 `Machine with ID <id> not found`. [BUG-2920] soft-deleted → the same 404 *(today accepted)*.
- **R3.** The order is created per `create_work_order` with: the template's type, priority, `uses_inventory`, `account_id`, `cost`; factory = the machine's factory; machine = the machine; `planned_date` from the overrides; `title` = override if truthy else `<template type name or "Maintenance"> — <machine name>`; `description` = override if truthy else the template's; `assigned_to` = override if truthy else the template's. An empty-string override falls back to the template.
- **R3a.** (G6) The `"Maintenance"` fallback is used only when the template's type has an empty name (`""`): a template's `work_order_type_id` is `NOT NULL` with a restricting foreign key, so the type always exists (a soft-deleted type still has its name). Example: type named `""`, machine `Loom 3` → title `Maintenance — Loom 3`.
- **R4.** `work_order_template_id` = the template's id.
- **R5.** With `uses_inventory`, one line per template line (template id order), through `add_item`: same item, quantity, action type, replaced item, notes; `uses_inventory = True`, source `storage` of the machine's factory. Any refusal of `add_item` (e.g. duplicate item 409, missing replaced item 404) fails the whole call.
- **R6.** Without `uses_inventory`, no lines.
- **R7.** With `requires_approval`, each template approver is added per `add_approver` with its slot, `assigned_by = user_id`. A refusal (not an active member, 400) skips that approver.
- **R8.** [BUG-1206] A 409 (`User is already an approver for this order`) is not swallowed: it propagates and nothing is saved. *(Today: every `HTTPException` is skipped; a 409 cannot arise with today's data.)*
- **R9.** [BUG-2922] (P8) When the template requires approval and no approver was added, the order is **not** approved: `required_approvals = 1`, no `auto_approved` stamp remains, event `approvals_needed` `Template approvers are no longer members — add an approver`. *(Today: 0 of 0, met; stamped `auto_approved`.)*
- **R10.** Last, event `created_from_template` `Generated from template "<template name>"` (metadata `work_order_template_id`).

**Side effects:** as `create_work_order`, plus lines, approvers and events; flushed.

---

## `update_work_order(session, wo_id, data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderService.update_work_order` ← `PUT /work-orders/{id}/`; the service notifies "re-approve" when `_approvals_reset` is true)

**Purpose:** Edit a draft or in-progress order, logging changes and resetting approvals when the details change.

**Inputs:** `data: WorkOrderUpdate` — every field optional: `work_order_type_id`, `title`, `description`, `priority`, `machine_id`, `project_component_id`, `planned_date`, `end_date`, `cost`, `account_id`, `assigned_to`, `required_approvals`, `completion_notes`.

**Returns:** the order (flushed) with the transient attribute `_approvals_reset` (`True` / `False`).

**Rules:**
- **R1.** An order not in the workspace → 404 `Work order with ID <id> not found`.
- **R2.** A soft-deleted order → 400 `Cannot update a deleted work order`.
- **R3.** ✅ (Q6) `title` is always dropped.
- **R4.** Fields sent as `null` are dropped, except: `machine_id` sent (even `null`) → that value and `project_component_id = None`; else `project_component_id` sent → that value and `machine_id = None` *(revisit after launch)*; `account_id` sent → that value (`null` clears it); `required_approvals` sent → that value (`null` = "all approvers"). [BUG-2919] (P6) An explicit `null` for `planned_date`, `end_date` or `cost` clears it. *(Today: dropped.)*
- **R5.** Nothing left after R3–R4 → the order is returned unchanged, `_approvals_reset = False`, nothing written, even on a completed or voided order.
- **R6.** Otherwise a locked order → 400 `Work order is completed and cannot be edited` / `… voided …` (status lower-cased).
- **R7.** An `IN_PROGRESS` order with any details field present → refused (R8). Editable in progress: `planned_date`, `end_date`, `assigned_to`, `completion_notes`.
- **R7a.** [BUG-2931] (OQ-58) An `IN_PROGRESS` order with `required_approvals` present (any value, `null` included) → 400 `Work has started — approvals can no longer change`, nothing written. *(Today: accepted in progress.)*
- **R8.** [BUG-2924] (Q3) The refusal is 400 `Work order is in progress — type, description, priority, target, cost and account are locked`. *(Today: `Work order is in progress — structural fields (target, type, cost, account) are locked`.)* The check uses presence, not change: sending a details field with its current value is refused too.
- **R9.** A non-null `account_id` not in the workspace → 404 `Selected account not found`; a `work_order_type_id` not in the workspace → 404 `Selected work order type not found` ([BUG-1228] soft-deleted type → the same 404, *today accepted*).
- **R9a.** [BUG-2912, BUG-2913] `cost` ≥ 0 with ≤ 2 decimals; `required_approvals` null or ≥ 0; otherwise 422 from `WorkOrderUpdate`. *(Today: any value.)*
- **R9b.** [BUG-2926] (Q4) After the update, both dates set and `end_date` before `planned_date` → 422 `End date cannot be before the planned date`, nothing written. *(Today: stored.)*
- **R10.** Changes are collected per `_collect_field_changes` before the write.
- **R11.** [BUG-2920] (P7) A soft-deleted account → the R9 404. *(Today: accepted.)*
- **R12.** On a `DRAFT` with at least one recorded approval, when a details field is present, every approval is cleared per `reset_approvals` with reason `Order details edited`, and `_approvals_reset = True`. [BUG-2915] (HR-9) Only when a details field actually changes value. *(Today: on presence; sending the current description clears the approvals.)*
- **R12a.** [BUG-2929] (OQ-56) On a `DRAFT` whose `invoice_id` names an invoice that is not `voided`, a change of value of `cost` or `account_id` (clearing it included) → 400 `This work order has an invoice. Delete the draft invoice first to change the cost or account.`, nothing written. Sending the current value is not a change (HR-9) and passes. No invoice, or a voided one → allowed. *(Today: changed; the invoice keeps its old amount and account.)*
- **R13.** With at least one change: one `updated` event `Order details updated`, metadata `{"changes": [...]}`; if `assigned_to` was sent, assignees are re-matched (`_sync_assignees_from_text`) and `assignee_user_ids` added to that metadata. Then, in the order of the changes: for an `assigned_to` change a `workers_updated` event `Workers updated` (metadata `from_value`, `to_value`, `assigned_to`, `assignee_user_ids`); for a `planned_date` / `end_date` change a `schedule_updated` event `<label> changed` (metadata `field`, `from_value`, `to_value`, `changes: [change]`).
- **R13a.** [BUG-2930] (OQ-57) On a `DRAFT` with at least one live (not deleted) `INSTALL`, `REPLACE` or `BORROW` line, `machine_id: null`, or a `project_component_id` that clears the machine (R4), → 400 `Remove the Install / Replace / Borrow parts first — they need a machine`, nothing written. A different non-null `machine_id` is accepted. With only `CONSUME` lines (or deleted ones) the machine may be removed. *(Today: accepted; the parts vanish at completion, verified.)*
- **R13b.** [BUG-2921] (Q1) On a draft, a new non-null `machine_id` also sets `factory_id` to that machine's factory; the change appears in the `updated` event (label `Factory`). *(Today: the factory is kept.)*
- **R14.** [BUG-1016] A `machine_id` / `project_component_id` not in the workspace → 404 `Machine with ID <id> not found` / `Project component with ID <id> not found`. *(Today: stored unchecked.)*
- **R15.** ✅ (Q6) On a `DRAFT`, when type, machine or component is present, `title` is re-derived per `_derive_default_title` from the new (or kept) type and target and the order's factory (machine wins; both `None` → factory name).
- **R16.** The row is written with the remaining fields and `updated_by = user_id` (inherited update; flushed).
- **R17.** If `assigned_to` was sent but no change was collected, assignees are re-matched from the stored text anyway.
- **R18.** Afterwards the approval stamp is recomputed per `_recompute_approval_status` (draft only), e.g. lowering `required_approvals` to the approved count stamps `approved`.
- **R19.** `_approvals_reset` is set on the returned object.
- **R20.** [BUG-2915] (HR-9) With no change in value, nothing is written: no `updated_by`, no event, no reset. *(Today: `updated_by` stamped, verified.)*
- **R21.** `completion_notes` may be set on a draft or in-progress order through this call.

**Errors:** 404 R1, R9, R14; 400 R2, R6, R7a, R8, R12a, R13a; 422 R9a, R9b.
**Side effects:** the row; events; assignee rows; approver rows (reset); flushed.

---

## `get_work_order(session, wo_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: most methods here; the service; `approval_notification_service`)
**Rules:**
- **R1.** The order of that workspace is returned; unknown or another workspace's → 404 `Work order with ID <id> not found`.
- **R2.** [BUG-1279] (HR-4) A soft-deleted order → the same 404, unless `include_deleted=True` *(requires new parameter)*; `delete_work_order` keeps its own lookup. *(Today: returned; verified it can be started.)* Every method that reaches an order through this call follows from it (items, approvers, events, start, complete, void).

## `list_work_orders(session, workspace_id, work_order_type_id=None, wo_status=None, priority=None, factory_id=None, machine_id=None, work_order_template_id=None, planned_date_from=None, planned_date_to=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /work-orders/`)
**Rules:**
- **R1.** Returns work order DAO `get_by_workspace` with the same filters (`wo_status` → `status`), R1–R11 there (live rows only, newest first; [BUG-2670] tie order).

## `bulk_delete_future_recurrence_drafts(session, *, workspace_id, user_id, work_order_template_id, machine_id, after_date=None)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `POST /work-orders/bulk-delete-future-recurrence-drafts/`)
**Rules:**
- **R1.** Cutoff = `after_date`, or today. [BUG-2925] (P9) "today" = `utcnow().date()`. *(Today: `date.today()`, server local.)*
- **R2.** Every row of work order DAO `list_future_drafts_for_template_machine` (live `DRAFT`s of that template and machine, planned strictly after the cutoff) is soft-deleted (`deleted_by = user_id`).
- **R3.** Returns their ids in planned-date, id order; none → `[]`. No event, no invoice handling.

## `delete_work_order(session, wo_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /work-orders/{id}/`)
**Rules:**
- **R1.** Unknown / another workspace → 404 `Work order with ID <id> not found`.
- **R2.** Already soft-deleted → 400 `Work order is already deleted`.
- **R3.** With `ENVIRONMENT == "production"` and `WORK_ORDER_ALLOW_DEV_DELETE` false, a non-`DRAFT` → 400 `Only a draft work order can be deleted — void it instead`.
- **R4.** ✅ (Q7) Otherwise (any other environment, or the switch on) any status is soft-deleted; consumed stock, machine status, lines and approvers are untouched.
- **R5.** [BUG-2923] (Q2) A linked draft invoice is deleted and `invoice_id` cleared, with event `invoice_voided`; a linked non-draft invoice → 400 `This work order has a confirmed invoice — void the invoice first`. Fix in `WorkOrderService.delete_work_order`. *(Today: the invoice stays linked.)*
- **R6.** Soft delete per work order DAO `soft_delete` R1–R3; returns the row. No event.

---

## `list_approvers(session, wo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /work-orders/{id}/approvers/`, sheet bundles)
**Rules:**
- **R1.** The order must exist per `get_work_order` (404).
- **R2.** One tuple per approver row (approver DAO `get_by_order` order, [BUG-1200] tie): `(row, profile or None, member position or None)`; the position is read from the membership whatever its status.

## `approval_summary(session, wo)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public
**Rules:**
- **R1.** `approved_count` = approver rows with `approved = True`.
- **R2.** `required` = `required_approvals` when not `None`; otherwise the number of approver rows.
- **R3.** `met` = `approved_count >= required`. With [BUG-2912] `required_approvals` < 0 cannot be stored *(today `-1` → met, verified)*; `0` is an explicit waiver (met).
- **R4.** [BUG-1204] An order that lost its last approver (through `remove_approver` or member removal) with `required_approvals` `None` is **not** met until an approver is added and approves (one way: `remove_approver` sets `required_approvals = 1`); an order that never had an approver stays 0 of 0, met. *(Today: 0 of 0, met.)*
- **R5.** Returns `(approved_count, required, met)`.

## `approvals_met(session, wo)`
**Shape:** validator · **Persistence:** reads · **Visibility:** public (used by: `start_work_order`, `complete_as_planned`)
**Rules:** **R1.** The `met` of `approval_summary`.

## `reset_approvals(session, wo_id, workspace_id, user_id, reason='Section unconfirmed')`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `update_work_order`, `void_work_order`, `add_item`, `update_item`, `remove_item`)
**Rules:**
- **R1.** Every approver row with `approved = True` becomes `approved = False`, `approved_at = None`; rows not approved are untouched.
- **R2.** With at least one cleared: flushed and one event `approvals_reset` `<reason> (<n> approval(s) cleared)`, `performed_by = user_id`.
- **R3.** None cleared → nothing written, no event. The order's own `approved_by` / `approved_at` are not touched here.

## `_recompute_approval_status(session, wo, workspace_id, actor_user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: create, update, approver methods)
**Rules:**
- **R1.** Only a `DRAFT` is looked at; any other status → nothing.
- **R2.** Met (per `approval_summary`) and `approved_at` empty → `approved_by = actor`, `approved_at = utcnow()`, flushed, event `auto_approved` `Ready to start — no approval required` when `required == 0`, else `approved` `All required approvals collected`.
- **R3.** Not met and `approved_at` set → both cleared, flushed, event `approval_revoked` `No longer meets approval requirements`.
- **R4.** Met with a stamp, or not met without one → nothing.

## `add_approver(session, wo_id, user_id, workspace_id, assigned_by, approver_slot=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /work-orders/{id}/approvers/`, template and sheet paths)
**Rules:**
- **R1.** Order per `get_work_order`.
- **R2.** Locked order → 400 `Work order is completed` / `Work order is voided`.
- **R2a.** [BUG-2931] (OQ-58) An `IN_PROGRESS` order → 400 `Work has started — approvals can no longer change`, nothing written (checked after R2, before R3). The template and sheet paths add approvers to new drafts only and are unaffected. *(Today: accepted, verified.)*
- **R3.** The user must have a membership of the workspace with status `active`; otherwise 400 `User is not an active member of this workspace`.
- **R4.** Already an approver of the order → 409 `User is already an approver for this order`.
- **R5.** A row is added: `approved = False`, `assigned_by`, `approver_slot` as given (free text, approver DAO R10); flushed.
- **R6.** Event `approver_added` `Added <name> as approver` (`User #<id>` with no profile), `performed_by = assigned_by`, metadata `user_id`, `user_name`.
- **R6a.** (G12) The `User #<id>` fallback cannot be reached: R3 requires a membership row and the approver row references `profiles.id` (both `NOT NULL` foreign keys), so the profile exists. A profile named `""` gives `Added  as approver` and `user_name ""` (the name is used as stored; only a missing profile falls back). The same holds for `remove_approver` R3. No card for the fallback; it is a dead-code candidate (as `sales_manager.py:791`, `:806`).
- **R7.** Then `_recompute_approval_status` (a met draft becomes unmet → `approval_revoked`).
- **R8.** [BUG-2916] (HR-10) (G15, decided by Claude under the reviewer's delegation, 2026-11-21) The order row is read `FOR UPDATE` before R2: adding an approver changes whether approvals are met (an approval decision under HR-10), and after BUG-2931 it checks the order's state before writing, so it can race a start. *(Today: no lock.)*

## `remove_approver(session, wo_id, user_id, workspace_id, performed_by=None)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /work-orders/{id}/approvers/{user_id}/`)
**Rules:**
- **R1.** Order per `get_work_order`; locked → 400 as `add_approver` R2.
- **R2a.** [BUG-2931] (OQ-58) An `IN_PROGRESS` order → 400 `Work has started — approvals can no longer change`, nothing removed (checked after R1, before R2). *(Today: removed.)*
- **R2.** No such approver row → 404 `Approver not found`.
- **R3.** The row is hard-deleted (an approval given is lost), flushed; event `approver_removed` `Removed <name> as approver` (metadata `user_id`, `user_name`), `performed_by` as given (may be `None`).
- **R4.** Then `_recompute_approval_status`; the last approver's removal follows `approval_summary` R4 [BUG-1204].
- **R5.** [BUG-2916] (HR-10) (G15, decided as `add_approver` R8) The order row is read `FOR UPDATE` before R1's state check; removing an approver can make approvals met. *(Today: no lock.)*
- **R4a.** (G7) The actor of that recompute is `performed_by`: when the removal makes a draft's approvals met, `approved_by = performed_by` (`None` when the argument is left out; the service always passes the caller) and the `approved` / `auto_approved` event has that `performed_by`; when it makes them unmet, `approved_by` / `approved_at` are cleared and `approval_revoked` has that `performed_by`.

## `set_approval(session, wo_id, user_id, workspace_id, approved)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: approve-as-me / unapprove-as-me)
**Rules:**
- **R1.** The caller's approver row is looked up first: none (also for an unknown order or another workspace's) → 403 `You are not an assigned approver for this order`.
- **R2.** Then the order per `get_work_order`; locked → 400 `Work order is completed` / `… voided`.
- **R3.** Approving an order that is not approvable → 400 with `approvability_gap_reason` (not reachable through the API, `is_approvable` R2). Withdrawing is not checked.
- **R3a.** [BUG-2931] (OQ-58) On an `IN_PROGRESS` order, approving and withdrawing → 400 `Work has started — approvals can no longer change`, nothing written (checked after R2; a non-approver still gets R1's 403 first). *(Today: accepted, verified; the order's stamp is not recomputed.)*
- **R4.** The row gets `approved`, `approved_at = utcnow()` when approving, `None` when withdrawing; flushed.
- **R5.** Event `approved` `Approved work order` or `approval_withdrawn` `Withdrew approval`, `performed_by = user_id`; then `_recompute_approval_status`.
- **R6.** [BUG-2917] (P4) Setting the value the row already has writes nothing and logs nothing; the row is returned unchanged. *(Today: re-stamped and logged.)*
- **R9.** [BUG-2916] (HR-10) The order row is read `FOR UPDATE` before R2. *(Today: no lock.)*

---

## `_consume_item(session, wo, item, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: `_run_start_side_effects`, `add_item`, `update_item`)
**Rules:**
- **R1.** A line not using inventory, or already consumed (`consumed_at` set) → nothing.
- **R2.** No source type or source id (empty / `0`) → 400 `Item line <id> uses inventory but has no source location set`.
- **R3.** A fractional quantity → 400 `Item line <id> has a fractional quantity; inventory consumption requires whole units`.
- **R4.** Stock leaves the source per `post_stock_out` (type and id of the line, `transaction_type = consumption`, `source_type = work_order`, `source_id` = order id, notes `<number> — <item name>`, machine activity `consumption` `Consumed for work order <number>: <qty> units of <name>`); its errors propagate (insufficient stock 400, unknown location type 400, location not in the workspace 404; [BUG-665] qty < 1 → 400, today `0` and negatives pass — verified `-2` raised stock).
- **R5.** The line gets `consumed_at = utcnow()`, `consumed_by = user_id`, `unit_cost` = the posting's unit cost, `total_cost = unit_cost × qty` rounded to 2 decimals [BUG-1040: half up; today half even]; flushed.
- **R5a.** (G10) The posting's unit cost comes from a `Numeric(15, 2)` column (storage: `inventory.avg_price`, 0 when empty; machine: the newest machine ledger row's `avg_price_after`, 0 when none), so with stored data `unit_cost × qty` already has 2 decimals and the BUG-1040 rounding never changes the result. BUG-1040 stays on this line (code fix) but has no failing card here; the observable case is `_adjust_consumed_item_quantity` R6a.
- **R6.** With a machine on the order, a machine activity event `work_order_item_used` `Used <qty> <name> from <machine #id | storage> for work order <number>` (metadata `item_id`, `item_name`, `quantity`, `work_order_id`).
- **R7.** With a project component on the order, the same entry in the component's activity log *(revisit after launch)*. [BUG-1884] When the component is not in the order's workspace, no component entry is written and the step goes on. *(Today: the entry is written under the order's workspace for whatever component id is stored; once BUG-1192 is fixed alone it would be a 404 that blocks the step.)*

## `_reverse_item_consumption(session, wo, item, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: `void_work_order`, `remove_item`)
**Rules:**
- **R1.** A line not consumed → nothing.
- **R2.** The line's whole current quantity goes back to its source per `post_stock_in` at the line's `unit_cost` (or 0), `transaction_type = consumption_reversal`, notes `<number> voided — <name> returned`, machine activity `consumption_reversed` `Returned <qty> <name> — work order <number> voided` (the same wording on `remove_item`).
- **R3.** The line's `consumed_at`, `consumed_by`, `unit_cost`, `total_cost` become `None`; flushed. No work order event here.

## `_adjust_consumed_item_quantity(session, wo, item, *, old_qty, new_qty, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: `update_item`)
**Rules:**
- **R1.** Equal quantities, or a line not using inventory → nothing.
- **R2.** Order not `IN_PROGRESS` → 400 `Consumed item quantity can only be adjusted while the work order is in progress` (not reachable through the API: consumed lines exist only on started orders and locked orders are refused first).
- **R3.** Old or new quantity fractional, or new ≤ 0 → 400 `Quantity must be a positive whole number for inventory-tracked consumed lines`.
- **R4.** Increase by `d`: `d` more leave the source per `post_stock_out` (`consumption`, notes `<number> — <name> qty increased by <d>`; for a machine source the machine activity has event type `consumption` and text `Additional <d> <name> consumed for work order <number> (qty adjustment)`).
- **R5.** Decrease by `d`: `d` go back per `post_stock_in` at the line's unit cost (`consumption_reversal`, notes `<number> — <name> qty reduced by <d>`; for a machine source the machine activity has event type `consumption_reversed` and text `Returned <d> <name> — work order <number> line qty adjusted`).
- **R6.** After an increase: `total_cost` = old total (or 0) + new unit cost × `d`; `unit_cost` = new total / new quantity; both rounded to 2 decimals [BUG-1040]. Verified 3 @ 2.50 → 4 @ 2.50, total 10.00.
- **R6a.** (G10) [BUG-1040] (HR-15) The division rounds half up. Example: a consumed line of 1 at unit cost 0.25 (total 0.25), raised to 2 while the source's average is 0.00 → total 0.25, unit cost 0.25 / 2 = 0.125 → **0.13**. *(Today: 0.12, half even.)*
- **R7.** After a decrease: `total_cost` = `unit_cost × new quantity` [BUG-1040]; `unit_cost` unchanged (no unit cost → total `None`); flushed.
- **R7a.** (G10) `unit_cost` is a stored 2-decimal value times a whole number, so R7's rounding never changes the result with stored data; no failing card for BUG-1040 here.
- **R8.** With a machine on the order, machine activity `work_order_item_qty_adjusted` `Adjusted <name> from <old> to <new> (<source>) for work order <number>` (metadata `item_id`, `item_name`, `old_quantity`, `new_quantity`, `work_order_id`). No component entry *(revisit after launch)*.

## `_apply_item_completion(session, wo, item, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: `finalize_completion`)
**Rules:**
- **R1.** Nothing for a line not using inventory, not consumed, on an order with no machine, or of action `CONSUME`.
- **R2.** `INSTALL`: the quantity goes into the order's machine per `post_stock_in` at the line's unit cost (`work_order_install`, notes `<number> — <name> installed`, activity `item_installed` `Installed <qty> <name> — work order <number>`).
- **R3.** `REPLACE`: the machine's on-hand quantity of the replaced item is read (no row → 0).
- **R4.** On hand ≥ quantity: the replaced item leaves the machine per `post_stock_out` (`work_order_replace_out`, activity `item_replaced_removed` `Removed <qty> <replaced name> (replaced) — work order <number>`).
- **R5.** On hand < quantity: nothing is removed; event `item_replace_degraded` `Machine only had <on hand> of <replaced name> on hand (needed <qty>) — installed <qty> <name> without removing anything` (verified).
- **R6.** ✅ (OQ-59, owner 2026-11-21: zero value intended) After R4, the same quantity of the replaced item enters the order's factory's **damaged** stock per `post_stock_in` at unit cost **0** (`work_order_replace_damaged`, notes `… moved to damaged stock`, no activity).
- **R7.** In both REPLACE cases the new item goes into the machine per `post_stock_in` at the line's unit cost (`work_order_replace_in`, activity `item_replaced` `Installed <qty> <name> as a replacement — work order <number>`).
- **R8.** `BORROW`: the quantity goes back to the line's source per `post_stock_in` at the line's unit cost, with a `work_order_borrow_returned` ledger row. Only when the source is a machine is a machine activity `item_borrowed_returned` `Returned <qty> <name> — work order <number>` written on that machine; a storage source gets the ledger row and no activity (G16: storage has no activity log; its trail is the inventory ledger, as for consumption from storage).
- **R9.** The line itself is not changed (stays consumed).

## `_set_machine_status(session, machine_id, workspace_id, user_id, new_status, *, work_order_number=None, work_order_id=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: start, complete, void)
**Rules:**
- **R1.** The current status = `status_from_activity` of `get_latest_status` (machine activity manager).
- **R2.** Equal to the new status → nothing; returns it.
- **R3.** Otherwise one status event per `MachineManager.create_machine_event` with note `Work order <number>` (no number → no note) and `work_order_id`; its errors propagate (deleted machine 400, machine not in the workspace 404, [BUG-1000] order not live 404).
- **R4.** Returns the status before (may be `None`).
- **R5.** (G2) `new_status` is a `MachineEventTypeEnum` member (a `str` enum); R2 compares the current status with `new_status.value`. The value returned is the plain text stored in the latest status event's metadata `status` (e.g. `"RUNNING"`), not an enum member, or `None` when the machine has no status event (or its metadata has no `status`). `status_from_activity` itself: `None` event or empty metadata → `None`; else metadata `status` (may be `None`).

## `_previous_machine_status(session, wo)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal
**Rules:**
- **R1.** The `previous_machine_status` metadata of the order's newest `started` event (event DAO order: newest first); no such event, or no key → `None`.

## `start_work_order(session, wo_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `POST /work-orders/{id}/start/`)
**Rules:**
- **R1.** Order per `get_work_order` (404; [BUG-1279] deleted).
- **R2.** Not `DRAFT` → 400 `Work order must be in draft to be started`.
- **R3.** Approvals not met → 400 `Assigned approvers must approve before work can start` ([BUG-1204] see `approval_summary` R4).
- **R4.** Side effects per `_run_start_side_effects`: every live inventory line not yet consumed is consumed (line-id order, [BUG-1272]); the first failing line stops the call (e.g. insufficient stock) — the service rolls back.
- **R5.** With a machine: the machine goes to `MAINTENANCE` (already there → no event); the status before is kept.
- **R6.** `status = IN_PROGRESS`, `started_by = user_id`, `started_at = utcnow()`; an empty `planned_date` becomes `utcnow().date()`; flushed.
- **R7.** Event `started` `Work started — <n> item(s) consumed` (or `no inventory items to consume`), metadata `items_consumed`, `previous_machine_status`, `started_at`, the planned date and variance (`_schedule_metadata_for_actual`), and the worker keys of `_started_worker_metadata`.
- **R8.** [BUG-1884] component entries per `_consume_item` R7 *(revisit after launch)*.
- **R9.** [BUG-2916] (HR-10) The order row is read `FOR UPDATE` before R2. *(Today: no lock.)*

## `_planned_date_noon_utc(planned_date)`
**Shape:** compute · **Persistence:** pure · **Visibility:** internal
**Rules:** **R1.** A naive `datetime` at 12:00:00 of that date.

## `_run_start_side_effects(session, wo, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal (used by: start, complete-as-planned)
**Rules:**
- **R1.** Consumes per `_consume_item` every live line with `uses_inventory` and no `consumed_at`; returns their count.
- **R2.** With a machine: `_set_machine_status(… MAINTENANCE …)`, returning the status before; no machine → `None`. Status is not changed here.
- **R3.** (G4) Returns one tuple `(count, status_before)`: the number of lines consumed in R1 (an `int`, `0` when none) first, then R2's status text or `None`.

## `_ensure_active_workspace_member(session, workspace_id, user_id)`
**Shape:** validator · **Persistence:** reads · **Visibility:** internal
**Rules:** **R1.** No membership, or one not `active` → 400 `User is not an active member of this workspace`.

## `_sync_assignees_from_text(session, wo, assigned_text)`
**Shape:** update · **Persistence:** writes · **Visibility:** internal (used by: create, update)
**Rules:**
- **R1.** The text is matched against the workspace's active members (`resolve_worker_text_to_members` over `load_active_member_lookups`); the order's assignee rows become exactly the matched ids (assignee DAO `replace_for_order`); returns them. `None` / blank → `[]` (rows removed). Unmatched names stay only in the text.

## `_resolve_completion_workers(session, workspace_id, performed_by_user_id, *, completed_by_names=None, completed_by_user_ids=None, completed_by_user_id=None)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `finalize_completion`)
**Rules:**
- **R1.** Ids = `completed_by_user_ids`; if empty / `None` and `completed_by_user_id` is given → `[completed_by_user_id]`.
- **R2.** With ids: each must be an active member (400 per `_ensure_active_workspace_member`, first failing id); names = `completed_by_names` trimmed if not blank, else `display_names_for_user_ids` (`Rahim, Karim`; [BUG-381] repeats); returns `(names, ids)` as given (repeats kept).
- **R3.** Without ids but with non-blank names: names matched to active members; returns the resolution's display text (or the trimmed names) and the matched ids (possibly `[]`).
- **R4.** Neither: the performer must be an active member (400); returns `(their profile name or "User #<id>", [performer])`.
- **R4a.** (G12) `User #<id>` is used when the performer's profile name is empty (`""`, storable directly) — unlike `add_approver`, an empty name falls back here. A missing profile cannot happen (the membership check passed).

## `complete_as_planned(session, wo_id, workspace_id, user_id, *, completion_notes=None, machine_status=None, completed_by_user_id=None, completed_by_user_ids=None, completed_by_names=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderService.complete_work_order_as_planned`, which first returns a completed order unchanged and confirms a draft invoice for an order with an account)
**Rules:**
- **R1.** Order per `get_work_order`; not `DRAFT` → 400 `Work order must be in draft to complete as planned`.
- **R2.** No planned date → 400 `Work order must have a planned date`.
- **R3.** Planned date after `utcnow().date()` → 400 `Complete as planned is only allowed when the planned date is today or in the past` (today allowed; verified future refused).
- **R4.** Approvals not met → 400 `Assigned approvers must approve before work can be completed`.
- **R5.** Order of checks: R1, R2, R3, R4.
- **R6.** Start side effects per `_run_start_side_effects` (consumption, machine to `MAINTENANCE`).
- **R7.** `started_by = user_id`, `started_at` = noon of the planned date (`_planned_date_noon_utc`); status is not set to `IN_PROGRESS`.
- **R8.** A `started` event as `start_work_order` R7, with the noon time and an extra `completion_mode: complete_as_planned`.
- **R9.** Then `finalize_completion` with `completed_at` = the same noon and extra metadata `completion_mode: complete_as_planned`. Verified: started_at = completed_at = 12:00 of the planned date; events `created, scheduled, auto_approved, started, completed`.
- **R10.** Returns the completed order.
- **R11.** [BUG-2916] (HR-10) Row lock before R1's state check. *(Today: none.)*

## `finalize_completion(session, wo, performed_by_user_id, completion_notes=None, machine_status=None, *, completed_by_user_id=None, completed_by_user_ids=None, completed_by_names=None, completed_at=None, event_metadata_extra=None)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderService.complete_work_order` after checking `IN_PROGRESS`; `complete_as_planned`)
**Rules:**
- **R1.** No state check of its own: whatever status the given order has, it is completed (the callers check).
- **R2.** Workers per `_resolve_completion_workers` (a refusal raises before anything is written).
- **R3.** `status = COMPLETED`, `completed_by_names` = the names, `completed_by` = the first id or `None`, `completed_at` = given or `utcnow()`; `completion_notes` replaced when not `None` (`""` clears); flushed.
- **R4.** Completer rows become exactly the ids (completer DAO `replace_for_order`; repeats once).
- **R5.** With a machine: each live line per `_apply_item_completion` (line-id order).
- **R6.** With a machine: machine activity `work_order_completed` `Work order completed: <number> — <title>` (metadata `work_order_id`).
- **R7.** With a machine: its status becomes `machine_status` if given, else the status before start (`_previous_machine_status`), else `IDLE`, per `_set_machine_status` (✅ Q9). A stored status that is not a `MachineEventTypeEnum` value raises `ValueError`.
- **R8.** With a component: component activity `work_order_completed` `Work order <number> completed: <title>` plus `. <completion notes>` when there are notes *(revisit after launch)*. [BUG-1884] Not written when the component is not in the order's workspace; the completion goes on. *(Today: written for any stored id.)*
- **R9.** Event `completed` `Work order <number> marked complete`: metadata = `completed_at`, planned date and variance, then `event_metadata_extra`, then `completed_by_names`, `completed_by_name` (same text), `completed_by_user_ids`; plus `recorded_by = performer` when the first completer is someone else, or `completed_by = performer` when it is the performer; neither with no completers.
- **R10.** Without a machine, `INSTALL` / `REPLACE` / `BORROW` lines do nothing at completion (as R1 of `_apply_item_completion`; this method has no state check of its own). [BUG-2930] (OQ-57) Such an order can no longer be produced through `update_work_order` (R13a); tests build it directly. *(Today: reachable by removing the machine from a draft; the stock taken at start is recorded nowhere, verified.)*
- **R11.** Returns the order.
- **R18.** [BUG-2916] (HR-10) (G9, decided by Claude under the reviewer's delegation, 2026-11-21) `finalize_completion` takes no lock of its own: it receives an order its caller has already loaded and checked. The lock belongs where the state check is: `WorkOrderService.complete_work_order` reads the order `FOR UPDATE` before its `IN_PROGRESS` check (a rule of the future work order service spec), and `complete_as_planned` per its R11. Tested there, not here. *(Today: no lock anywhere.)*

## `void_work_order(session, wo_id, workspace_id, user_id, void_note)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderService.void_work_order`, which first deletes a draft invoice)
**Rules:**
- **R1.** Order per `get_work_order`.
- **R2.** `COMPLETED` → 400 `Cannot void a completed work order` (consistent with the freeze; owner 2026-11-14).
- **R3.** `VOIDED` → 400 `Work order is already voided`.
- **R4.** `IN_PROGRESS`: every consumed live line is returned per `_reverse_item_consumption` (verified storage back to its level before).
- **R5.** `IN_PROGRESS` with a machine: status back to the status before start, else `IDLE`.
- **R6.** `DRAFT`: no stock, no machine change.
- **R7.** Approvals cleared per `reset_approvals` with reason `Work order voided`; the order's `approved_by` / `approved_at` stay.
- **R8.** `status = VOIDED`, `void_note` as given, `voided_at = utcnow()`, `voided_by = user_id`; flushed; event `voided` `Work order <number> voided. Reason: <note>` (metadata `void_note`). [BUG-2918] (P5) A blank note is refused (422 in the schema). *(Today: `"  "` stored, verified.)*
- **R9.** Lines are not deleted.
- **R10.** [BUG-2916] (HR-10) Row lock before R2. *(Today: none.)*

---

## `_ensure_catalog_item_not_on_wo(session, work_order_id, item_id, workspace_id, *, exclude_item_id=None)`
**Shape:** validator · **Persistence:** reads · **Visibility:** internal (used by: `add_item`)
**Rules:** **R1.** A live line of the order with that item (other than `exclude_item_id`) → 409 with `catalog_item_already_on_order_detail` (`<item name> is already on this order`). Soft-deleted lines do not count.

## `_guard_item_mutations(wo)`
**Shape:** validator · **Persistence:** pure · **Visibility:** internal
**Rules:**
- **R1.** Order with `uses_inventory = false` → 400 `This work order does not use stock items` (checked first).
- **R2.** Locked → 400 `Work order is completed` / `Work order is voided`.

## `add_item(session, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /work-orders/{id}/items/`, template and sheet paths)

**Inputs:** `WorkOrderItemCreate` — `work_order_id`, `item_id`, `quantity` (default 1), `notes?`, `uses_inventory` (default false), `source_location_type?`, `source_location_id?`, `action_type` (`CONSUME` | `INSTALL` | `REPLACE` | `BORROW`, default `CONSUME`; anything else 422), `replaced_item_id?`.

**Rules:**
- **R1.** Order per `get_work_order`, then `_guard_item_mutations`.
- **R2.** `uses_inventory` with no source type or id → 400 `Select a source location for this item`.
- **R3.** A non-`CONSUME` line without `uses_inventory` → 400 `<Install|Replace|Borrow> requires "uses inventory" to be on`; on an order with no machine → 400 `Install/Replace/Borrow only apply to work orders that target a machine`.
- **R4.** `REPLACE` without `replaced_item_id` → 400 `Select the item being replaced`; a replaced item not in the workspace → 404 `Item with ID <id> not found`.
- **R5.** A `replaced_item_id` on any other action → 400 `replaced_item_id only applies to Replace`.
- **R5a.** [BUG-2912, BUG-2913] (P1, P2) quantity > 0 with ≤ 2 decimals; else 422. *(Today: any value.)*
- **R5b.** [BUG-2914] (P3) With `uses_inventory`, a fractional quantity → 400 `<item name> has a fractional quantity; inventory consumption requires whole units`, nothing written. *(Today: accepted; start then fails.)*
- **R6.** The item already on a live line of the order → 409 (`_ensure_catalog_item_not_on_wo`).
- **R6a.** [BUG-2927] (HR-16) With `uses_inventory`, a source that is not a live factory (`storage`) or live machine (`machine`) of the workspace → 404 `Factory with ID <id> not found` / `Machine with ID <id> not found`; another type → 400 `Unsupported source location type: <type>`. *(Today: stored; refused at consumption.)*
- **R7.** Order of checks: R1, R2, R3, R4/R5, R5a (schema), R5b, R6, R6a.
- **R8.** The line is created with every field, `workspace_id`, `created_by = user_id`; flushed.
- **R9.** Event `item_added` `Added <quantity> <item name>` (metadata `item_id`, `item_name`). The quantity is printed as sent, not as stored: `Decimal("2")` → `Added 2 Bolt`, `Decimal("2.50")` → `Added 2.50 Bolt` (G17).
- **R10.** `DRAFT` with recorded approvals → `reset_approvals` reason `Items edited`.
- **R11.** `IN_PROGRESS` → consumed at once per `_consume_item` (and component entry per its R7).
- **R12.** [BUG-1016] An `item_id` not in the workspace → 404 `Item with ID <id> not found`. *(Today: stored.)*
- **R13.** Returns the line.
- **R14.** [BUG-2916] (HR-10) On an `IN_PROGRESS` order the order row is locked before the state check. *(Today: none.)*

## `update_item(session, item_id, data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /work-orders/{id}/items/{item_id}/`)

**Inputs:** `WorkOrderItemUpdate` — `quantity?`, `notes?`, `uses_inventory?`, `source_location_type?`, `source_location_id?` (no action type, item or replaced item).

**Rules:**
- **R1.** A line not in the workspace, or soft-deleted → 404 `Work order item not found`.
- **R2.** Its order per `get_work_order`, then `_guard_item_mutations`.
- **R3.** `null` fields are dropped; nothing left → the line is returned unchanged, nothing written.
- **R4.** Consumed line: any field other than `quantity` / `notes` → 400 `Consumed lines only support quantity and notes updates`.
- **R5.** Consumed line, quantity changed: stock adjusted per `_adjust_consumed_item_quantity` first, then the line written (`updated_by`), then event `item_quantity_adjusted` `Adjusted <name> from <old> to <new>` (metadata `item_id`, `old_quantity`, `new_quantity` as text). No approval reset.
- **R6.** Consumed line, only notes (or the same quantity): written, no event.
- **R7.** Line not consumed: written with the fields and `updated_by`; event `item_updated` `Item line <id> updated`.
- **R7a.** [BUG-2927] (HR-16) As `add_item` R6a for a changed source. *(Today: stored.)*
- **R7b.** [BUG-2912, BUG-2913] As `add_item` R5a.
- **R7c.** [BUG-2914] As `add_item` R5b for a line that will use inventory after the update.
- **R8.** Not consumed, `DRAFT` with recorded approvals → `reset_approvals` reason `Items edited`.
- **R9.** Not consumed, `IN_PROGRESS` → `_consume_item` (a line just switched to inventory is consumed now; a missing source → 400).
- **R10.** [BUG-2915] (HR-9) A request that changes no value writes nothing, logs nothing and resets nothing. *(Today: `updated_by`, `item_updated`, reset.)*
- **R11.** [BUG-2916] (HR-10) Order and line rows locked on an `IN_PROGRESS` order. *(Today: none.)*

## `remove_item(session, item_id, workspace_id, user_id)`
**Shape:** soft-delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /work-orders/{id}/items/{item_id}/`)
**Rules:**
- **R1.** Line as `update_item` R1; order per `get_work_order` and `_guard_item_mutations` (locked → `Work order is completed` / `… voided`). (A later second "completed or voided" check, lines 1467–1471, is dead code to be removed — Q8; not specified.)
- **R3.** `IN_PROGRESS` with a consumed inventory line: the stock goes back per `_reverse_item_consumption`.
- **R4.** The line gets `is_deleted = True`, `deleted_at = utcnow()`, `deleted_by = user_id`; flushed.
- **R5.** Event `item_voided` `Voided <name>` for a line that was consumed, else `item_removed` `Removed <name>`.
- **R6.** `DRAFT` with recorded approvals → `reset_approvals` reason `Items edited`.
- **R7.** Returns the line.
- **R9.** [BUG-2916] (HR-10) Locks as `update_item` R11.

## `get_items(session, wo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public
**Rules:**
- **R1.** The order must exist per `get_work_order`.
- **R2.** Its live lines per work order item DAO `get_by_work_order` ([BUG-1272] `id` order).
- **R3.** [BUG-1273] (HR-4) An `include_deleted` option (default false) returns the soft-deleted lines too *(requires new parameter, reachable from `GET /work-orders/{id}/items/`)*.

---

## `_apply_sheet_entry_lines(session, wo, *, items, approvers, machine_id, factory_id, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** internal (used by: `sheet_entry`, with `approvers=[]`)
**Rules:**
- **R1.** Each item dict becomes a line per `add_item`: source type = given or `storage`; source id = given, else the machine for `machine`, else the factory; `uses_inventory = True`; action = given or `CONSUME`; quantity as `Decimal(str(q))`.
- **R2.** Each approver dict per `add_approver`; a 409 is skipped, any other refusal propagates. [BUG-1206] The 409 propagates too. (Never reached today: the only caller passes no approvers.)

## `sheet_entry(session, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /work-orders/sheet-entry/`)

**Inputs:** `WorkOrderSheetEntryCreate` — `machine_id`, `work_order_type_id`, `planned_date` (required), `assigned_to?`, `description?`, `priority`, `account_id?`, `cost?`, `template_id?`, `recurrence_end_date?`, `items[]` (`item_id`, `quantity`, `action_type`, `source_location_type` default `storage`, `source_location_id?`, `replaced_item_id?`), `approvers[]` (`user_id`, `approver_slot?`).

**Rules:**
- **R1.** A machine not in the workspace → 404 `Machine with ID <id> not found` ([BUG-2920] soft-deleted → the same, *today accepted*).
- **R2.** A type not in the workspace → 404 `Work order type not found` ([BUG-1228] soft-deleted).
- **R3.** The order per `create_work_order`: title `<type> — <machine>`, factory = the machine's, `uses_inventory` = whether `items` is non-empty, the other fields from the entry.
- **R4.** A truthy `template_id` is stored on the order (checked in R9).
- **R5.** With items: lines per `_apply_sheet_entry_lines`.
- **R6.** An order saved without items has `uses_inventory = false` and can never get lines (`_guard_item_mutations` R1).
- **R7.** Each approver per `add_approver`; a 409 is skipped, other refusals propagate. [BUG-1206] The 409 propagates: one person twice → 409, nothing saved. *(Today: the second line is dropped, verified in the approver spec.)*
- **R8.** Recurrence per `_maybe_seed_template_recurrence` when `template_id` is truthy.
- **R9.** The template is read per `get_template`: another workspace's or unknown → 404, nothing saved (service rollback). [BUG-2928] (Q5) An inactive template → 400 `Template is inactive`, nothing saved. *(Today: accepted when not recurring.)*
- **R10.** Returns the order.

## `sync_recurrence_drafts_for_machine(session, *, workspace_id, user_id, template, machine_id, range_start, range_end)`
**Shape:** update · **Persistence:** writes · **Visibility:** internal in practice (used by: `_maybe_seed_template_recurrence`)
**Rules:**
- **R1.** Every row of work order DAO `list_drafts_outside_range_for_template_machine` is soft-deleted (`deleted_by = user_id`); flushed.
- **R2.** Then drafts per `generate_drafts_for_anchored_range` (template manager R1–R7). No event, no invoice handling.

## `_maybe_seed_template_recurrence(session, *, template_id, workspace_id, user_id, machine_id, planned_date, recurrence_end_date)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** internal
**Rules:**
- **R1.** Template per `get_template` (404). Not recurring → nothing.
- **R2.** No `recurrence_end_date`: template without `next_generation_date` → 400 `recurrence_end_date is required when placing an unanchored recurring template`; with one → nothing.
- **R3.** End date given, template without `next_generation_date`: anchored per `seed_recurrence_from_planned_date` (a `ValueError` → 400 with its text), flushed, drafts per `generate_drafts_for_anchored_range`.
- **R4.** Template anchored with the same start (= `planned_date`) and end → nothing.
- **R5.** Otherwise re-anchored per `reseed_recurrence_program` (`ValueError` → 400), flushed, then `sync_recurrence_drafts_for_machine` over `planned_date`..`recurrence_end_date`.

## `list_sheet_orders(…)` · `count_sheet_orders(…)` · `sheet_daily_counts(…)`
**Shape:** list / compute · **Persistence:** reads · **Visibility:** public (used by: `GET /work-orders/sheet/`, `/sheet/daily-counts/`)
**Rules:**
- **R0.** (G11) Parameters: `list_sheet_orders(session, workspace_id, factory_id=None, machine_id=None, planned_date_from=None, planned_date_to=None, status=None, status_scope=None, work_order_type_id=None, priority=None, exclude_completed=False, search=None, skip=0, limit=50)`; `count_sheet_orders` the same without `skip` / `limit`; `sheet_daily_counts(session, workspace_id, factory_id=None, machine_id=None, planned_date_from=None, planned_date_to=None, status=None, work_order_type_id=None, priority=None)`. `status` / `wo_status` take `WorkOrderStatusEnum`, `priority` `WorkOrderPriorityEnum`.
- **R1.** `list_sheet_orders` returns work order DAO `list_for_sheet` with the same arguments (default `limit` 50); `count_sheet_orders` returns `count_for_sheet` ([BUG-2672], [BUG-2673], [BUG-2674] there).
- **R2.** `sheet_daily_counts` returns `count_by_calendar_date_for_sheet` with each date key as ISO text (`{"2026-03-10": 2}`); no date → `{}` ([BUG-2675] there).

---

## `log_event(session, wo_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: this manager, the service, `AttachmentManager`)
**Rules:**
- **R1.** One `work_order_events` row with the arguments as given (metadata in `metadata_json`; `None` stored as JSON null); flushed; returned.
- **R2.** [BUG-1192] (HR-16) An order not in the workspace (another workspace's, unknown, `0`) → 404 `Work order with ID <id> not found`, nothing written. *(Today: stored under the caller's workspace.)* A soft-deleted order of the workspace is accepted (history).

## `list_events(session, wo_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /work-orders/{id}/events/`)
**Rules:**
- **R1.** The order must exist per `get_work_order`.
- **R2.** `(event, performer profile or None)` per event, newest first (event DAO `get_by_order`); no performer → `None`.

---

### Performer, ledger source and fallback cost (G18; facts from the code)
Applies to every callable below; it adds no new behaviour, it pins values the rules left implicit.
- **Performer.**
  - Order events: `started` (`start_work_order` and `complete_as_planned`), `voided` and `completed` have `performed_by` = the `user_id` passed to the method. For `finalize_completion` that is `performed_by_user_id`: the person recording the completion, **not** the workers in `completed_by_user_id(s)`. When the first completer differs, `completed` metadata has `recorded_by` = `performed_by_user_id` (rule unchanged).
  - Machine activity: `work_order_completed` `Work order completed: <number> — <title>` has `performed_by` = `performed_by_user_id`, metadata `{work_order_id}`. So does the machine-status change.
  - Ledger rows: every stock posting here passes the same `user_id`. Storage / damaged ledger rows store it as `performed_by` (and as `created_by` / `updated_by` on the inventory bucket); machine ledger rows and machine activities store it as `performed_by`. Per path: consumption at start = the starter; reversal at void = the voider; adjust (in-progress quantity change) = the `update_item` caller; completion postings (Install, Replace out / damaged / in, Borrow return) = `performed_by_user_id`.
- **Ledger source.** Every posting here (consumption, `consumption` adjust-up, `consumption_reversal` reversal and adjust-down, `work_order_install`, `work_order_replace_out`, `work_order_replace_damaged`, `work_order_replace_in`, `work_order_borrow_returned`) has `source_type = 'work_order'` and `source_id = wo.id` (the order's id, not the line's).
- **Fallback cost.** Consumption sets the line's `unit_cost` to the source's average at that moment (`avg_price`, or `0` when it has none), and only consumed lines are touched at completion. So Install, Replace-in and Borrow return post at the line's `unit_cost`, and `0.00` when it is `None` (legacy rows) or `0` (`item.unit_cost or Decimal(0)`). The same fallback holds for the reversal and the adjust-down posting. The removed part in a Replace always posts at `0.00` (OQ-59, intended).
- **Ledger notes (G19).** `<number>` = the order's `work_order_number`, `<name>` = the line's item name, `<replaced name>` = the replaced item's name:
  - Replace out (machine): `<number> — <replaced name> removed for replacement`.
  - Replace damaged (order's factory, damaged bucket): `<number> — <replaced name> moved to damaged stock`.
  - Replace in (machine): `<number> — <name> installed (replacement)`.
  - Borrow return (line's source): `<number> — <name> returned`.
  - For reference: Install `<number> — <name> installed`; void reversal `<number> voided — <name> returned`.
- **Damaged stock factory.** The removed part of a Replace goes to the damaged bucket of the **order's** factory (`wo.factory_id`). It does not go to the line's source location or to a factory looked up from the machine. Once BUG-2921 is fixed the order's factory is always the machine's factory, so this is where the part physically is. Today a legacy order whose machine sits in another factory puts it in the order's factory (covered by BUG-2921, no new bug).

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 98 | locked statuses | `_is_locked` R1 |
| 102 | any approved | `_has_recorded_approvals` R1 |
| 105 | title / factory | `is_approvable` R1 |
| 108–112 | gap reasons | `approvability_gap_reason` R1–R3 |
| 115–124 | None / date / Decimal whole / enum / text / blank | `_format_scalar_value` R1–R5 |
| 129–139 | missing; datetime; delta 0; 1 vs n; early/late | `_variance_vs_planned` R1–R4 |
| 150–154 | planned date; variance | `_schedule_metadata_for_actual` R2 |
| 172, 176, 178 | field absent; equal; type field | `_collect_field_changes` R1–R3 |
| 193–196 | None; found | `_work_order_type_name` R1, R2 |
| 199–204 | account set | `resolve_invoice_account_id` R1, R2 |
| 217–238 | type name; machine; component; target; factory | `_derive_default_title` R1–R5 |
| 249–265 | factory, type, account checks | `create_work_order` R1–R3 |
| 270–282 | blank title | `create_work_order` R4 |
| 290 | assigned_to | `create_work_order` R6 |
| 304 | planned date | `create_work_order` R7 |
| 322–327 | inactive; machine | `create_work_order_from_template` R1, R2 |
| 335–344 | `or` fallbacks | `create_work_order_from_template` R3 |
| 351–362 | uses_inventory; lines | R5, R6 |
| 364–373 | requires_approval; except | R7, R8 |
| 388–391 | missing; deleted | `update_work_order` R1, R2 |
| 400–410 | explicit fields; title pop | R3, R4 |
| 411–413 | empty | R5 |
| 415–424 | locked; in-progress details | R6–R8 |
| 425–434 | account; type | R9 |
| 439–445 | reset conditions | R12 |
| 447–481 | changes; assigned_to; workers; schedule | R13 |
| 483–501 | structural change on draft | R15 |
| 505–506 | assigned_to without changes | R17 |
| 512–514 | found | `get_work_order` R1 |
| 549, 558 | cutoff; loop | `bulk_delete_future_recurrence_drafts` R1–R3 |
| 565–576 | missing; deleted; environment | `delete_work_order` R1–R4 |
| 586–591 | per approver; member | `list_approvers` R2 |
| 597–601 | explicit required | `approval_summary` R2, R3 |
| 612–622 | approved rows; count | `reset_approvals` R1–R3 |
| 631–652 | draft; met/stamp | `_recompute_approval_status` R1–R4 |
| 659–666 | locked; member; duplicate | `add_approver` R2–R4 |
| 675 | profile | `add_approver` R6 |
| 688–694 | locked; missing; profile | `remove_approver` R1–R3 |
| 707–718 | not approver; locked; approvable; value | `set_approval` R1–R4 |
| 730–742 | skip; source; fractional | `_consume_item` R1–R3 |
| 765–779 | source label; machine; component | `_consume_item` R6, R7 |
| 782 | not consumed | `_reverse_item_consumption` R1 |
| 818–832 | equal; status; whole/positive | `_adjust_consumed_item_quantity` R1–R3 |
| 840–885 | increase / decrease; unit cost None | R4–R7 |
| 889 | machine | R8 |
| 910–913 | skip conditions | `_apply_item_completion` R1 |
| 918–985 | INSTALL / REPLACE (on hand) / BORROW | R2–R8 |
| 1002–1004 | same status; note | `_set_machine_status` R2, R3 |
| 1015–1018 | started event | `_previous_machine_status` R1 |
| 1022–1031 | draft; approvals | `start_work_order` R2, R3 |
| 1038 | planned date empty | `start_work_order` R6 |
| 1042 | pending count | `start_work_order` R7 |
| 1069–1078 | pending; machine | `_run_start_side_effects` R1, R2 |
| 1087 | member | `_ensure_active_workspace_member` R1 |
| 1116–1141 | ids; single id; names; neither | `_resolve_completion_workers` R1–R4 |
| 1157–1177 | draft; planned; future; approvals | `complete_as_planned` R1–R5 |
| 1245 | notes not None | `finalize_completion` R3 |
| 1256–1275 | machine; explicit status; previous | R5–R7 |
| 1277–1284 | component; notes | R8 |
| 1289–1300 | extra; recorded_by / completed_by | R9 |
| 1310–1327 | completed; voided; in progress; consumed; machine | `void_work_order` R2–R6 |
| 1350–1355 | duplicate line | `_ensure_catalog_item_not_on_wo` R1 |
| 1358–1361 | uses_inventory; locked | `_guard_item_mutations` R1, R2 |
| 1368–1382 | source; non-consume; replace | `add_item` R2–R5 |
| 1396–1400 | draft reset; in progress consume | `add_item` R10, R11 |
| 1407–1414 | missing; empty | `update_item` R1, R3 |
| 1419–1447 | consumed; disallowed; qty changed | R4–R6 |
| 1453–1457 | draft reset; in progress | R8, R9 |
| 1462–1466 | missing; guard | `remove_item` R1 (1467–1471 dead, Not specified) |
| 1476–1489 | reverse; event type; reset | R3–R6 |
| 1509–1542 | source defaults; 409 skip | `_apply_sheet_entry_lines` R1, R2 |
| 1551–1559 | machine; type | `sheet_entry` R1, R2 |
| 1579, 1583, 1595–1607, 1609 | template; items; approvers; recurrence | R4–R8 |
| 1634–1644 | orphans | `sync_recurrence_drafts_for_machine` R1 |
| 1665–1710 | recurring; end date; anchored; same range; ValueError | `_maybe_seed_template_recurrence` R1–R5 |
| 1797 | date keys | `sheet_daily_counts` R2 |
| 1818 | performer | `list_events` R2 |

## Gap log
G1 (work_order_manager.cases.md gap 1) — Fact — Notes: modules of the order, template and item schemas.
G2 (gap 2) — Fact — `_set_machine_status` R5: `new_status` is a `MachineEventTypeEnum` member; the return is the stored status text or `None`.
G3 (gap 3) — Fact — Notes: quantities render as integers in stock / activity texts; `update_item` R5 renders `str(Decimal)` (old as held by the session, new as parsed), with a pinning recipe.
G4 (gap 4) — Fact — `_run_start_side_effects` R3: returns `(count, status_before)`.
G5 (gap 5) — Test mechanics — Notes: `uq_wo_template_approver` makes the template-path 409 impossible from stored data; trigger by patching `work_order_template_manager.get_approvers` to return a member twice.
G6 (gap 6) — Fact — `create_work_order_from_template` R3a: the `Maintenance` fallback needs a type named `""` (type always exists); Notes on storing empty names.
G7 (gap 7) — Fact — `remove_approver` R4a: the recompute's actor is `performed_by` (may be `None`).
G8 (gap 8) — Intent, decided by Claude under the reviewer's delegation (2026-11-21) — `create_work_order` R3b: the create-side check lives in `WorkOrderCreate` (ValidationError); the update-side merged check stays in the manager (HTTPException 422).
G9 (gap 9) — Intent, decided by Claude under the reviewer's delegation (2026-11-21) — `finalize_completion` R18 rewritten: no lock in this method; the service's `complete_work_order` locks before its state check (future service spec), `complete_as_planned` per R11. Card FC-22 to be retired.
G10 (gap 10) — Fact — every cost column involved is `Numeric(15, 2)`: `_consume_item` R5a and `_adjust_consumed_item_quantity` R7a (BUG-1040 rounding unobservable with stored data), new R6a with an observable half-up example (0.25 / 2 → 0.13). Card CI-14 to be retired; a card for R6a to be added. No owner question: nothing about stock value changes, only where the rounding can be seen.
G11 (gap 11) — Fact — full parameter lists of `list_work_orders` (heading) and the sheet lists (R0).
G12 (gap 12) — Fact — `add_approver` R6a: the `User #<id>` fallback is unreachable (profile always exists; an empty name is used as stored); `_resolve_completion_workers` R4a: an empty profile name does fall back; Notes on storing `""`.
G13 (gap 13) — Fact — Notes: write order of the events of one `update_work_order` call, and `list_events` order.
G14 (gap 14) — Fact — Notes: the storage and machine insufficient-stock texts.
G15 (gap 15) — House rule not applied — HR-10 also covers `add_approver` (R8) and `remove_approver` (R5): approval decisions with a state check after BUG-2931. Same fix as BUG-2916 (no new ID); house-rule line extended.
G16 (executor discrepancy, WOM-AIC-10) — fact, decided under delegation (2026-11-21) — the spec was wrong, not the code: `_apply_item_completion` R8 restated. A borrow return writes the `item_borrowed_returned` machine activity only for a machine source; a storage source gets only its ledger row. That matches every storage movement in the module (consumption from storage also writes no activity, because storage has no activity log), so it is not a bug and BUG-2891 stays unused. Card WOM-AIC-10: assert the activity only for a machine source; for a storage source assert the `work_order_borrow_returned` ledger row and no activity.
G17 (executor discrepancy, WOM-AI-01) — fact, decided under delegation (2026-11-21) — `add_item` R9 restated to today's text (quantity as sent). Not a bug: no event or activity text in this module formats quantities to 2 places, all of them print the value as held. Card WOM-AI-01 expects `Added 2 Bolt`.
G18 (verifier NEEDS WORK, 3 routed gaps) — Fact — new section "Performer, ledger source and fallback cost" before the Branch map: `performed_by` on started / completed / voided events, the machine completion activity and every ledger posting; `source_type='work_order'`, `source_id=wo.id` on all postings; cost fallback `unit_cost or 0`; the damaged part of a Replace goes to the order's factory (`wo.factory_id`; same as the machine's after BUG-2921). No rule renumbered, no new bug.
G19 (cases rev 4, 3 gaps) — Fact — `_adjust_consumed_item_quantity` R4 / R5: machine-source activity event types `consumption` / `consumption_reversed`; R5 notes in full `<number> — <name> qty reduced by <d>`; full ledger notes for Replace out / damaged / in and Borrow return added to the "Performer, ledger source and fallback cost" section. Also corrected G18's transaction type to `consumption_reversal` (`consumption_reversed` is the activity type).
