# Spec — `app/services/transfer_order_service.py`

> **Status:** APPROVED (2026-11-21; apply-review: BUG-3142 per HR-10 and D1–D3 applied as decided under the reviewer's delegation, 2026-11-21; fill-gaps 2026-11-21, 5 gaps closed, no new question; nothing open)
> **Source commit:** e48a092

> **Form.** As `tests/unit/services/department_service.spec.md`. A service spec covers only what the service adds on top of its manager: the transaction (commit, rollback, re-read), the readiness snapshot and approval notifications, response shaping of the hub reads, and which arguments reach the manager. What the manager decides is **cited, not restated**: `tests/unit/managers/transfer_order_manager.spec.md` (APPROVED 2026-11-21, incl. OQ-55 / BUG-2903), stock posting `tests/unit/managers/to_inventory.spec.md`, hub reads `tests/unit/dao/transfer_order.spec.md` (OQ-39 / BUG-2659, OQ-40 / BUG-2660), notifications `tests/unit/services/approval_notification_service.spec.md`, DTO mappers `tests/unit/services/order_hub_stats_helpers.spec.md`. Transaction contract **TC1–TC6** is `tests/unit/services/base_service.spec.md`, cited as is.
>
> **Bug block:** BUG-3142 … BUG-3161 (provisional). Used: BUG-3142. Existing bugs written as rules here, no new ID: **BUG-1194** (`delete_transfer_order` needs the deleter), **BUG-2892** (row locks, manager), **BUG-2903** (OQ-55). Routed here by other specs and settled below: approval notification spec **FU-1** (readiness race, → BUG-3142); DAO spec **FU-3** (`exclude_complete` default, `"all"`; → D2, D3).
>
> **Production deferred:** this module does not touch production. **Projects (revisit after launch):** nothing here touches projects; the `project` destination is the manager's (BUG-825).
>
> **Verified by running** (my own script `v1_tos.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2desc\transfer_order\`, one outer transaction on `marker_test`, session as the unit-test `db` fixture (`join_transaction_mode="create_savepoint"`), rolled back; nothing persisted; `get_next_number` patched to unique numbers, `post_transfer_order_inventory` patched): create returns the row with `created_at` loaded and sends no notification; the first `add_item` that gives a routed order a line sends `approval_pending` "0 of 1 approval(s) collected" to the creator; `add_approver` on a ready order sends only `approval_assigned` "Assigned by Karim · ready for your approval · 0 of 2 approval(s) collected" to the new approver (actor excluded from the pending round); an edit that makes source = destination sends `section_confirm` "Add at least one item before approvals can proceed" to the creator; the edit back sends `approval_pending` to both pending approvers; a ready → ready edit, removing every line, approving, a `required_approvals` change and completion send nothing; an `add_item` refused 400 after an approval also discarded an unrelated pending change in the session; a completion whose stock posting raised left `completed_at` and the line's `transferred_at` empty; `list_transfer_orders(limit=1)` of 2 orders → `total 2, 1 item, has_more True`; `skip=5` → `0 items, has_more False`; default `exclude_complete` keeps completed orders (2 vs 1); `"all"` and `""` mean no location filter, `"All"` matches nothing; `list_transfer_orders` reports `limit 100` by default, `list_transfer_orders_page` 50; an unknown filter keyword → `TypeError`; hub stats `(2, 1, 1)`, `machine_involved 1`, 2 recent with `status_name "Draft"`; `approval_summary_for` 404 for an unknown id; delete of a completed order 400. **Read, not run:** `app/api/v1/endpoints/transfer_orders.py` (every caller).

## Review
> All items answered and applied (2026-11-21): HR-10 → BUG-3142 (house rule); D1–D3 intended, decided by Claude under the reviewer's delegation (2026-11-21). Nothing pending.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| HR-10 | The "was it ready?" snapshot before an edit is read without a lock, so two concurrent edits can both send "approval pending" | bug (BUG-3142) | house rule |
| D1 | Removing or editing a line never sends a readiness notice; order edits and adding a line do | intended for now; notifications note | Claude, delegated |
| D2 | The list and hub show completed orders unless `exclude_complete=true` (the DAO's own default is the opposite) | intended | Claude, delegated |
| D3 | A location-type filter of `"all"` or empty means "no filter"; `"All"` filters on that exact text and finds nothing | intended | Claude, delegated |

### House-rule violations — applied automatically

- **HR-10** `update_transfer_order` R2, `add_item` R2 — the service reads the order and works out whether it was ready for approval (route valid + a line) **before** the manager runs, with no row lock; the manager's own lock (BUG-2892) comes later, inside its guard. Two edits that run at once can both see "not ready" and both see "ready" afterwards, so every pending approver gets `approval_pending` twice (HR-10: duplicate side effects). Intended: the order row is read `SELECT … FOR UPDATE` before the readiness snapshot (the same lock BUG-2892 takes; taking it first is enough), so the second edit waits, sees "ready", and sends nothing.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-3142 (pattern `hr-10-unlocked-state-transition`, as BUG-2892 / BUG-720). Rules: `update_transfer_order` R2a, `add_item` R2a (tagged). Settles approval notification spec FU-1 for transfer orders.

Checked and **not** violated: **HR-1/2/3** — no names; location types are exact lower-case codes (BUG-823), so D3 is not HR-3. **HR-4** — transfer orders have no soft-delete column. **HR-5/6/8** — paging, order and search are the DAO's (BUG-2654 … BUG-2657); the service does no filtering of its own after the query. **HR-7** — `GET /transfer-orders/` enforces `skip >= 0`, `1 <= limit <= 100`; the service does not re-check (not API-reachable). **HR-9** — the service writes no audit field (BUG-2893 is the manager's). **HR-11 … HR-14** — no external system, no batch. **HR-15** — transfer orders carry no money. **HR-16** — every call is scoped by the caller's `workspace_id`; foreign links are refused in the manager (BUG-2894, BUG-1018, BUG-1192); notifications go only to active members of the workspace.

**Permission checks:** none. Any active member may create, edit, delete and complete a transfer order and add or remove approvers; only approving is limited to the approver themself (manager `set_approval` R1, the endpoint passes the caller). Noted for `docs/future/permissions.md` (report).

### New questions — decided by Claude under the reviewer's delegation (2026-11-21)

### D1. Removing or editing a line never sends a readiness notice — ✅ intended (notifications note)
**Background:** After an order edit and after adding a line, the service compares "ready for approval" (a valid route and at least one line) before and after, and notifies: became ready → every pending approver gets "approval pending"; stopped being ready → the creator gets "confirm sections". `update_item` and `remove_item` do not run this.
**What happens today:** Removing the last line makes the order not ready, but nobody is told; approvers who were told "approval pending" are not told it is off (verified: no notification). The order can't be approved anyway (the manager refuses approval without a line).
**Example:** TR-2026-031 is ready and Nadia got "approval pending". Rahim removes its only line. Nadia still has the notice; clicking Approve gives "Add at least one item before approving".
**Rules affected:** `update_item` R2, `remove_item` R2
**Answer:** intended — today's behaviour is kept; no bug. The missing notice is a notifications design item, routed to `docs/future/notifications.md` with the other approval notice gaps (decided by Claude under the reviewer's delegation, 2026-11-21).

### D2. The list and hub include completed orders by default — ✅ intended
**Background:** The DAO's hub filters default to hiding completed orders (`exclude_complete=True`); the service and the endpoint default to `False` and always pass the flag (DAO spec FU-3).
**What happens today:** `GET /transfer-orders/` and `GET /transfer-orders/stats/` without the flag count and list completed orders too (verified: 2 with, 1 with `exclude_complete=true`).
**Example:** The hub of a workspace with 3 open and 7 completed transfers shows 10 orders until the user ticks "Hide completed".
**Rules affected:** `_hub_filter_kwargs` R3
**Answer:** intended — the web app sends the flag explicitly and the endpoint's default is the service's; the DAO's own default is never used through the API (decided by Claude under the reviewer's delegation, 2026-11-21).

### D3. `"all"` means no location filter; other spellings are taken literally — ✅ intended
**Background:** The hub's location-type dropdowns send `"all"` for "any". Location types are exact lower-case codes (`storage`, `damaged`, `machine`, `project`; BUG-823).
**What happens today:** `"all"`, `""` and no value mean no filter; `"All"` or `"ALL"` is passed on as a type and matches nothing (verified: 2 vs 0).
**Example:** An API client sending `source_location_type=All` gets an empty list.
**Rules affected:** `_hub_filter_kwargs` R2
**Answer:** intended — only the web app's exact `"all"` is a keyword; the codes are exact everywhere else (decided by Claude under the reviewer's delegation, 2026-11-21).

## Overview
`TransferOrderService` is the transaction boundary for transfer orders (internal stock movements between a workspace's factory storage / damaged buckets and machines). Every `/transfer-orders/` endpoint calls it. Each write calls `TransferOrderManager`, commits, re-reads and returns the row (TC1–TC6); a failure rolls back everything, including the stock posted by a failed completion. Two writes add approval notifications inside the same transaction: order edits and adding a line compare readiness before and after (`handle_order_update_notifications`), and adding an approver notifies them (`handle_add_approver`). The hub reads assemble the list page (`total`, `has_more`) and the stats DTO from the manager's hub reads. The service adds no check, no error translation and no permission check of its own: every refusal is the manager's `HTTPException`, passed on unchanged.

**Callables:** 19 specified · 2 not specified
**Externals to mock:** none in the service. Notifications are rows written by `approval_notification_service` (real; its `pg_notify` runs inside the test transaction, harmless). `utcnow` only through the manager (`app.managers.transfer_order_manager.utcnow`).
**Integration-only behavior:** the HTTP status of passed-on `HTTPException`s; `skip >= 0`, `1 <= limit <= 100` and the query-parameter defaults of the endpoint; the endpoint's 204 for delete / remove item / remove approver; the concurrency effect of BUG-3142 (needs two sessions; the lock itself is checkable by capturing SQL, as in `to_inventory.spec.md`).

**Facts for the test designer**
- Import: `from app.services.transfer_order_service import TransferOrderService, transfer_order_service`. `TransferOrderService()` takes no arguments; its manager is the attribute `manager`, the singleton `app.managers.transfer_order_manager.transfer_order_manager`. All parameters are positional-or-keyword except where `*` is shown; the endpoints pass everything after `db` by keyword.
- Response types: `TransferOrderListResponse(items, total, skip, limit, has_more)` and `TransferOrderHubStatsResponse` (`app/schemas/transfer_order.py`); `items` are `TransferOrderResponse` built from the ORM rows (`from_attributes`).
- Notifications are `app.models.notification.Notification` rows (`notification_type`, `recipient_user_id`, `actor_user_id`, `entity_type = "transfer_order"`, `entity_id`, `source_type`, `source_id`, `preview`). Recipients must be active members (approval notification spec `_notify_user`).
- Event types and texts: manager spec. Setup (statuses, factories, items, numbering patch, stock seeding or patching `post_transfer_order_inventory`): manager spec Notes.

**Notes for the test designer**
- Session and commits as `department_service.spec.md` Notes: the `db` fixture turns service commits into savepoint releases. Assert "committed" with a test-level `db.rollback()` and a re-select; "nothing saved" with a re-select. On error paths commit the setup first (`db.commit()`), or the service's rollback discards it too (verified).
- TC3 here also covers notifications and stock: on a raising call, no `notifications` row and no `inventory_ledger` row of that call remains.
- Pass-through cases: one per manager outcome the service exposes (a 404, a guard 400, a 409), not the manager's edge cases.

## Not specified
- `TransferOrderService.__init__` — stores the manager, no logic.
- `transfer_order_service` — module-level singleton.

---

## `create_transfer_order(db, to_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/`)

**Purpose:** Create a transfer order and save it.

**Returns:** the new `TransferOrder`, committed and re-read (TC2).

**Rules:**
- **R1.** The order is created as `create_transfer_order` of the manager (R1–R7 there, incl. BUG-2894, BUG-1018, BUG-825, BUG-823/824, BUG-2889) with `workspace_id` and `user_id` as given, and committed (TC1); `created_at` is loaded on the returned row (TC2).
- **R2.** Any refusal (400 same route, 409 duplicate item, schema / foreign-key errors) rolls back: no order, approver, line or event row is saved (TC3).
- **R3.** No notification is sent, even when the new order is ready at once (route + lines): the creator is its only approver and is not told (verified). (Notifications note.)
- **R4.** TC4, TC5 apply.

---

## `update_transfer_order(db, to_id, to_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /transfer-orders/{id}/`)

**Purpose:** Apply an order edit, notify on a readiness change, save.

**Returns:** the order, committed and re-read.

**Rules:**
- **R1.** The order is first read in `workspace_id`: missing or another workspace's → 404 "Transfer order with ID {to_id} not found", nothing written (manager `get_transfer_order` R2).
- **R1a.** The pre-read runs **inside** the method's `try` (source line 47): its 404 rolls the session back, so other uncommitted changes pending in the session are discarded too (TC3), as for any manager error (G2).
- **R2.** "Was ready" is taken from the order **before** the edit (route valid and at least one line; manager `_ready_for_approval` R1).
- **R2a.** [BUG-3142] (HR-10) The order row is read with a row lock before the R2 snapshot, so a concurrent edit waits and then sees the new state (it finds "already ready" and sends no second `approval_pending`). **Exact clause (G1):** the pre-read's SELECT on `transfer_orders` ends in `FOR UPDATE OF transfer_orders` (SQLAlchemy `with_for_update(of=TransferOrder)`), never a bare `FOR UPDATE`: the get eager-loads `current_status` with a `LEFT OUTER JOIN statuses`, and Postgres refuses a bare `FOR UPDATE` there ("FOR UPDATE cannot be applied to the nullable side of an outer join", verified `v2_lock.py`); the `OF` form runs and locks only the order row, never the status row (BUG-029 form). The statement must come before the first SELECT on `transfer_order_items` of the call. *(Today: no lock before the snapshot; the manager's BUG-2892 lock, once fixed, comes after it.)*
- **R3.** The edit is applied as the manager's `update_transfer_order` (R1–R7 there, incl. OQ-55 / BUG-2903 approval wipe, BUG-2895, BUG-2899, BUG-2893) and committed.
- **R4.** Notifications follow `handle_order_update_notifications` R2–R5 with `entity_type = "transfer_order"`, `entity_id = to_id`, actor `user_id`, the edited order and R2's snapshot:
  - **R4a.** not ready → ready, approvals required → every pending (unapproved) approver who is an active member gets `approval_pending`, the actor included (verified). Through this method every approver is pending whenever R4a fires (G5): an edit that can change readiness touches the route, and the manager refuses route edits once any approval is given (`_guard_confirmed_updates` R4). The "already approved approver is skipped" branch is covered by `add_approver` R2b and by the helper's own spec, not here.
  - **R4b.** ready → not ready, approvals required → the creator gets `section_confirm` with the gap text (verified: "Add at least one item before approvals can proceed" for a source = destination edit). **Reachability (G4, decided by Claude under the reviewer's delegation, 2026-11-21):** today three edits reach it: source = destination, a route id of `0`, an empty location type. Once BUG-2899 (same route → 400), BUG-2894 (id `0` / missing / foreign end → 404) and BUG-823 (unknown or empty type → 422) are fixed, no update can make a ready order not ready (lines are not edited here; `null` route fields → 422 under BUG-2895), and R4b is unreachable through this method. R4b stays as a **pass-through pointer** to `handle_order_update_notifications` R2 (tested in `approval_notification_service.spec.md`), not as a new defensive check in the service: the service holds no readiness logic of its own to defend, so nothing is added to the code. The service card for R4b uses the source = destination edit and retires when BUG-2899 is fixed; no replacement card is written on the id-`0` / empty-type paths (they close with BUG-2894 / BUG-823, and the helper spec keeps R2 covered).
  - **R4c.** Readiness unchanged, or no approvals required (`required` ≤ 0) → nothing.
- **R5.** A change of `required_approvals`, including the approval wipe of BUG-2903, sends nothing (readiness does not change). ✅ (OQ-55: the missing "approve again" notice is a notifications note, not a bug.)
- **R6.** Any error — the manager's, or one raised while notifying — rolls back the edit, its events, any approval wipe and any notification (TC3). To raise while notifying, patch the name the service imported: `app.services.transfer_order_service.handle_order_update_notifications` (G3).
- **R7.** TC4, TC5 apply.

---

## `get_transfer_order(db, to_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/{id}/`)

**Rules:**
- **R1.** Returns the manager's `get_transfer_order` (R1, R2 there): the workspace's order with its status loaded; 404 otherwise. TC6.

---

## `list_transfer_orders(db, workspace_id, skip=0, limit=100, **hub_filters)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/`)

**Rules:**
- **R1.** Returns exactly `list_transfer_orders_page` with the same `skip`, `limit` and filters.
- **R2.** Default `limit` is **100** here (the page method's is 50); the endpoint always passes `limit` (default 50), so 100 is reached only by a direct call (verified: `limit 100` in the response).
- **R3.** A filter keyword the page method does not take raises `TypeError` (verified).

---

## `_hub_filter_kwargs(self, *, date_from=None, date_to=None, status_ids=None, factory_id=None, source_location_type=None, destination_location_type=None, search=None, exclude_complete=False)`
**Shape:** mapper · **Persistence:** pure · **Visibility:** internal (used by: `list_transfer_orders_page`, `get_transfer_order_hub_stats`)

**Rules:**
- **R1.** Returns a dict with exactly the eight keys, each value as given, except R2.
- **R2.** `source_location_type` and `destination_location_type`: `None`, `""` or exactly `"all"` → `None` (no filter); any other text is kept as is, case included (`"All"` stays `"All"`, D3 ✅).
- **R3.** `exclude_complete` defaults to `False` (D2 ✅).

---

## `list_transfer_orders_page(db, workspace_id, *, skip=0, limit=50, <eight filters>)`
**Shape:** list · **Persistence:** reads · **Visibility:** internal (used by: `list_transfer_orders`)

**Rules:**
- **R1.** Filters are mapped by `_hub_filter_kwargs`; the same filters go to the count and the list (DAO `count_for_hub`, `list_for_hub`, incl. BUG-2654 … BUG-2660).
- **R2.** Returns `TransferOrderListResponse`: `items` = the page of orders, `total` = the count of all orders matching the filters, `skip` and `limit` as given.
- **R3.** `has_more` = `skip + len(items) < total` (verified: 2 orders, `limit 1` → true; `skip 1` → false; `skip 5` → 0 items, false).
- **R4.** TC6: no commit, no rollback.

---

## `get_transfer_order_hub_stats(db, workspace_id, *, <eight filters>)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/stats/`)

**Rules:**
- **R1.** Filters are mapped by `_hub_filter_kwargs` and the same filters reach every hub read.
- **R2.** `total_count`, `open_count`, `completed_count` = the DAO's `aggregate_hub_stats`; `machine_involved_count` = `count_machine_involved_for_hub`.
- **R3.** `recent_orders` = at most **10** orders of `list_recent_for_hub` (order: DAO R2, BUG-2655 / BUG-2656), each mapped by `transfer_order_to_recent_summary` (helpers spec R1–R3).
- **R4.** `pending_planned_count`, `awaiting_setup_count` and the lists `pending_planned`, `awaiting_setup`, `oldest_drafts` = the DAO's `get_pending_highlights_for_hub`, each list item mapped by `pending_highlight_from_dict` (BUG-2659: Planned needs a route **and** a line, OQ-39; BUG-2660: status ticks by stage, OQ-40).
- **R5.** Returns `TransferOrderHubStatsResponse`. TC6.

---

## `delete_transfer_order(db, to_id, workspace_id)`
**Shape:** delete (hard) · **Persistence:** writes · **Visibility:** public (`DELETE /transfer-orders/{id}/`)

**Rules:**
- **R1.** Deletes as the manager's `delete_transfer_order` (R1–R6 there) and commits; returns `None`.
- **R2.** A refusal (404, 400 "Cannot delete a completed transfer order") rolls back; the order and its rows stay (TC3).
- **R3.** [BUG-1194] The service takes the deleter (`user_id`, required) and passes it on, so the manager can write the `transfer_order_deleted` audit row; the endpoint passes the current user. *(Today: no `user_id` parameter here or in the endpoint; nothing is logged.)*
- **R4.** No notification. TC4 applies.

---

## `mark_order_complete(db, to_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/{id}/complete/`)

**Rules:**
- **R1.** Completes as the manager's `mark_order_complete` (R1–R9 there: lines stamped, stock posted, completion stamps, events; BUG-821, BUG-2899) and commits; returns the order re-read.
- **R2.** An already completed order is returned unchanged and the call still commits (nothing pending from it).
- **R3.** Any error — unmet approvals, no line, or a stock-posting error (shortage, missing location) — rolls back everything of the call: no ledger row, no line `transferred_at`, no `completed_at`, no event is saved (verified with a raising posting).
- **R4.** No notification is sent on completion (verified). (Notifications note.)
- **R5.** TC4, TC5 apply.

---

## `add_item(db, to_id, item_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/{id}/items/`)

**Returns:** the new `TransferOrderItem`, committed and re-read.

**Rules:**
- **R1.** The order is first read in `workspace_id`; missing or another workspace's → 404 as `update_transfer_order` R1. The pre-read is inside the `try` (source line 241): its 404 rolls back other pending changes too, as `update_transfer_order` R1a (G2).
- **R2.** "Was ready" is snapshot before the line is added, as `update_transfer_order` R2.
- **R2a.** [BUG-3142] (HR-10) The order row is locked before that snapshot with the same clause as `update_transfer_order` R2a: `FOR UPDATE OF transfer_orders` on the pre-read, before the first SELECT on `transfer_order_items` (G1). *(Today: no lock.)*
- **R3.** The line is added as the manager's `add_item` (R1–R6 there) and committed.
- **R4.** Notifications as `update_transfer_order` R4, judged on the order after the line is added: a routed order getting its first line → `approval_pending` to every pending approver (verified: creator, "0 of 1 approval(s) collected"); a second line (ready → ready) or an order without a valid route → nothing.
- **R5.** A refusal (completed 400; "Withdraw all approvals before editing transfer items" 400; 409 item already on the order) rolls back: no line, no event, no notification, and other pending changes in the session are discarded too (verified, TC3). To raise while notifying, patch `app.services.transfer_order_service.handle_order_update_notifications` (G3).
- **R6.** TC4, TC5 apply.

---

## `update_item(db, item_id, item_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (`PUT /transfer-orders/items/{item_id}/`)

**Rules:**
- **R1.** Updates as the manager's `update_item` (R1–R10 there, incl. BUG-2895, BUG-2896, BUG-2900) and commits; returns the line re-read.
- **R2.** No notification, whatever changes (D1 ✅).
- **R3.** A refusal rolls back (TC3); TC4, TC5 apply.

---

## `remove_item(db, item_id, workspace_id, user_id)`
**Shape:** delete (hard) · **Persistence:** writes · **Visibility:** public (`DELETE /transfer-orders/items/{item_id}/`)

**Rules:**
- **R1.** Removes as the manager's `remove_item` (R1–R3 there) and commits.
- **R2.** No notification, also when the last line goes and the order stops being ready (verified; D1 ✅).
- **R3.** Returns the deleted `TransferOrderItem` object **without** a re-read (it no longer exists); its attributes read before the commit are still on it (the endpoint answers 204 and does not use it). Verified: the returned object's `id` is the removed line's.
- **R4.** A refusal rolls back: the line stays (TC3). TC4 applies.

---

## `get_items(db, to_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/{id}/items/`)

**Rules:**
- **R1.** Returns the manager's `get_items` (R1, R2 there). TC6.

---

## `list_events(db, to_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/{id}/events/`)

**Rules:**
- **R1.** Returns the manager's `list_events` (R1–R4 there): `(event, profile or None)` pairs, newest first. TC6.

---

## `list_approvers(db, to_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/{id}/approvers/`)

**Rules:**
- **R1.** Returns the manager's `list_approvers` (R1–R4 there). TC6.

---

## `approval_summary_for(db, to_id, workspace_id)`
**Shape:** compute · **Persistence:** reads · **Visibility:** public (`GET /transfer-orders/{id}/approvers/`, with `list_approvers`)

**Rules:**
- **R1.** Order not in the workspace → 404 "Transfer order with ID {to_id} not found" (verified). There is no `try` here: the 404 neither commits nor rolls back, so other changes pending in the session stay pending (TC6; G2).
- **R2.** Otherwise returns the manager's `approval_summary` of that order: `(approved_count, required, met)` (R1–R4 there, incl. BUG-1203, BUG-2901). TC6.

---

## `add_approver(db, to_id, user_id, workspace_id, assigned_by)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (`POST /transfer-orders/{id}/approvers/`)

**Returns:** the new approver row, committed and re-read.

**Rules:**
- **R1.** Adds as the manager's `add_approver` (R1–R6 there, incl. BUG-2897: refused on a completed order; BUG-2892) and commits.
- **R2.** Notifications as `handle_add_approver` R1–R3, with actor `assigned_by`, approver `user_id`, the new row's id, and the order as it is after the add:
  - **R2a.** The new approver gets `approval_assigned`; on a ready order the preview reads "Assigned by <actor> · ready for your approval · <n> of <m> approval(s) collected", counting the new approver (verified "0 of 2").
  - **R2b.** Ready order → every other pending approver except the actor and the new approver gets `approval_pending` (verified: with the creator as actor, nobody else).
  - **R2c.** Not ready → the creator gets `section_confirm` with the gap text.
- **R3.** A refusal (404, 400 not an active member, 409 already an approver, 400 completed) rolls back: no row, no event, no notification (TC3). To raise while notifying, patch `app.services.transfer_order_service.handle_add_approver` (G3).
- **R4.** TC4, TC5 apply.

---

## `remove_approver(db, to_id, user_id, workspace_id, performed_by=None)`
**Shape:** delete (hard) · **Persistence:** writes · **Visibility:** public (`DELETE /transfer-orders/{id}/approvers/{user_id}/`)

**Rules:**
- **R1.** Removes as the manager's `remove_approver` (R1–R5 there) with `performed_by` as given (the endpoint passes the caller; default `None` = event with no performer) and commits; returns `None`.
- **R2.** No notification, also when the removal makes approvals met. (Notifications note.)
- **R3.** A refusal (404 "Approver not found", verified; BUG-2897 completed) rolls back (TC3). TC4 applies.

---

## `set_approval(db, to_id, user_id, workspace_id, approved)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (`POST` / `DELETE /transfer-orders/{id}/approvers/me/approve/`; the endpoint passes the caller as `user_id`)

**Rules:**
- **R1.** Sets the approval as the manager's `set_approval` (R1–R7 there: 403 not an approver, readiness 400s, BUG-2897, BUG-2898, BUG-2892) and commits; returns the approver row re-read.
- **R2.** No notification on approve or withdraw, also when approvals become met or stop being met (verified). (Notifications note.)
- **R3.** A refusal rolls back (TC3). TC4, TC5 apply.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 33–37 | create succeeds → commit, refresh | `create_transfer_order` R1, R3, R4 |
| 38–40 | create raises → rollback, re-raise | `create_transfer_order` R2 |
| 47 | pre-read 404 | `update_transfer_order` R1 |
| 48 | readiness snapshot (no lock) | `update_transfer_order` R2, R2a |
| 50–52 | manager update | `update_transfer_order` R3, R5 |
| 53–61 | notifications (helper's R1 skipped: no `section_was_unconfirmed`) | `update_transfer_order` R4a–R4c, R5 |
| 62–64 | commit, refresh | `update_transfer_order` R3, R7 |
| 65–67 | any raise → rollback | `update_transfer_order` R6 |
| 69–70 | get | `get_transfer_order` R1 |
| 72–79 | delegate to page; unknown keyword | `list_transfer_orders` R1–R3 |
| 98–103 | location type truthy and ≠ `"all"` / else None (×2) | `_hub_filter_kwargs` R2 |
| 91, 105 | `exclude_complete` default False | `_hub_filter_kwargs` R3 |
| 136–139 | count and list with same filters | `list_transfer_orders_page` R1, R2 |
| 145 | `skip + len < total` | `list_transfer_orders_page` R3 |
| 174–184 | aggregate, recent (limit 10), machine count | `get_transfer_order_hub_stats` R2, R3 |
| 190–211 | pending highlights; mapping loops (empty / many) | `get_transfer_order_hub_stats` R3, R4, R5 |
| 214–219 | delete commit / rollback | `delete_transfer_order` R1, R2 |
| 213 | no `user_id` parameter | `delete_transfer_order` R3 |
| 224–233 | complete commit / rollback | `mark_order_complete` R1–R3, R5 |
| 241–242 | add_item pre-read 404; snapshot | `add_item` R1, R2, R2a |
| 244–256 | manager add; re-read; notifications | `add_item` R3, R4 |
| 257–262 | commit, refresh / rollback | `add_item` R5, R6 |
| 268–275 | update_item commit / rollback | `update_item` R1–R3 |
| 278–284 | remove_item commit (no refresh) / rollback | `remove_item` R1–R4 |
| 286–287 | get_items | `get_items` R1 |
| 290–291 | list_events | `list_events` R1 |
| 294–295 | list_approvers | `list_approvers` R1 |
| 297–299 | pre-read 404; summary | `approval_summary_for` R1, R2 |
| 302–316 | manager add; re-read; `handle_add_approver` (ready / not) | `add_approver` R1, R2a–R2c |
| 317–322 | commit, refresh / rollback | `add_approver` R3, R4 |
| 327–334 | remove_approver commit / rollback | `remove_approver` R1–R3 |
| 337–346 | set_approval commit, refresh / rollback | `set_approval` R1–R3 |

## Gap log
- G1 (`transfer_order_service.cases.md` gap 1) — Fact (verified, `v2_lock.py` on `marker_test`, rolled back) — `update_transfer_order` R2a, `add_item` R2a: the lock clause is `FOR UPDATE OF transfer_orders` (`with_for_update(of=TransferOrder)`) on the pre-read, before the first `transfer_order_items` SELECT. A bare `FOR UPDATE` on this get (which LEFT OUTER JOINs `statuses` for `current_status`) is refused by Postgres, so the `OF` form is required, not just preferred (BUG-029 form).
- G2 (gap 2) — Fact — `update_transfer_order` R1a, `add_item` R1: the pre-read 404 is inside the `try` and rolls back other pending changes; `approval_summary_for` R1: no `try`, the 404 leaves pending changes pending (TC6).
- G3 (gap 3) — Test mechanics — `update_transfer_order` R6, `add_item` R5, `add_approver` R3: patch targets `app.services.transfer_order_service.handle_order_update_notifications` and `app.services.transfer_order_service.handle_add_approver` (the names the service imported).
- G4 (gap 4) — Intent, decided by Claude under the reviewer's delegation (2026-11-21) — `update_transfer_order` R4b: kept as a pass-through pointer to the helper's R2, not restated as a new defensive check; today reachable by same-route, id `0` and empty-type edits; unreachable through this method once BUG-2899, BUG-2894 and BUG-823 are fixed. The R4b card (U-11, same-route path) retires when BUG-2899 is fixed; no replacement card.
- G5 (gap 5) — Fact — `update_transfer_order` R4a: through this method every approver is pending whenever R4a fires (route edits are refused once any approval is given); the approved-approver branch is covered via `add_approver` R2b and the helper spec.
- G6 (coordinator, 2026-11-22) — fact (cosmetic) — `_hub_filter_kwargs` header now shows `self`: it is an instance method (`def _hub_filter_kwargs(self, *, …)`, source line 81); no rule changed.
