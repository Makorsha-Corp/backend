# Spec — `app/managers/transfer_order_manager.py`

> **Status:** APPROVED (2026-11-21; apply-review of the owner's OQ-55 answer and the 2026-11-19 delegated decisions; fill-gaps 2026-11-21, 9 gaps closed, no new question)
> **Source commit:** e48a092

> **Apply-review 2026-11-21.** The owner answered OQ-T1 in chat on 2026-11-21 (recorded as **OQ-55** in `docs/testing/owner-questions.md`): option (a), not the recommendation. The change is allowed but wipes every approval given → BUG-2903. Every delegated item below was applied as answered.
>
> **Review round 2026-11-19 (describe + delegated decisions).** Everything below the owner question is **decided by Claude under the reviewer's delegation (2026-11-19)** or by a house rule / precedent; none of it is the owner's own answer. Bugs **BUG-2892 … BUG-2903** are logged in `docs/testing/bugs.md` (block BUG-2892 … BUG-2911; 2904 … 2911 unused). Existing bugs whose rule lives here are cited with their own IDs (BUG-821, BUG-823, BUG-824, BUG-825, BUG-1018, BUG-1192, BUG-1194, BUG-1203, BUG-2657).
>
> **Base behaviour** is in `tests/unit/managers/base_manager.spec.md` (inherited, not used by any public method here) and `tests/unit/dao/base.spec.md` (`create` and `update` flush; `get_by_id_and_workspace` is raw). DAO reads are specified in `tests/unit/dao/transfer_order.spec.md`, `transfer_order_approver.spec.md`, `transfer_order_event.spec.md`; stock posting in `tests/unit/managers/to_inventory.spec.md`. They are described here only as outcomes.
>
> **Transactions.** The service (`TransferOrderService`) wraps every write in TC1–TC6 of `tests/unit/services/base_service.spec.md`; this manager never commits. Every write here flushes.
>
> **Production deferred:** this module does not touch production. **Projects (revisit after launch):** a `project` location (a project component) appears only in event labels (`_format_location_id` R5) and as a destination type that BUG-825 refuses at entry; no project costing happens here.
>
> **Verified by running** (my own script `v1_to.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\ordersdesc\transfer_order\`, one transaction on `marker_test`, rolled back; nothing committed; `get_next_number` patched to a unique number to avoid the global index of BUG-2650): create with another workspace's destination factory accepted; the creator is the only approver, unapproved, summary `(0, 1, False)`; an empty update stamps `updated_by`; an update to source = destination accepted; `updated` events with labels (a foreign factory shows as `Factory #<id>`); `description: null` keeps the old text; a route edit after one approval refused 400; after one of two approvals, `required_approvals = 1` accepted → `(1, 1, True)`; `-1` accepted → `(1, -1, True)`; `transferred_at: null, transferred_by: null` leaves both unchanged; quantity edit refused with an approval, the line `approved` flag accepted (stamps `approved_by`); a second approve writes a second `approved` event; on a completed order: withdrawing an approval and removing an approver succeed, an empty update succeeds, a second completion returns the order, delete refused 400; get from another workspace 404. **Read, not run:** `TransferOrderService`, `app/api/v1/endpoints/transfer_orders.py`, `approval_notification_service`, `attachment_manager` (calls `log_event`), the web app's `TransferOrderDetailPanel.tsx` and `ManageTransferOrderTransfersDialog.tsx`.

## Review
> All items answered and applied (2026-11-21). Nothing pending.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| OQ-T1 (OQ-55) | The number of approvals needed can be changed after approvals have started (down to 0) | bug (BUG-2903): allowed, but a real change wipes every approval given | **owner**, 2026-11-21 |
| HR-10 | Approving, deleting and guarded edits check state with no row lock | bug (BUG-2892) | house rule |
| HR-9 | Every update stamps `updated_by`, even when nothing changed | bug (BUG-2893) | house rule |
| HR-16 | A route may name another workspace's factory or machine | bug (BUG-2894) | house rule |
| P1 | Optional fields cannot be cleared; "Clear transfer" does nothing | bug (BUG-2895) | precedent BUG-753 / BUG-942 |
| P2 | A line's `approved` flag is writable but means nothing | bug (BUG-2896) | precedent BUG-751 |
| P3 | Approvers and approvals can be changed on a completed order | bug (BUG-2897) | precedent BUG-737 / BUG-756 |
| P4 | Approving twice is recorded twice | bug (BUG-2898) | precedent BUG-757 |
| P5 | `required_approvals` accepts negative numbers | bug (BUG-2901) | precedent BUG-362 |
| P6 | Events and approvers are read one profile at a time | bug (BUG-2902) | precedent BUG-1141 |
| Q1 | An edit can make source and destination the same, which create refuses | bug (BUG-2899) | Claude, delegated |
| Q2 | Changing a line's quantity or notes leaves no entry in the order's log | bug (BUG-2900) | Claude, delegated |
| Q3 | The manager's plain `list_transfer_orders` has no caller | remove | Claude, delegated |
| Q4 | The creator is added as the first approver | intended ✅ | Claude, delegated |
| Q5 | "Mark complete" stamps every unrecorded line as transferred now | intended ✅ | Claude, delegated |
| Q6 | Event labels name a deleted factory or machine by its name | intended ✅ | Claude, delegated |
| Q7 | BUG-825 (refuse `project` destination at entry) stays although projects are deferred | intended (keep BUG-825) ✅ | Claude, delegated |

### House-rule violations — applied automatically

- **HR-10** `set_approval` R7; `delete_transfer_order` R6; `add_approver` R6, `remove_approver` R5 (added G10); `_guard_confirmed_updates` R6, `_guard_item_mutations` R4 (used by `update_transfer_order`, `add_item`, `update_item`, `remove_item`) — each checks the order's state (completed? any approval given?) and then writes, with no row lock. Two approvers approving at once can both pass; a delete can pass its "not completed" check while a completion posts stock, leaving ledger rows for a deleted order; a quantity edit can pass "no approval yet" while an approver approves the old quantity. Intended: the transfer order row is read `SELECT … FOR UPDATE` before these checks; the loser sees the new state and gets the normal error. (The completion itself: BUG-821, `mark_order_complete` R9.)
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2892 (pattern `hr-10-unlocked-state-transition`, bundled as BUG-720). Rules listed (tagged).

- **HR-9** `update_transfer_order` R7 — `updated_by` is written on every successful call: an empty body, all-`null` body, unchanged values, and an empty body on a completed order (verified). Intended: written only when at least one field changes value.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-2893 (pattern `audit-stamp-on-noop`, as BUG-009 / BUG-740). Rule: `update_transfer_order` R7.

- **HR-16** `create_transfer_order` R2a, `update_transfer_order` R3a — the route's ids are stored unchecked: a source or destination factory / machine of another workspace is accepted (verified on create), and its id then shows in the order's own log (`Factory #<id>`). Completion later fails with 404 (to_inventory), so the order is stuck. Intended: create and update refuse a route end that is not a live row of the caller's workspace with 404 `Factory with ID {id} not found` / `Machine with ID {id} not found`, nothing written; a soft-deleted factory or machine is refused the same way (BUG-822 / BUG-340 precedent: deleted = missing). Status and line items: BUG-1018 (existing).
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2894 (pattern `cross-workspace-link-not-refused`). Rules: `create_transfer_order` R2a, `update_transfer_order` R3a.

Checked and **not** a new line here: **HR-1/2/3** — no names; `description` is free prose, `transferred_by` free text (person's name as typed). **HR-4** — transfer orders, lines, approvers and events have no soft-delete column. **HR-5/6/7/8** — paging, order and search live in the DAO (BUG-2654…2657 there); `get_items` inherits line ties (BUG-2657). **HR-15** — no money here; quantities are `Numeric(15,2)`, rounded by Postgres half away from zero. **HR-11…14** — no external system.

### Owner question — order workflow

### OQ-T1. The number of approvals needed can be changed after approvals have started — 🐞 BUG-2903 (owner, OQ-55)
**Background:** A transfer order lists approvers. By default every listed approver must approve ("All assigned"); a number typed into "Required approvals" replaces that (0 = no approval needed, per the owner's BUG-1203 rule). Once anyone has approved, the route and description are locked ("Withdraw all approvals before editing order details") and lines are locked ("Withdraw all approvals before editing transfer items"). The required number is **not** locked, and any member may change it.
**What happens today:** After approvals have started, anyone in the workspace can lower the number (to 1, or to 0) and the order immediately counts as approved and can be completed; raising it is also possible. Nothing is reset and only an `updated` log entry records it. (Verified: two approvers, one approved, required set to 1 → "1 of 1 — met".)
**Example:** TR-2026-031 moves 40 motors from Factory A to Factory B. The store manager (Karim) and the factory head (Nadia) are approvers. Karim approves; Nadia has doubts. A storekeeper changes "Required approvals" to 1 and clicks "Mark complete": 40 motors leave Factory A without Nadia's approval.
**Recommended answer:** bug — the required number is locked like the route: while any approval is given, changing it is refused with 400 "Withdraw all approvals before editing order details", nothing written. Before any approval it can be changed freely.
**Options, for the owner:**
- **Recommended — lock it once approving has started.** The number of approvals an order needs is set while the order is being prepared. As soon as one person approves, it can't be changed until approvals are withdrawn. *Example:* Karim has approved TR-2026-031. A storekeeper tries to change "Required approvals" from 2 to 1 and gets "Withdraw all approvals before editing order details". The order still waits for Nadia.
- **(a) Allow the change, but it wipes the approvals given so far.** Anyone may change the number at any time, but every approval already given is cleared and everyone has to approve again under the new rule. *Example:* the storekeeper changes the number from 2 to 1 on TR-2026-031. Karim's approval disappears; the order needs one fresh approval before it can be completed, and Karim or Nadia must click Approve again.
- **(b) Keep it as it is.** The number can be changed at any time without touching approvals given. This is the most flexible, but anyone in the workspace can effectively skip approval. *Example:* with Karim's approval in place, the storekeeper sets 1 and completes TR-2026-031 at once; Nadia is never asked.
**Rules affected:** `_guard_confirmed_updates` R4; `update_transfer_order` R3
**Answer:** owner, 2026-11-21 (OQ-55): option (a). The change is allowed, but it wipes every approval given so far and everyone approves again. (Chosen over the recommended lock.)
**Resolution:** 🐞 BUG-2903 (pattern `approval-rule-change-keeps-approvals`). Rules: `update_transfer_order` R6, R6a, R6b; `_guard_confirmed_updates` R4 (unchanged: `required_approvals` is not locked).
- **Decided (Claude, under the reviewer's delegation, 2026-11-21; coordinator's lean):** sending the value the order already has (`2` when it is `2`; `null` when it is already "All assigned") is a no-op: no approval wiped, no event, no `updated_by` stamp (HR-9, BUG-2893). Only a real change of the stored value wipes.
- **Decided (same):** the wipe follows the sibling `reset_approvals` of the expense / purchase / sales managers. Every approver row with `approved = true` gets `approved = false`, `approved_at = null`; approver rows stay; one `approvals_reset` event "Required approvals changed (<n> approval(s) cleared)", `performed_by = user_id`, no metadata, only when n ≥ 1. The normal `updated` event (R4) is still written. Clearing to `null` under BUG-2895 is a change like any other.
- **Notifications (note, not a rule here):** today nobody is told. The service calls `handle_order_update_notifications`, which reacts only to a change of *readiness* (route + lines). Changing `required_approvals` never changes readiness, so no notice goes out, and after the wipe approvers would not learn they must approve again. Unlike the expense and work order services, the transfer service reads no `_approvals_reset` marker. Noted for `docs/future/notifications.md`.

### Precedent matches — decided by Claude under the reviewer's delegation (2026-11-19)

### P1. Optional fields cannot be cleared; "Clear transfer" does nothing — 🐞 BUG-2895 (precedent)
**Background:** Updates drop every field sent as `null` (`exclude_none`). The web app's "Clear transfer" button sends `transferred_at: null, transferred_by: null`; emptying "Required approvals" sends `required_approvals: null` (meaning "All assigned").
**What happens today:** All three edits answer 200 and change nothing; the web app shows "Transfer cleared" while the line still shows as transferred (verified). An order description, once set, can only be replaced. The `transfer_cleared` event can never be written.
**Example:** A storekeeper records line 2 as transferred by mistake and clicks "Clear transfer": toast "Transfer cleared", the line still says "Transferred by Rahim on 1 Jan".
**Rules affected:** `update_transfer_order` R2; `update_item` R2, R9
**Answer:** bug — per BUG-753 / BUG-942 precedent: an explicit `null` clears `description` and `required_approvals` (back to "All assigned") on the order, and `transferred_at`, `transferred_by`, `notes` on a line; `null` for the route fields (order) or `quantity` (line) is refused with 422; omitted fields unchanged (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2895 (pattern `exclude-none-blocks-clear`). Clearing `required_approvals` to `null` is a change of it: it wipes given approvals under BUG-2903 (OQ-55).

### P2. A line's `approved` flag is writable but means nothing — 🐞 BUG-2896 (precedent)
**Background:** Approval is per approver, per order. `TransferOrderItemUpdate.approved` is stored on the line and stamps `approved_by` / `approved_at`; nothing in the backend reads it, and it is not locked by approvals.
**What happens today:** `{"approved": true}` on a line is saved (verified), even after approvals; no event.
**Example:** An API client sends `approved: true` for line 1; the line response shows approved by that user while the order shows 0 of 2 approvals.
**Rules affected:** `update_item` R6
**Answer:** bug — per BUG-751 precedent: `approved` is removed from `TransferOrderItemUpdate` (a request that sends it gets 422 under `extra="forbid"`, or has it ignored — the schema's choice, as BUG-751) (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2896 (pattern `client-writable-internal-field`).

### P3. Approvers and approvals can be changed on a completed order — 🐞 BUG-2897 (precedent)
**Background:** A completed order (`completed_at` set) refuses edits to its details and lines. Approver add / remove and approve / withdraw have no such check.
**What happens today:** On a completed order an approver can be added or removed, an approval withdrawn or given (verified: withdraw and remove succeed), changing what the finished order's approval record shows.
**Example:** TR-2026-020 was completed with 2 of 2 approvals. A week later Nadia withdraws hers; the order now shows "1 of 2 — not met" although the goods moved.
**Rules affected:** `add_approver` R5, `remove_approver` R4, `set_approval` R5
**Answer:** bug — per BUG-737 / BUG-756 precedent: on a completed order `add_approver`, `remove_approver` and `set_approval` (both directions) are refused with 400 "Transfer order is complete", nothing written (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2897 (pattern `missing-state-guard`).

### P4. Approving twice is recorded twice — 🐞 BUG-2898 (precedent)
**What happens today:** `set_approval` always writes and logs: a second Approve moves `approved_at` to now and writes a second `approved` event (verified); withdrawing when not approved writes `approval_withdrawn`.
**Example:** Karim double-clicks Approve: the log shows "Approved transfer order" twice, the second time 1 second later.
**Rules affected:** `set_approval` R6
**Answer:** bug — per BUG-757 precedent: setting the state the approver already has is a no-op: row returned unchanged, `approved_at` kept, no event (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2898 (pattern `non-idempotent-state-set`). The readiness check of R3 still runs first for `approved = true`.

### P5. `required_approvals` accepts negative numbers — 🐞 BUG-2901 (precedent)
**What happens today:** `TransferOrderUpdate.required_approvals` is a plain `int`; `-1` is stored and the order counts as approved with nobody approving (verified `(1, -1, True)`). The web app refuses negatives; the API does not.
**Example:** `{"required_approvals": -1}` → approvers panel "0 of −1 — met", "Mark complete" succeeds.
**Rules affected:** `approval_summary` R2a
**Answer:** bug — per BUG-362 precedent (expense spec Q4): `required_approvals` must be `null` or `>= 0`; anything else 422, nothing written; `0` keeps waiving approval (BUG-1203) (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2901 (pattern `unvalidated-numeric-range`; fix in `app/schemas/transfer_order.py`).

### P6. Events and approvers are read one profile at a time — 🐞 BUG-2902 (precedent)
**What happens today:** `list_events` reads the performer's profile once per event with a performer; `list_approvers` reads profile and membership once per approver (two reads each). A log of 500 entries by one person takes 501 reads.
**Example:** A long-running transfer order's activity tab gets slower with every entry.
**Rules affected:** `list_events` R4, `list_approvers` R4
**Answer:** bug — per BUG-1141 precedent: performers (and approvers' profiles and memberships) are read together, a fixed number of reads per call, result unchanged (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2902 (pattern `n-plus-one-read`).

### New questions — decided by Claude under the reviewer's delegation (2026-11-19)

### Q1. An edit can make source and destination the same, which create refuses — 🐞 BUG-2899
**Background:** Create refuses a route whose source equals its destination (same type and id). Update does not look. Approval refuses such a route, but with `required_approvals = 0` (or no approvers, until BUG-1203 is fixed) nobody has to approve.
**What happens today:** `PUT` with `destination_location_id` = the source factory is accepted (verified). Completing such an order writes a `transfer_out` and a `transfer_in` on the same bucket.
**Example:** TR-2026-040 goes Factory A → Factory B. Someone edits the destination to Factory A; the page shows "Factory A → Factory A", and with approvals waived "Mark complete" writes two ledger rows that cancel out.
**Rules affected:** `update_transfer_order` R3b; `mark_order_complete` R4a
**Answer:** bug — the update checks the merged route like create: 400 "Source and destination cannot be the same", nothing written; completion refuses such a route too (same 400), as a safety net for stored rows (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2899 (pattern `inconsistent-sibling-guard`).

### Q2. Changing a line's quantity or notes leaves no entry in the order's log — 🐞 BUG-2900
**Background:** Adding and removing a line, recording a transfer, route edits and approvals each write an event. `update_item` writes one only for `transferred_at`.
**What happens today:** Line 3 changed from 10 to 100 before approval leaves no trace in the activity log.
**Example:** Karim approves TR-2026-050 after Rahim, unseen, changed line 3 from 10 to 100 motors (before any approval). The log shows "Item #3 added" with no later change.
**Rules affected:** `update_item` R8a
**Answer:** bug — a change of `quantity` or `notes` that actually changes a value writes one `item_updated` event "Item #<n> updated", `performed_by` = the user, metadata `{"line_number", "item_id", "changes": [{field, label, from_value, to_value}]}` with labels "Quantity" / "Notes" and values formatted as `_format_scalar_value` (decided by Claude under the reviewer's delegation, 2026-11-19)
**Resolution:** 🐞 BUG-2900 (pattern `change-not-logged`).

### Q3. The manager's plain `list_transfer_orders` has no caller — ♻️ remove
**Background:** `GET /transfer-orders/` goes through `TransferOrderService.list_transfer_orders` → `list_transfer_orders_page` → the hub list. The manager's `list_transfer_orders` (and the DAO's `get_by_workspace` it calls, already ruled dead in the DAO spec Q3) is never called.
**Example:** No user-visible effect.
**Answer:** remove (decided by Claude under the reviewer's delegation, 2026-11-19; as expense spec Q24)
**Resolution:** moved to **Not specified** as dead code; listed in `docs/testing/dead-code-removal-checklist.md` (`app/managers/transfer_order_manager.py:348`). Not a bug, no ID.

### Q4. The creator is added as the first approver — ✅ intended
**What happens today:** Every new order gets one approver row: its creator, unapproved. With "All assigned" the creator's own approval completes the requirement.
**Answer:** intended ✅ — the web app relies on it; who may approve their own order is a permissions question (noted for `docs/future/permissions.md`) (decided by Claude under the reviewer's delegation, 2026-11-19)

### Q5. "Mark complete" stamps every unrecorded line as transferred now — ✅ intended
**What happens today:** Lines not recorded one by one get `transferred_at` = completion time and a `transfer_recorded` event; lines already recorded keep their time. Stock moves only at completion, for every line.
**Answer:** intended ✅ — completion means every line moved (decided by Claude under the reviewer's delegation, 2026-11-19)

### Q6. Event labels name a deleted factory or machine by its name — ✅ intended
**What happens today:** Change labels look up the location in the workspace, deleted rows included, so a deleted factory keeps its name in the log.
**Answer:** intended ✅ — the log is history (DAO spec precedent: order history names deleted locations) (decided by Claude under the reviewer's delegation, 2026-11-19)

### Q7. BUG-825 stays although projects are deferred — ✅ intended
**Background:** BUG-825 (reviewer, 2026-10) refuses destination type `project` at create / update because completion can never post to a project. Projects are deferred until after launch.
**Answer:** intended ✅ — BUG-825 is a guard against orders that can never complete, not project costing; it stays. Today's behaviour (accepted) is kept visible in the rule's *Today* note; revisit after launch (decided by Claude under the reviewer's delegation, 2026-11-19)

## Overview
Business logic for transfer orders: internal movements of catalog items between locations of one workspace (a factory's storage or damaged bucket, a machine; `project` exists only as a label). An order has a route (source and destination type + id), numbered lines (one per catalog item), approvers, and an append-only event log. Its stage is derived, never stored: **Draft** until the route and a line exist, then **Planned**, then **Completed** once `completed_at` is set (`current_status_id` is fixed at creation, BUG-1018 / BUG-2660). Approval locks the route and lines; completion moves the stock (through `post_transfer_order_inventory`) and freezes the order. Called by `TransferOrderService` (all public methods), `approval_notification_service` (`get_transfer_order`, `approval_summary`, `_ready_for_approval`, `_route_defined`) and `AttachmentManager` (`log_event`). Transfer orders have no invoice, so the invoice freeze (account invoice manager O1, F1–F7) does not apply.

**Callables:** 37 specified · 3 not specified
**Externals to mock:** `utcnow` (`app.managers.transfer_order_manager.utcnow`: `set_approval`, `mark_order_complete`). None else. Notifications are sent by the service, not here.
**Integration-only behavior:** the concurrency guarantees of the intended row locks (BUG-821, BUG-2892) need two sessions; the lock itself is checkable by capturing SQL (`FOR UPDATE`), as in `to_inventory.spec.md`.

**Notes for the test designer**
- Setup: `make_workspace`, `make_profile` (tests/unit/factories.py); `WorkspaceMember(workspace_id, user_id, role, status='active')`; `Status(workspace_id, name, comment)` for `current_status_id` (pass it explicitly; the default 1 is BUG-1018); `Factory(workspace_id, name, abbreviation)`; `Item(workspace_id, name, name_normalized, unit)`.
- Numbering: the transfer number index is global (BUG-2650). Patch `transfer_order_manager.to_dao.get_next_number` to return a unique string (e.g. with a uuid) in every create, or the second workspace's create fails.
- Completion moves real stock: seed the source bucket with an `inventory_ledger` row (see `to_inventory.spec.md` Notes) or patch `app.managers.transfer_order_manager.post_transfer_order_inventory` when only this module's effects are under test (it returns the number of lines posted).
- Events are rows of `transfer_order_events` (`TransferOrderEvent`, column `metadata` mapped as `metadata_json`).
- `approved_at` on a line uses SQL `now()` (transaction start); on an approver row it is `utcnow()`.

## Not specified
- `TransferOrderManager.__init__` — wires the DAOs, no logic.
- `transfer_order_manager` — module instance.
- `TransferOrderManager.list_transfer_orders` — dead code, to be removed (reviewer delegation, Q3).

---

## `_is_completed(record)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: guards, `delete_transfer_order`, `mark_order_complete`, `update_item`)

**Rules:**
- **R1.** True exactly when `completed_at` is set; any value counts.

---

## `_route_defined(record)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_route_valid`, `_validate_ready_for_approval`, `approval_notification_service`)

**Rules:**
- **R1.** True only when all four of source type, destination type, source id, destination id are truthy. An empty type string or an id of `0` counts as not set.

---

## `_route_valid(record)`
**Shape:** helper · **Persistence:** pure · **Visibility:** internal (used by: `_ready_for_approval`)

**Rules:**
- **R1.** False when the route is not defined (`_route_defined` R1).
- **R2.** False when source and destination have the same type **and** the same id (exact, case-sensitive type comparison); true otherwise (same id with a different type is valid).

---

## `_order_items(session, to, workspace_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal

**Rules:**
- **R1.** Returns the order's lines of `workspace_id`, by line number (ties: BUG-2657, DAO spec); a line stored under another workspace is not returned.

---

## `_ready_for_approval(session, record, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `TransferOrderService.update_transfer_order`, `add_item`, notifications)

**Rules:**
- **R1.** True when the route is valid (`_route_valid`) and the order has at least one line (`_order_items`); false otherwise. Approvals are not looked at.

---

## `_validate_ready_for_approval(session, record, workspace_id)`
**Shape:** validator · **Persistence:** reads · **Visibility:** internal (used by: `set_approval`)

**Rules:**
- **R1.** Route not defined → 400 "Set source and destination before approving".
- **R2.** Source equals destination (type and id) → 400 "Source and destination cannot be the same".
- **R3.** No line → 400 "Add at least one item before approving".
- **R4.** Checks run in that order; the first failing one is raised. Otherwise returns `None`.

---

## `_has_any_approval(session, to)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: both guards)

**Rules:**
- **R1.** True when at least one approver row of the order (in the order's own workspace) has `approved = True`; false with no approvers or none approved.

---

## `_format_scalar_value(field, value)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `_format_field_value`)

**Rules:**
- **R1.** `None` → `"—"`.
- **R2.** A `date` or `datetime` → its ISO text (`2026-03-04`, `2026-03-04T09:00:00`).
- **R3.** A whole `Decimal` → integer text (`Decimal("5.00")` → `"5"`); otherwise normalised (`Decimal("2.50")` → `"2.5"`).
- **R4.** Anything else → `str(value)` trimmed; empty after trimming → `"—"` (`"  "` → `"—"`, `True` → `"True"`).
- **R5.** `field` is not used. (Through `update_transfer_order` only `description` reaches this helper; R2/R3 are reachable by direct call, and by BUG-2900's line changes.)

---

## `_format_location_id(session, workspace_id, location_type, location_id)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal

**Rules:**
- **R1.** `location_id` `None` → `"—"`.
- **R2.** Type is compared lower-cased (`None` → `""`).
- **R3.** `storage` or `damaged` → the factory's name when a factory with that id exists in `workspace_id` (soft-deleted included, Q6); otherwise `"Factory #<id>"`. ✅
- **R4.** `machine` → the machine's name (same lookup, deleted included); otherwise `"Machine #<id>"`. ✅
- **R5.** `project` → the project component's name in the workspace; otherwise `"Project component #<id>"`. *(Projects: revisit after launch.)*
- **R6.** Any other type, or none → `"#<id>"`.
- **R7.** Another workspace's row is never named: its id gives the fallback text of R3–R5. (HR-16: after BUG-2894 such ids cannot be stored.)

---

## `_format_field_value(session, workspace_id, field, value, *, source_type, destination_type)`
**Shape:** mapper · **Persistence:** reads · **Visibility:** internal

**Rules:**
- **R1.** `source_location_type` / `destination_location_type`: falsy value → `"—"`; otherwise the label for its lower-cased value (`storage` → "Storage", `machine` → "Machine", `damaged` → "Damaged", `project` → "Project"; `"STORAGE"` → "Storage"); an unknown value is shown as sent.
- **R2.** `source_location_id` → `_format_location_id` with `source_type`; `destination_location_id` → with `destination_type`.
- **R3.** `required_approvals`: `None` → `"All assigned"`; otherwise its number as text (`0` → `"0"`).
- **R4.** Any other field → `_format_scalar_value`.

---

## `_collect_field_changes(session, workspace_id, record, update_dict)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `update_transfer_order`)

**Purpose:** List the logged fields an update actually changes, with display values before and after.

**Rules:**
- **R1.** Only these fields are considered, in this order, each with its label: source type "Source type", source location "Source location", destination type "Destination type", destination location "Destination location", `description` "Description", `required_approvals` "Required approvals". Other keys are ignored.
- **R2.** A field absent from `update_dict`, or equal to the stored value, gives no entry.
- **R3.** Each entry is `{field, label, from_value, to_value}`, values formatted by `_format_field_value`.
- **R4.** `from_value` of a location id is labelled with the **stored** type of that end; `to_value` with the type in `update_dict` when sent, else the stored type (moving a route end from a factory to a machine labels the new id as a machine).
- **R5.** Nothing changes → `[]`.

---

## `_log_field_change_event(session, to_id, workspace_id, user_id, event_type, description, changes)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** internal

**Rules:**
- **R1.** Empty `changes` → nothing written.
- **R2.** Otherwise one event via `log_event` with the given type and description, `performed_by = user_id`, metadata `{"changes": changes}`.
- **R3.** Returns `None` in both cases (G3).

---

## `_guard_confirmed_updates(session, record, update_dict)`
**Shape:** validator · **Persistence:** reads · **Visibility:** internal (used by: `update_transfer_order`)

**Rules:**
- **R1.** Completed order and a non-empty `update_dict` → 400 "Transfer order is complete and cannot be edited".
- **R2.** Completed order with an empty `update_dict` passes this check.
- **R3.** `current_status_id` sent (any value) → 400 "Status is derived from workflow state — use Mark complete instead" (checked after R1).
- **R4.** At least one approval given and any of source type, source id, destination type, destination id, `description` sent → 400 "Withdraw all approvals before editing order details". `required_approvals` alone passes (verified) ✅. Owner, OQ-55: it is not locked; a real change wipes the approvals instead (`update_transfer_order` R6a).
- **R5.** Checks in order R1, R3, R4. A sent value equal to the stored one still counts as "sent".
- **R6.** [BUG-2892] (HR-10) The order row is read `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`; no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused because the order read LEFT OUTER JOINs `statuses` — BUG-029 rule) before these checks. *(Today: no lock.)*
- **R7.** When every check passes it returns `None` and writes nothing (G3).

---

## `_guard_item_mutations(session, to, workspace_id)`
**Shape:** validator · **Persistence:** reads · **Visibility:** internal (used by: `add_item`, `update_item`, `remove_item`)

**Rules:**
- **R1.** Completed order → 400 "Transfer order is complete".
- **R2.** Otherwise, at least one approval given → 400 "Withdraw all approvals before editing transfer items".
- **R3.** Otherwise passes: returns `None`, writes nothing (G3).
- **R4.** [BUG-2892] (HR-10) The order row is read `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`; no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused because the order read LEFT OUTER JOINs `statuses` — BUG-029 rule) before these checks. *(Today: no lock.)*

---

## `create_transfer_order(session, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/`)

**Purpose:** Create a numbered order with its creator as first approver and optional lines.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `data.source_location_type`, `destination_location_type` | `str` | required; any text today (BUG-823: known types only, 422) |
| `data.source_location_id`, `destination_location_id` | `int` | required; not checked today (BUG-2894) |
| `data.description` | `str \| None` | stored as sent |
| `data.current_status_id` | `int`, default `1` | stored unchecked (BUG-1018) |
| `data.items` | list of `{item_id, quantity, notes}` or `None` | `None` = no lines; quantity any decimal today (BUG-824) |
| `workspace_id`, `user_id` | `int` | scope; creator |

**Returns:** the new `TransferOrder`, flushed, not committed.

**Rules:**
- **R1.** Source type and id both equal to destination type and id → 400 "Source and destination cannot be the same", nothing written. Comparison is exact (`storage` vs `Storage` differ).
- **R2.** The order is stored with `workspace_id`, `transfer_number` from the DAO (`TR-<year>-NNN`, DAO spec; BUG-2650…2653), `created_by = user_id`, the sent fields; `required_approvals` empty ("All assigned"); `completed_at` empty.
- **R2a.** [BUG-2894] (HR-16) A route end of type `storage` / `damaged` whose factory, or `machine` whose machine, is not a live row of `workspace_id` (missing, another workspace's, or soft-deleted) → 404 `Factory with ID {id} not found` / `Machine with ID {id} not found`, nothing written. *(Today: stored unchecked; verified with another workspace's factory.)*
- **R2b.** [BUG-1018] The status is the caller's workspace's (the fixed default is removed; a sent status outside the workspace → 404 `Status with ID {id} not found`); each line's `item_id` must exist in the workspace, else 404 `Item with ID {item_id} not found`; nothing written. Which status replaces the default is open (status spec O2). *(Today: both stored unchecked.)*
- **R2c.** [BUG-825] Destination type `project` → 400 "Project destination is not yet supported", nothing written. *(Today: accepted; completion can never succeed. Projects: revisit after launch; Q7.)* ✅
- **R2d.** [BUG-823] / [BUG-824] Location types outside the known ones and line quantities that are not whole numbers > 0 are refused by the schema (422). *(Today: accepted.)* The known types are exact, lower-case values (BUG-823 register row): source `storage`, `damaged`, `machine`; destination `storage`, `damaged`, `machine`, `project`. So `project` as a **source** → 422; `project` as a destination passes the schema and is then refused by R2c (400); `"Storage"`, `"warehouse"` and `""` → 422. Nothing is lower-cased for the caller (G7).
- **R2e.** Order of the entry checks (decided under the reviewer's delegation, 2026-11-21; G1): R1 (same route), R2d (schema), R2a (route ends), R2c (project destination), R2b (status, then each line's `item_id` in the sent order), then R4 (duplicate item). All of them run before anything is written. Consequence: once BUG-1018 is fixed, R4's `Item #<id>` fallback can no longer be reached through create (a foreign or missing item is refused by R2b first); R4 then always names the workspace's item. The fallback text stays the shared helper's (`assert_unique_catalog_item_ids`), not a rule of this method. *(Today: R2b does not exist and R4 runs after the order and approver rows are flushed.)*
- **R3.** One approver row is created: the creator, `assigned_by` = creator, `approved = False` (Q4). So a new order's summary is 0 of 1, not met. ✅
- **R4.** The same catalog item twice in `items` → 409 "<item name> appears more than once on this order" (name from the workspace's item, else `Item #<id>`).
- **R4b.** [BUG-2889] (G11, decided by Claude under the reviewer's delegation, 2026-11-21) The 409 of R4 is raised before anything is written: no `transfer_orders`, `transfer_order_approvers`, `transfer_order_items` or `transfer_order_events` row is added to the session (R2e). This is the manager's own contract; the service's rollback (TC3) hides the difference from the API. *(Today: the order and approver rows are already flushed when the 409 is raised.)*
- **R5.** Lines are created in the sent order with `line_number` 1, 2, 3 …, `workspace_id`, `transfer_order_id`, the sent `item_id`, `quantity`, `notes`; `approved = False`, nothing transferred.
- **R6.** No lines (`items` empty or `None`) is allowed (a Draft).
- **R7.** One event `created` "Transfer order created", `performed_by = user_id`, no metadata.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| source = destination | `HTTPException` 400 | `Source and destination cannot be the same` |
| duplicate catalog item | `HTTPException` 409 | `<name> appears more than once on this order` |
| [BUG-2894] foreign / missing / deleted route end | `HTTPException` 404 | `Factory with ID {id} not found` / `Machine with ID {id} not found` |
| [BUG-1018] foreign status / item | `HTTPException` 404 | `Status with ID {id} not found` / `Item with ID {item_id} not found` |
| [BUG-825] destination `project` | `HTTPException` 400 | `Project destination is not yet supported` |

**Side effects:** rows in `transfer_orders`, `transfer_order_approvers`, `transfer_order_items`, `transfer_order_events`; flushed.

---

## `update_transfer_order(session, to_id, data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /transfer-orders/{id}/`)

**Inputs:** `TransferOrderUpdate`: route fields, `current_status_id`, `required_approvals`, `description`, all optional.

**Returns:** the order, flushed.

**Rules:**
- **R1.** Order not in `workspace_id` (missing or another workspace's) → 404 "Transfer order with ID {to_id} not found".
- **R2.** Only fields sent with a non-null value are applied; a field sent as `null` is ignored (verified for `description`).
- **R2a.** [BUG-2895] An explicit `null` clears `description` and sets `required_approvals` back to empty ("All assigned"); `null` for a route field → 422; omitted fields unchanged. *(Today: every `null` ignored.)*
- **R3.** The guards of `_guard_confirmed_updates` R1–R5 apply before anything is written. `required_approvals` can be changed while approvals are given ✅ (OQ-55); its effect on approvals is R6a, R6b.
- **R3a.** [BUG-2894] (HR-16) A route end changed to a factory / machine that is not a live row of the workspace → 404 as `create_transfer_order` R2a, nothing written; the check is on the merged route (a type change alone re-checks the stored id under the new type). *(Today: stored unchecked.)* BUG-823 / BUG-825 apply to update the same way as create R2c, R2d.
- **R3b.** [BUG-2899] A merged route whose source equals its destination → 400 "Source and destination cannot be the same", nothing written. *(Today: accepted; verified.)*
- **R4.** When at least one logged field changes (`_collect_field_changes`), one `updated` event "Order details updated" is written with the changes, `performed_by = user_id`; otherwise no event.
- **R5.** The sent values are stored.
- **R6.** The new `required_approvals` is what `approval_summary` uses from then on.
- **R6a.** [BUG-2903] (owner, OQ-55) When the stored `required_approvals` actually changes (a different number, a number → `null` under BUG-2895, or `null` → a number), every approver row of the order with `approved = true` gets `approved = false` and `approved_at = null`; the approver rows stay. When at least one approval was cleared, one `approvals_reset` event "Required approvals changed (<n> approval(s) cleared)" is written, `performed_by = user_id`, no metadata; with none given, no such event. The order then needs fresh approvals under the new number (with `0` it is met at once, BUG-1203). The `updated` event of R4 is still written. *(Today: approvals kept; verified 2 approvers, 1 approved, set to 1 → 1 of 1, met.)*
- **R6b.** Sending the value `required_approvals` already has is a no-op for approvals: nothing cleared, no `approvals_reset` event (decided under the reviewer's delegation, 2026-11-21; with R7, no `updated_by` stamp either).
- **R6c.** When both are written, the `updated` event (R4) comes first and the `approvals_reset` event (R6a) second, both `performed_by = user_id`: in id order `updated` < `approvals_reset`, so `list_events` (newest first, then id descending) shows `approvals_reset` above `updated` (decided under the reviewer's delegation, 2026-11-21; G8).
- **R7.** [BUG-2893] (HR-9) `updated_by = user_id` only when at least one field changes value. *(Today: on every call that passes the guards, including `{}`, unchanged values and `{}` on a completed order; verified.)*

**Errors:** R1; guards; R3a, R3b; schema 422 (R2a, BUG-2901 for negative `required_approvals`).

**Side effects:** order row; at most one `updated` event; on a real `required_approvals` change, approver rows reset and at most one `approvals_reset` event (R6a); flushed.

---

## `get_transfer_order(session, to_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public

**Rules:**
- **R1.** Returns the order of `workspace_id` with that id, with its `current_status` relationship (the `Status` row) loaded eagerly in the same query (joined load), so reading `order.current_status` issues no further query (G5).
- **R2.** Missing, or another workspace's → 404 "Transfer order with ID {to_id} not found" (verified).

---

## Hub reads: `list_transfer_orders_for_hub`, `count_transfer_orders_for_hub`, `transfer_order_hub_stats`, `list_transfer_orders_recent_for_hub`, `count_transfer_orders_machine_involved_for_hub`, `transfer_order_pending_highlights_for_hub`
**Shape:** list / compute · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/`, `GET /transfer-orders/stats/`, via the service)

**Rules:**
- **R1.** Each returns exactly what the same-named DAO method returns for `workspace_id` and the given filters (`list_for_hub`, `count_for_hub`, `aggregate_hub_stats`, `list_recent_for_hub`, `count_machine_involved_for_hub`, `get_pending_highlights_for_hub`; `tests/unit/dao/transfer_order.spec.md`, including BUG-2654 … BUG-2660). Filters are passed through unchanged.
- **R2.** Defaults: hub list `skip = 0`, `limit = 50`; recent `limit = 10`.
- **R3.** Signatures (G2): `list_transfer_orders_for_hub(session, workspace_id, *, skip=0, limit=50, **filters)`; `list_transfer_orders_recent_for_hub(session, workspace_id, *, limit=10, **filters)`; the other four `(session, workspace_id, **filters)`. The manager declares no filter of its own and requires none; `**filters` go to the DAO as sent. The DAO's filter keywords (all optional): `date_from`, `date_to`, `status_ids`, `factory_id`, `source_location_type`, `destination_location_type`, `search`, `exclude_complete` (default `True`). A keyword the DAO does not know raises `TypeError`. A card may pass any of them (e.g. `exclude_complete=False`, `search="TR-"`) and compare with the DAO called with the same keywords.

---

## `delete_transfer_order(session, to_id, workspace_id)`
**Shape:** delete (hard) · **Persistence:** writes · **Visibility:** public (`DELETE /transfer-orders/{id}/`)

**Rules:**
- **R1.** Order not in the workspace → 404 "Transfer order with ID {to_id} not found".
- **R2.** Completed order → 400 "Cannot delete a completed transfer order", nothing removed.
- **R3.** Otherwise the order's lines, approvers and events are removed with it (lines explicitly, approvers through the ORM cascade, events through `ON DELETE CASCADE`); returns `None`. Approvals already given do not prevent the delete.
- **R4.** [BUG-2890] (HR-16; G12, decided by Claude under the reviewer's delegation, 2026-11-21) Every line of the order is removed with it, a line stored under another workspace (invalid data, HR-16) included: the delete succeeds and no `transfer_order_items` row with that `transfer_order_id` remains. *(Today: the line step removes only the workspace's own lines; for any other line the ORM's `line_items` backref (no `passive_deletes`) sets `transfer_order_id` to NULL at flush, the NOT NULL column refuses it and the delete fails with `IntegrityError`.)* Same-workspace lines cannot hit this: the line step loads all of them (no limit, no soft delete), and approvers (ORM `delete-orphan` cascade, any workspace) and events (no ORM relationship; `ON DELETE CASCADE`) are unaffected.
- **R5.** [BUG-1194] (owner, 2026-11-01) A delete writes one `workspace_audit_logs` row: `workspace_id`, `user_id` = the deleter, `action` = `transfer_order_deleted`, `resource_type` = `transfer_order`, `resource_id` = the order id, `metadata` = `{"number", "created_by", "created_at" (ISO)}`; a refused delete writes none; `user_id` becomes a required parameter (the endpoint passes the current user). *(Today: no trace, no `user_id` parameter.)*
- **R6.** [BUG-2892] (HR-10) The order row is read `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`; no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused because the order read LEFT OUTER JOINs `statuses` — BUG-029 rule) before the completed check. *(Today: no lock.)*

---

## `mark_order_complete(session, to_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/{id}/complete/`)

**Purpose:** Finish the order: record every line as transferred, move the stock, stamp completion.

**Rules:**
- **R1.** Order not in the workspace → 404 (`get_transfer_order` R2).
- **R2.** Already completed → the order is returned unchanged; nothing written, no event (verified).
- **R3.** Approvals not met (`approvals_met`) → 400 "Required approvals are not met", nothing written.
- **R4.** No line → 400 "Add at least one item before completing" (checked after R3).
- **R4a.** [BUG-2899] A route whose source equals its destination → 400 "Source and destination cannot be the same", nothing written. *(Today: completes.)*
- **R4b.** Order of the checks (decided under the reviewer's delegation, 2026-11-21; G6): R1, R2, R3, R4, then R4a, all before anything is written. So an already completed order with such a route is returned unchanged (R2), and an order with unmet approvals or no line gets R3's / R4's error, not R4a's.
- **R5.** Every line without `transferred_at` gets the current time (`utcnow`) and one `transfer_recorded` event "Item #<n> transfer recorded", metadata `{line_number, item_id}`; lines already recorded keep their time and get no event (Q5). ✅
- **R6.** Stock is posted for all lines (`post_transfer_order_inventory`, to_inventory spec): any error there (quantity, type, missing location, shortage) reaches the caller unchanged, and the service rolls everything back.
- **R7.** The order gets `completed_at` = now (`utcnow`), `completed_by` = `updated_by` = `user_id`.
- **R8.** When at least one line was posted: one `inventory_posted` event "<n> item(s) posted to inventory", metadata `{lines_posted: n}`. Then always one `order_completed` event "Transfer order marked complete". All events `performed_by = user_id`.
- **R9.** [BUG-821] (HR-10) The order row is read `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`; no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused because the order read LEFT OUTER JOINs `statuses` — BUG-029 rule) before the completed check, so two concurrent completions post each line once. *(Today: no lock.)*

**Errors:** R1, R3, R4, R4a; those of `post_transfer_order_inventory`.

**Side effects:** lines' `transferred_at`; ledger rows (to_inventory); order completion stamps; events; flushed.

---

## `_ensure_catalog_item_not_on_to(session, to_id, item_id, workspace_id, *, exclude_item_id=None)`
**Shape:** validator · **Persistence:** reads · **Visibility:** internal (used by: `add_item`)

**Rules:**
- **R1.** A line of the order (in the workspace) with the same `item_id`, other than `exclude_item_id`, → 409 "<item name> is already on this order" (name from the workspace's item, else `Item #<id>`).
- **R2.** Otherwise returns `None`. (`exclude_item_id` is never passed by its only caller.)

---

## `add_item(session, to_id, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/{id}/items/`)

**Rules:**
- **R1.** Order not in the workspace → 404.
- **R2.** Guards of `_guard_item_mutations` (completed → 400; any approval → 400).
- **R3.** The item already on the order → 409 (`_ensure_catalog_item_not_on_to` R1).
- **R4.** The line gets `line_number` = highest existing line number + 1 (1 on an empty order; gaps after removals are not reused below the highest), the sent `item_id`, `quantity`, `notes`.
- **R4a.** [BUG-1018] An `item_id` not in the workspace → 404 `Item with ID {item_id} not found`, nothing written. *(Today: accepted.)* [BUG-824] quantity validated by the schema.
- **R4b.** Order of the checks (decided under the reviewer's delegation, 2026-11-21; G1): R1, R2, R4a, then R3. A foreign or missing item gets R4a's 404, never R3's 409.
- **R5.** One `item_added` event "Item #<n> added", metadata `{item_id, line_number}`, `performed_by = user_id`.
- **R6.** Returns the new `TransferOrderItem` row, flushed (it has an `id`), with the values of R4 (G3).

---

## `update_item(session, item_id, data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /transfer-orders/{id}/items/{item_id}/`)

**Inputs:** `TransferOrderItemUpdate`: `quantity`, `approved`, `transferred_by`, `transferred_at`, `notes`, all optional.

**Rules:**
- **R1.** Line not in the workspace → 404 "Transfer order item not found"; its order not in the workspace → 404 "Transfer order with ID {id} not found"; completed order → 400 "Transfer order is complete".
- **R2.** Fields sent as `null` are ignored (verified for `transferred_at`, `transferred_by`).
- **R2a.** [BUG-2895] An explicit `null` clears `transferred_at`, `transferred_by`, `notes`; `quantity: null` → 422. *(Today: ignored; the web app's "Clear transfer" does nothing.)*
- **R3.** Sending `quantity` or `notes` applies `_guard_item_mutations` (any approval → 400 "Withdraw all approvals before editing transfer items"). `transferred_at`, `transferred_by` and `approved` are not locked by approvals.
- **R4.** Sending a `transferred_at` requires the order's approvals to be met (`approvals_met`) → else 400 "Required approvals are not met". Any time is accepted (past or future), and an already recorded line can be given a new time.
- **R5.** The line's sent fields are stored.
- **R6.** `approved: true` on a line not yet approved also sets `approved_by = user_id` and `approved_at` = database `now()`; `approved: false` stores false and keeps `approved_by` / `approved_at`. [BUG-2896] `approved` is not accepted at all. *(Today: stored as described.)*
- **R7.** Setting `transferred_at` on a line that had none writes one `transfer_recorded` event "Item #<n> transfer recorded", metadata `{line_number, item_id}`, `performed_by = user_id` (G9). Replacing an existing time writes nothing.
- **R8.** Clearing a recorded time writes `transfer_cleared` "Item #<n> transfer cleared" (no metadata), `performed_by = user_id` (G9). Unreachable today (R2); reachable after BUG-2895.
- **R8a.** [BUG-2900] A change of `quantity` or `notes` writes one `item_updated` event as decided in Q2; an unchanged value writes none. *(Today: no event.)*
- **R9.** Stock is not moved here; it moves only at `mark_order_complete`.
- **R10.** Returns the updated `TransferOrderItem` (the same row object, flushed, with the stored values) (G3).

---

## `remove_item(session, item_id, workspace_id, user_id)`
**Shape:** delete (hard) · **Persistence:** writes · **Visibility:** public (`DELETE /transfer-orders/{id}/items/{item_id}/`)

**Rules:**
- **R1.** Line not in the workspace → 404 "Transfer order item not found"; its order missing → 404.
- **R2.** Guards of `_guard_item_mutations`.
- **R3.** The line is deleted; other lines keep their numbers. One `item_removed` event "Item #<n> removed" (no metadata), `performed_by = user_id` (G9). Returns the deleted line object.

---

## `get_items(session, to_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public

**Rules:**
- **R1.** Order not in the workspace → 404.
- **R2.** Returns the order's lines as `_order_items` R1 (empty list when none).

---

## `list_approvers(session, to_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/{id}/approvers/`)

**Rules:**
- **R1.** Order not in the workspace → 404.
- **R2.** One tuple per approver row of the order in the workspace, by `assigned_at` (ties: BUG-1200): `(approver, profile or None, position or None)`.
- **R2a.** The profile is never `None` in practice (G4): `transfer_order_approvers.user_id` is NOT NULL with a foreign key to `profiles.id` (`ON DELETE CASCADE`), so an approver row always has a profile; deleting the profile deletes the row. `profiles.name` is NOT NULL but may be an empty string, which is returned as stored. No card can build the "no profile" case without disabling foreign keys; none is required.
- **R3.** `position` is the approver's membership position in this workspace, whatever the membership status; `None` without a membership.
- **R4.** [BUG-2902] Profiles and memberships are read together, a fixed number of reads per call. *(Today: two reads per approver.)*

---

## `approval_summary(session, to)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (used by: `approvals_met`, the service's approvers endpoint, notifications)

**Returns:** `(approved_count, required, met)`.

**Rules:**
- **R1.** `approved_count` = approver rows of the order (its own workspace) with `approved = True`.
- **R2.** `required` = `required_approvals` when set (`0` included); else the number of approver rows.
- **R2a.** [BUG-2901] A negative `required_approvals` cannot be stored (422 at entry). *(Today: used as is; `-1` → met.)*
- **R3.** `met` = `approved_count >= required`.
- **R4.** [BUG-1203] (owner) With `required_approvals` empty and no approver rows, `required = 1` and `met` is false; only an explicit `0` waives approval. *(Today: `required = 0`, met.)*

---

## `approvals_met(session, to)`
**Shape:** compute · **Persistence:** reads · **Visibility:** internal (used by: `mark_order_complete`, `update_item`)

**Rules:**
- **R1.** Returns `met` of `approval_summary`.

---

## `add_approver(session, to_id, user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/{id}/approvers/`)

**Rules:**
- **R1.** Order not in the workspace → 404.
- **R2.** `user_id` without a membership in this workspace, or with a status other than `active` → 400 "User is not an active member of this workspace".
- **R3.** Already an approver of the order → 409 "User is already an approver for this order".
- **R4.** Creates the row (`assigned_by`, `approved = False`) and one `approver_added` event "Added <name> as approver" (name from the profile, else `User #<id>`), `performed_by = assigned_by`, metadata `{user_id, user_name}`. Returns the row. Adding raises `required` when it is "All assigned".
- **R4a.** The `User #<id>` fallback of R4 cannot be reached (G4): R2 needs an active membership, and both the membership and the new approver row reference `profiles.id` through NOT NULL foreign keys, so the profile exists. An empty profile name gives "Added  as approver" and `user_name: ""`. The fallback branch (line 663) is unreachable code, as `sales_manager.spec.md` G8.
- **R5.** [BUG-2897] On a completed order → 400 "Transfer order is complete", nothing written. *(Today: added.)*
- **R6.** [BUG-2892] (HR-10) (G10, decided by Claude under the reviewer's delegation, 2026-11-21, matching `work_order_manager.spec.md` `add_approver` R8 / `remove_approver` R5) The transfer order row is read `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`; no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused because the order read LEFT OUTER JOINs `statuses` — BUG-029 rule) before the R5 state check: adding an approver changes whether approvals are met and can race a completion. The loser sees the new state and gets the normal error. *(Today: no lock.)*

---

## `remove_approver(session, to_id, user_id, workspace_id, performed_by=None)`
**Shape:** delete (hard) · **Persistence:** writes · **Visibility:** public (`DELETE /transfer-orders/{id}/approvers/{user_id}/`)

**Rules:**
- **R1.** No approver row for that order, user and workspace (also: an order of another workspace) → 404 "Approver not found". The order itself is not looked up.
- **R2.** Deletes the row, approved or not, and writes one `approver_removed` event "Removed <name> as approver" (`User #<id>` without a profile), `performed_by` as given (`None` allowed), metadata `{user_id, user_name}`.
- **R2a.** The `User #<id>` fallback of R2 cannot be reached (G4): the approver row found references `profiles.id` through a NOT NULL foreign key with `ON DELETE CASCADE`, so its profile exists. The fallback branch (line 682) is unreachable code, as `sales_manager.spec.md` G8.
- **R2b.** Returns `None` (G3).
- **R3.** Removing an approver may make approvals met (2 approvers, 1 approved, remove the other → 1 of 1).
- **R4.** [BUG-2897] On a completed order → 400 "Transfer order is complete", nothing written. *(Today: removed; verified.)*
- **R5.** [BUG-2892] (HR-10) (G10, decided by Claude under the reviewer's delegation, 2026-11-21, matching `work_order_manager.spec.md` `add_approver` R8 / `remove_approver` R5) Before R4's state check the order row is read `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`; no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused because the order read LEFT OUTER JOINs `statuses` — BUG-029 rule) (the order is then looked up, not only the approver row); removing an approver can make approvals met (R3). *(Today: no lock.)*

---

## `set_approval(session, to_id, user_id, workspace_id, approved)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST` / `DELETE /transfer-orders/{id}/approve/`)

**Rules:**
- **R1.** No approver row for that user on that order in the workspace → 403 "You are not an assigned approver for this order" (checked before the order lookup).
- **R2.** Order not in the workspace → 404 (reachable only with an approver row whose order is gone).
- **R3.** `approved = true` → `_validate_ready_for_approval` R1–R4 first. Withdrawing has no readiness check.
- **R4.** The row gets `approved` and `approved_at` = now (`utcnow`) when approving, `None` when withdrawing; one event `approved` "Approved transfer order" or `approval_withdrawn` "Withdrew approval", `performed_by = user_id`. Returns the row.
- **R5.** [BUG-2897] On a completed order, both directions → 400 "Transfer order is complete", nothing written. *(Today: allowed; verified for withdraw.)*
- **R6.** [BUG-2898] Setting the state the row already has returns it unchanged: no event, `approved_at` kept. *(Today: rewritten and logged again; verified.)*
- **R7.** [BUG-2892] (HR-10) The order row is read `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`; no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` is refused because the order read LEFT OUTER JOINs `statuses` — BUG-029 rule) before the checks. *(Today: no lock.)*

---

## `log_event(session, to_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** public (used by: this manager, `AttachmentManager`)

**Rules:**
- **R1.** Writes one `transfer_order_events` row with the given values (`metadata` stored as JSON, `None` allowed), flushes, returns it; `created_at` defaults to now.
- **R2.** [BUG-1192] (HR-16) A `to_id` that is not an order of `workspace_id` → 404 `Transfer order with ID {to_id} not found`, nothing written. *(Today: stored under the caller's workspace; a missing id fails at flush with `IntegrityError`.)*

---

## `list_events(session, to_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/{id}/events/`)

**Rules:**
- **R1.** Order not in the workspace → 404.
- **R2.** Returns `(event, performer profile or None)` for every event of the order in the workspace, newest first, then `id` descending (event DAO spec); no paging.
- **R3.** An event with no performer gets `None`; a performer with no profile row gets `None`.
- **R3a.** Facts for R3 (G4): `transfer_order_events.performed_by` is nullable with a foreign key to `profiles.id` (`ON DELETE SET NULL`). An event with no performer is reachable (`log_event(..., performed_by=None)`, e.g. `remove_approver` without `performed_by`, or a deleted profile); "a performer id with no profile row" cannot be stored, so only the first half of R3 can be tested.
- **R4.** [BUG-2902] Performers are read together, a fixed number of reads per call. *(Today: one read per event with a performer.)*

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 65 | `completed_at` set | `_is_completed` R1 |
| 68–73 | four route parts truthy | `_route_defined` R1 |
| 76–77 | route not defined | `_route_valid` R1 |
| 78–81 | same type and id | `_route_valid` R2 |
| 93–95 | route invalid / lines > 0 | `_ready_for_approval` R1 |
| 100–104 | route not defined | `_validate_ready_for_approval` R1 |
| 105–112 | same route | `_validate_ready_for_approval` R2 |
| 113–117 | no lines | `_validate_ready_for_approval` R3 |
| 123 | any approved | `_has_any_approval` R1 |
| 126–127 | `None` | `_format_scalar_value` R1 |
| 128–129 | date | `_format_scalar_value` R2 |
| 130–131 | Decimal whole / not | `_format_scalar_value` R3 |
| 132–133 | trimmed empty | `_format_scalar_value` R4 |
| 138–139 | id `None` | `_format_location_id` R1 |
| 141–145 | storage/damaged, found / not | `_format_location_id` R3 |
| 146–150 | machine, found / not | `_format_location_id` R4 |
| 151–155 | project, found / not | `_format_location_id` R5 |
| 156 | other type | `_format_location_id` R6 |
| 168–171 | type field, falsy / label / unknown | `_format_field_value` R1 |
| 172–175 | location id fields | `_format_field_value` R2 |
| 176–177 | `required_approvals` None / value | `_format_field_value` R3 |
| 178 | other | `_format_field_value` R4 |
| 188–189 | sent type else stored | `_collect_field_changes` R4 |
| 190–192 | field not sent | `_collect_field_changes` R1, R2 |
| 195–196 | unchanged | `_collect_field_changes` R2, R5 |
| 223–224 | no changes | `_log_field_change_event` R1 |
| 233–238 | completed and non-empty | `_guard_confirmed_updates` R1, R2 |
| 239–243 | `current_status_id` sent | `_guard_confirmed_updates` R3 |
| 244–248 | approval and route field | `_guard_confirmed_updates` R4 |
| 251–255 | completed | `_guard_item_mutations` R1 |
| 256–260 | any approval | `_guard_item_mutations` R2 |
| 268–275 | same route on create | `create_transfer_order` R1 |
| 278 | `items or []` | `create_transfer_order` R6 |
| 286–293 | creator approver | `create_transfer_order` R3 |
| 297–302 (util 20–34) | `item_id` None skipped / duplicate, name found / not | `create_transfer_order` R4 |
| 304–309 | loop over lines | `create_transfer_order` R5, R6 |
| 320–324 | not found | `update_transfer_order` R1 |
| 326 | `exclude_none` | `update_transfer_order` R2, R2a |
| 330–334 | changes present | `update_transfer_order` R4 |
| 336 | `updated_by` always | `update_transfer_order` R7 |
| 326–336 | `required_approvals` changed / same value (intended, BUG-2903; not in code today) | `update_transfer_order` R6a, R6b |
| 341–345 | not found | `get_transfer_order` R2 |
| 352–401 | pass-through | Hub reads R1, R2 |
| 405–409 | not found | `delete_transfer_order` R1 |
| 410–414 | completed | `delete_transfer_order` R2 |
| 419–423 | delete lines, order | `delete_transfer_order` R3, R4 |
| 433–434 | already completed | `mark_order_complete` R2 |
| 436–440 | approvals not met | `mark_order_complete` R3 |
| 443–447 | no lines | `mark_order_complete` R4 |
| 450–457 | line not yet transferred | `mark_order_complete` R5 |
| 460–462 | posting | `mark_order_complete` R6 |
| 469–475 | lines posted > 0 | `mark_order_complete` R8 |
| 494–503 (util 38–42) | same item, not excluded; name found / not | `_ensure_catalog_item_not_on_to` R1, R2 |
| 515 | `max(..., default=0)` | `add_item` R4 |
| 534–535 | line not found | `update_item` R1 |
| 538–542 | completed | `update_item` R1 |
| 546–547 | quantity / notes sent | `update_item` R3 |
| 549–554 | `transferred_at` set, approvals not met | `update_item` R4 |
| 556–559 | `approved` true and line not approved | `update_item` R6 |
| 564–570 | set and was not transferred | `update_item` R7 |
| 571–575 | cleared and was transferred (unreachable today) | `update_item` R8 |
| 581–582 | line not found | `remove_item` R1 |
| 609–614 | loop; member found / not | `list_approvers` R2, R3 |
| 622–627 | explicit / count / zero | `approval_summary` R2, R4 |
| 628 | `>=` | `approval_summary` R3 |
| 640–644 | not active member | `add_approver` R2 |
| 648–652 | already approver | `add_approver` R3 |
| 663 | profile found / not (not found unreachable) | `add_approver` R4, R4a |
| 679–680 | approver not found | `remove_approver` R1 |
| 682 | profile found / not (not found unreachable) | `remove_approver` R2, R2a |
| 698–702 | not an approver | `set_approval` R1 |
| 704–705 | approving → readiness | `set_approval` R3 |
| 707 | approved_at now / None | `set_approval` R4 |
| 711–712 | event type by direction | `set_approval` R4 |
| 723–733 | write event | `log_event` R1 |
| 743 | performer set / not | `list_events` R3 |

## Gap log
- G1 (`transfer_order_manager.cases.md` gap 1) — Intent, decided under the reviewer's delegation (2026-11-21) — `create_transfer_order` R2e: entry checks run R1, R2d, R2a, R2c, R2b, then R4, all before any write, so after BUG-1018 the `Item #<id>` fallback of R4 is not reachable through create; `add_item` R4b: R4a (item in workspace) runs before R3 (already on order). The fallback text of `_ensure_catalog_item_not_on_to` R1 stays reachable by direct call on a legacy line.
- G2 (gap 2) — Fact — Hub reads R3: manager signatures, no manager-level filters, the DAO's filter keywords and defaults (`exclude_complete=True`), unknown keyword → `TypeError`.
- G3 (gap 3) — Fact — Returns stated: `add_item` R6 (new line, flushed), `update_item` R10 (same row, updated), `remove_approver` R2b (`None`), `_guard_confirmed_updates` R7, `_guard_item_mutations` R3, `_log_field_change_event` R3 (`None`).
- G4 (gap 4) — Fact — `list_approvers` R2a, `add_approver` R4a, `remove_approver` R2a, `list_events` R3a: approver `user_id` is NOT NULL FK → `profiles` (CASCADE), event `performed_by` nullable FK (SET NULL), `profiles.name` NOT NULL but may be `""`. The profile-missing fallbacks (lines 663, 682) are unreachable; only "no performer" is testable.
- G5 (gap 5) — Fact — `get_transfer_order` R1: `current_status` is joined-loaded by the DAO query.
- G6 (gap 6) — Intent, decided under the reviewer's delegation (2026-11-21) — `mark_order_complete` R4b: R4a runs after R1–R4, before any write.
- G7 (gap 7) — Fact (BUG-823 register row) — `create_transfer_order` R2d: known types are exact lower-case values; `project` is a destination type only (then refused by R2c); `"Storage"` → 422, nothing lower-cased.
- G8 (gap 8) — Intent, decided under the reviewer's delegation (2026-11-21) — `update_transfer_order` R6c: `updated` first, then `approvals_reset`; both `performed_by = user_id`.
- G9 (gap 9) — Fact — `update_item` R7, R8 and `remove_item` R3: `performed_by = user_id`.
- G10 (coordinator follow-up after work order G15) — House rule not applied, decided under the reviewer's delegation (2026-11-21) — `add_approver` R6, `remove_approver` R5: row lock under BUG-2892 (HR-10), as the work order spec.
- G11 (cases rev 2 gap 10) — Contradiction, decided under the reviewer's delegation (2026-11-21) — R2e's order is intended: new `create_transfer_order` R4b [BUG-2889], the duplicate 409 writes nothing; R4 no longer states the flushed rows. TOM-C-11 becomes a strict xfail (BUG-2889) asserting no order or approver row after the 409.
- G12 (executor DISCREPANCY-1, TOM-D-02) — Fact + decided under the reviewer's delegation (2026-11-21) — R4 was wrong: a foreign-workspace line makes the delete fail with `IntegrityError` (ORM nulls its FK). Intended per HR-16: the delete removes every line of the order; R4 rewritten [BUG-2890], low priority. Checked: only foreign-workspace lines are affected. TOM-D-02 becomes a strict xfail (BUG-2890).
- G13 (coordinator, 2026-11-22, from transfer_order_service fill-gaps G1) — fact — every BUG-821 / BUG-2892 lock rule (`_guard_confirmed_updates` R6, `_guard_item_mutations` R4, `delete_transfer_order` R6, `mark_order_complete` R9, `add_approver` R6, `remove_approver` R5, `set_approval` R7) states the exact clause `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`), no `NOWAIT` / `SKIP LOCKED`; a plain `FOR UPDATE` on the joined order read is refused by Postgres (verified `v2_lock.py`). The HR-10 lines keep the short form. Decided by Claude under the reviewer's delegation (2026-11-22).
