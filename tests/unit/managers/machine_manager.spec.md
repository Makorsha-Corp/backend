# Spec — `app/managers/machine_manager.py`

> **Status:** APPROVED (2026-10-30). Nothing is open: the owner answered O1–O5 and the four sub-points of O4. Stays APPROVED after fill-gaps (Gap log at the end).
> **Source commit:** e48a092

> **Review round 2026-10-30.** **The owner's own answers:** O1 — the suggested list as written, the BUG-968 blockers and the "does not block" list stand; O2 — `intended`, overdue counts only `IN_PROGRESS`, no bug; O3 — `bug`, as suggested (BUG-974); O4 — **move and update orders, not the suggested refusal** (BUG-975): a machine with open work orders may move factories, and its open work orders' factory changes to the new factory in the same transaction; O5 — `intended`, a work order on a deleted machine stays refused as today, no bug. **Delegated:** every suggested answer accepted — P1–P9, Q1–Q4 and the house-rule lines (decided by Claude under the reviewer's delegation (2026-10-30)). None of those is the reviewer's own answer. For the BUG-953 conflict with machine DAO `restore` R9, FU-3 stands and the DAO spec is not edited. The "(pilot default — awaiting reviewer)" markers were removed.
>
> **Review round 2026-10-30 (second owner answer, O4 sub-points).** **The owner's own answers:** SP-1 — leave them, unconsumed lines keep their source; SP-2 — keep recorded approvals unless the lines changed, and a move never changes lines; SP-3 — one `updated` event per moved order; SP-4 — confirmed, `IN_PROGRESS` orders move. Rules changed: `update_machine` R28b, R28d, R28e, R28f (new). The open markers on R28d and R28e were removed.
>
> **Fill-gaps round 2026-10-30 (`machine_manager.cases.md` gaps 1–10).** Gaps 1, 2, 9, 10 are facts read from the models and verified by running. **Gap 3 was first answered by carrying over the item answer "blocking is by id only, whatever the row's `workspace_id`"; that carry-over is withdrawn (see the correction round above).** Gaps 4–8 are decided by Claude under the reviewer's delegation (2026-10-30). No new bug. Rules changed: `create_machine` R3, `update_machine` R8, R23, R24, `search_machines` R8, R21, `delete_machine` R4, R4a, R4b, `create_machine_event` R13; Notes; FU-1.
>
> **Correction round 2026-10-30 (cross-workspace rows; owner's answers).** The owner's words, verbatim: *"we don't want to allow cross workspace"*, *"it should block from happening"*, and on the recommendation put to them, *"yeah i agree with your recommendations"*. **Withdrawn:** the G3 carry-over "blocking is by machine id only, whatever `workspace_id`", which the owner never meant as a normal state. **Intended now:** a row linking across workspaces is invalid data and creating one must be refused; if such a row exists anyway, `delete_machine` still refuses, exposing nothing of the other workspace: one generic entry `{"type": "other_workspace"}`, no id, once, last. That entry is the **owner's approved answer**. Rules changed: `delete_machine` R4, R4a; `create_machine_event` R2a (new), R3a, R9, Inputs, Errors; Notes; FU-1, FU-7. New bug: BUG-1000. The machine's own factory and section links were checked and are refused today (`create_machine` R1, R11; `update_machine` R11, R17). Only the work-order link is not.
>
> **Fill-gaps round 2026-10-30 (gap 12, owner's answer).** The owner's choice, verbatim: *"1 and 2 block, 3 not"*. For `delete_machine` R4: (1) a blocker still counts when the order's factory, or the other end of a transfer, is soft-deleted; (2) a line sourcing parts from this machine still blocks when its order belongs to a soft-deleted machine; (3) a sourcing line that is already consumed or has `uses_inventory = False` does not block. Rules changed: `delete_machine` R4 intro, R4 (c), R4 (d), R4a, R4b; Notes; FU-5 (one sentence). No new bug: everything that differs from today is BUG-968.
>
> **Standing reviewer decisions applied here (not asked again):**
> 1. Soft-deleted rows are kept but must not show up in lists or be counted (inventory DAO Q2, 2026-10-10).
> 2. Things of a soft-deleted parent are **hidden by the parent's state, their own rows untouched** ("hidden, not cascaded", 2026-10-11). A machine of a soft-deleted factory is hidden (BUG-890, BUG-891); restoring the factory brings it back unchanged.
> 3. **Refuse while in use**: a delete with live dependents is refused (owner, 2026-10-18, item manager Q2, BUG-948). **A refusal lists every blocker** (owner, 2026-10-18, item manager R9b): `ValueError` with `args[0]` = the message, `args[1]` = a list of `{"type", "id"}`. Showing it is a frontend note (BUG-949 precedent).
> 4. Physical row order and collation order are **not** an order: no order recipe here is called deterministic, and a missing `ORDER BY` is a bug.
> 5. "Whitespace" means what Python's `str.strip()` removes (machine DAO P3).
> 6. Machine names are unique per factory among live machines (machine DAO Q9; HR-2). `DAOMachine.restore` is kept; "restore machine" is a feature to build (machine DAO Q5, FU-3).
> 7. The machine checks before `set_assignment` and expiring `section_assignment` after it are this manager's job (assignment manager Q1, P2).
>
> **Verified by running** (throwaway scripts `h.py`, `p0.py` … `p5.py` against the test database, each in one transaction rolled back; nothing committed or dropped): every "Today:" note below; the `machines` indexes (primary key, `ix_machines_id`, `ix_machines_workspace_id`, `ix_machines_factory_id` — **no unique index**), constraint names, database defaults (only `id`, `created_at`), no trigger; every status code and detail message; create with padded / `""` / whitespace-only name, case and padding duplicates, a reused deleted name, the same name in another factory, missing / `0` / other-workspace / soft-deleted / inactive factory, an unknown user and workspace, a 201-character model number and manufacturer (200 is accepted), section valid / missing / `0` / deleted / of another factory, the machine row left flushed after a section refusal, savepoint roll-back; `get_machine` own / other workspace / missing / deleted / in a deleted factory; update of every field, `{}` and same values by the stamped user and by another user, `null` and `""` fields, rename conflict, case-only rename, every move case (missing, other workspace, `0`, deleted, inactive, same id, into a taken name, with a rename), section set / same / change / clear / clear again / bad, move with and without a section, a re-sent left-over link to a deleted section, field changes left flushed after a section refusal, the order of `changes`, edit and move-out in a deleted factory, unknown user, move with an open work order; `search_machines`: every window against 22 machines with work orders at the boundaries (today, ±1, +7, +8, +30, +31, +365, +366, +400, −3650, −3651, −4000; every status; no date; deleted work order; another workspace's work order), unknown windows, both sort directions, ties, case ties, Python paging including negative values, `latest_event_type` (crash), the `include_deleted` branch with every filter and every ignored parameter, page before filter, an empty workspace; the name-check cap (101 machines → 100 found, 1 missed; 150 → 100 found, 50 missed; which ones varies); the 10 000 cap (10 001 machines); delete with stock, open work order, maintenance log, purchase and transfer order on the machine, unknown user, in a deleted factory, savepoint roll-back, mocked `utcnow`; every `create_machine_event` branch: first status, same status, null metadata, no `status` key, other event types, another workspace's event, `created_at` tie, older row inserted last, `work_order_id` `77` and `0`, `""` and whitespace note, `is_running` already matching, unknown user, savepoint roll-back, no `FOR UPDATE` in the emitted SQL; `_set_machine_status` of the work order manager on a deleted machine (400) and on a machine of a deleted factory (succeeds); a move with one order per state, a line with a storage source and an order of another machine (no order changes, no order event; script `p6.py`). Fill-gaps (scripts `p7.py`, `p8.py`, same conditions): a recorded approval and an assignee kept through a move; a maintenance log, template, production line and formula stage naming a machine, delete succeeding; blocker rows of another workspace, delete succeeding today; a section-only change by the stamped user and by another; work dates of a deleted machine and of a machine of a deleted factory; the type of `MachineEventResponse.event_type`. Gap 12 (script `p9.py`, same conditions): the columns of `work_order_items` (`uses_inventory` NOT NULL default `False`, `consumed_at` nullable); that `purchase_orders` and `transfer_orders` have no factory column; rows for each of the owner's three points, the R4 (c) and (d) conditions run as SQL over them (a work order on the machine in a deleted factory, a sourcing line on an order of a deleted machine, and a transfer whose other end is a deleted factory or a deleted machine all match; a consumed line, a line with `uses_inventory = False` and a line left at the default do not), and today's delete succeeding with all of them. Correction round (script `p10.py`, same conditions): a factory and a section of another workspace on create and update (404, nothing written), a work order of another workspace and an unknown work order id on `create_machine_event` (both stored). **Not run:** anything at the service / HTTP level; two concurrent transactions; the *intended* behavior of the bug rules.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### Quick list — answered
| # | What the code does today, in plain words | Answer |
|---|---|---|
| **Owner (2026-10-30)** | | |
| O1 | Stock on the machine and open work / purchase / transfer orders did not stop a delete | **owner:** the suggested list stands — refuse, list the blockers — BUG-968 |
| O2 | "Overdue" counts only started work orders | **owner:** intended |
| O3 | The status of a machine in a deleted factory can still be changed | **owner:** bug — manual change refused; work-order-driven stays allowed — BUG-974 |
| O4 | A machine with open work orders can be moved; the orders stayed in the old factory | **owner:** move, and the open orders follow — BUG-975. Sub-points answered: lines stay, approvals stay, one `updated` event per moved order, `IN_PROGRESS` orders move |
| O5 | A work order on a deleted machine cannot be started, and one in progress cannot be completed or voided | **owner:** intended, stays refused |
| **Delegated — decided by Claude under the reviewer's delegation (2026-10-30)** | | |
| P1 | Editing a machine with factory id `0` crashes (500) | bug — 404 — BUG-961 |
| P2 | Clearing a machine's model number, manufacturer or note does nothing | bug — `null` clears them; `null` name / factory refused — BUG-962 |
| P3 | A machine can be created in, or moved to, a deleted factory | bug — refused 400, as sections — BUG-963 |
| P4 | A machine inside a deleted factory can still be edited | bug — refused like a deleted machine — BUG-964 |
| P5 | A machine inside a deleted factory can still be deleted | bug — refused 400 — BUG-965 |
| P6 | A machine inside a deleted factory can still be opened by id | bug — 404 unless `include_deleted` — BUG-966 |
| P7 | Model number and manufacturer are stored with their spaces; only-spaces counts as "has a value" | bug — trim, blank = empty — BUG-967 |
| P8 | An unknown maintenance filter value is treated as "all" | intended here; endpoint review |
| P9 | One branch of the maintenance filter can never run | remove |
| Q1 | Moving a machine without naming a section keeps its old factory's section | bug — the section is cleared — BUG-970 |
| Q2 | Editing a machine whose section was deleted fails, because the form re-sends that section | bug — an unchanged section is not re-checked — BUG-971 |
| Q3 | A model number or manufacturer over 200 characters crashes (500) | bug — 422 — BUG-972 |
| Q4 | Work more than a year ahead counts as "no upcoming work"; in-progress work older than 10 years is not overdue | bug — no date limits — BUG-973 |

House-rule lines stand: BUG-950 … BUG-960. Frontend note for the refusal: BUG-969.

Reused, cited, no new ID: BUG-886, BUG-887, BUG-888, BUG-889, BUG-890, BUG-891, BUG-892, BUG-343 (the machine DAO's rules, reached through this manager); BUG-909, BUG-910 (assignment DAO / manager); BUG-908 (factory section manager); BUG-340 (template generation).

### House-rule violations — applied automatically

- **HR-1** `create_machine` R6, `update_machine` R7 — machine names are stored as typed (`" Press "` keeps its spaces); `""` and `"   "` are accepted on create and on update (`""` on update even skips the duplicate check). Intended: stored trimmed; blank / whitespace-only rejected by `MachineCreate` / `MachineUpdate` (422), nothing written.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-950 (pattern `blank-name-accepted`; per BUG-896 / BUG-915). Rules: `create_machine` R6, `update_machine` R7. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-2** `_check_name_exists_in_factory` R5 — the check loads at most 100 live machines of the factory, in no order; a duplicate outside them is missed (verified: 101 machines → one name not found; which one varies). Intended: every live machine of the factory is checked.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-951 (pattern `capped-uniqueness-scan`; per BUG-893 / BUG-911). Rules: `_check_name_exists_in_factory` R5. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-2** `_check_name_exists_in_factory` R4 — names are compared exactly: "Press", "press" and " Press " count as three names. Intended: compared case-insensitively after trimming.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-952 (pattern `unnormalised-uniqueness-compare`; per BUG-894 / BUG-912). Rules: `_check_name_exists_in_factory` R4. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-2** `create_machine` R9, `update_machine` R10a — `machines` has no unique index; two requests at once both pass the Python check. Intended: a partial unique index on live rows, per factory, on the normalised name; a violation surfaces as 409, never 500. **This changes an approved rule:** machine DAO `restore` R9 ("restore succeeds with a duplicate name") then fails in the database — see FU-3.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-953 (pattern `python-only-uniqueness`; per BUG-895 / BUG-913; FU-3 stands, the DAO spec is not edited). Rules: `create_machine` R9, `update_machine` R10a. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-2** `update_machine` R10 — the name check runs only when a different name is sent: a plain move, or a move re-sending the same name, into a factory with a live machine of that name is saved (verified: two live "Same"). Intended: whenever the factory or the name changes, the resulting name is checked in the resulting factory. Same root cause as BUG-914.
**Answer:** bug — per HR-2 (house rule)
**Resolution:** 🐞 BUG-954 (pattern `uniqueness-unchecked-on-move`; per BUG-914). Rules: `update_machine` R10. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-4** `get_machine` R3, R4 — a soft-deleted machine is returned by id (`GET /machines/{id}/` answers 200) although the list hides it and edit answers 400. Intended: 404 by default; a new `include_deleted=True` returns it.
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-955 (pattern `get-returns-soft-deleted`; per BUG-897 / BUG-916). Rules: `get_machine` R3, R4. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-4** (second bullet) `search_machines` R20 — the list has an `include_deleted` option that `MachineService.get_machines` and `GET /machines/` never pass. Intended: reachable from the API (the future "restore machine" screen needs it). Precedent BUG-901 / BUG-920. *Alternative for the reviewer:* machine DAO Q6 removed the same-named parameter of two internal lookups; if deleted machines should never be listed, answer `remove` instead (this line and the next one disappear, the branch goes on the dead-code list).
**Answer:** bug — per HR-4 (house rule)
**Resolution:** 🐞 BUG-956 (pattern `flag-unreachable-from-api`; per BUG-901 / BUG-920; the alternative `remove` was not taken). Rules: `search_machines` R20. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-5 / HR-6** `search_machines` R21 — the `include_deleted` path loads one page first (deleted rows included) and filters afterwards in Python; it ignores `has_model_number`, `has_manufacturer`, `latest_event_type`, `maintenance_window`, `sort_by` and `sort_dir`, and has no display order. Intended: the same filters, sort and paging as the normal list, deleted machines included. Its comment "Preserve existing behavior for include_deleted callers" has no caller to preserve.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-957 (pattern `paginate-before-filter`; per BUG-898). Rules: `search_machines` R21. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-5** `search_machines` R7 — the maintenance filter and the maintenance sort load at most 10 000 machines and work on those (verified: machine number 10 001 by name, with work due tomorrow, is not found by "next 7 days"). Intended: every matching machine is considered.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-958 (pattern `silent-result-cap`; per BUG-342). Rules: `search_machines` R7. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-9** `update_machine` R24 — `updated_by` is written on every successful update, including `{}` and unchanged values. Intended: only when a field or the section actually changes.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-959 (pattern `audit-stamp-on-noop`; per BUG-900 / BUG-919). Rules: `update_machine` R24. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).
- **HR-10** `create_machine_event` R14 — the current status is read and then a new status written without a row lock; two identical clicks at once both pass the "already in this state" check and leave two status events (duplicate side effect). Work orders also go through this method. Intended: the machine row is read `FOR UPDATE`; the loser sees the new status and gets the normal 400.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-960 (pattern `hr-10-unlocked-state-transition`; per HR-10). Rules: `create_machine_event` R14. Kept as applied — decided by Claude under the reviewer's delegation (2026-10-30).

Checked and **not** violated: **HR-3** — no categorical free text here (`model_number` / `manufacturer` are not grouped; P7 decides the trim). **HR-5, HR-6, HR-8** on the normal list — inherited from the machine DAO (BUG-887, BUG-888, BUG-892 cited); the maintenance sort breaks ties by the DAO's name order, so it inherits BUG-887 and adds nothing. **HR-7** — `GET /machines/` enforces `1 <= limit <= 1000`. **HR-10** on `delete_machine` and `update_machine` — plain soft delete and edit: no lock (same as item manager). **HR-11 … HR-14** — no external system, no batch.

### Questions for the owner — order workflow / stock
> Answered by the owner on 2026-10-30, the sub-points of O4 included.

### O1. What counts as "in use" when deleting a machine? — 🐞 BUG-968 (owner's answer)
**Background:** Deleting a machine is a soft delete; its rows elsewhere stay. For items you decided "Refuse while in use", and that a refusal names every blocker. That decision is applied here as a standing rule; the list of what blocks is new, because different rows point at a machine. Stock on a machine is `machine_items.qty`. Work orders point at a machine directly (`machine_id`), and a line of any work order can take parts from a machine (`source_location_type = 'machine'`). Purchase orders can deliver to a machine and transfer orders can start or end at one.
**What happens today:** Nothing is looked at: a machine with stock, an in-progress work order, an open purchase order and an open transfer order is deleted (verified), and those rows stay as they were.
**Example:** "Press 4" holds 5 bolts and has a work order in progress. A user deletes it: 200. The work order can then no longer be completed (O5), and receiving a purchase order into "Press 4" still books stock onto a machine nobody can see.
**Rules affected:** `delete_machine` R4, R4a, R4b
**Suggested answer:** `ok` to the list in R4: blocks = non-zero stock on the machine; a purchase order to it (not voided, not `Complete`); a live `DRAFT` / `IN_PROGRESS` work order on it, or with a live line sourcing parts from it; a not-completed transfer order from or to it. Does **not** block = maintenance history, activity log, ledgers, a recurring template naming it (generation already skips deleted machines, BUG-340), a production line or formula stage naming it, its section, its running state. Say so if a production line or an active template should block too.
**Answer:** bug — the suggested list as written: the BUG-968 blockers stand, and the "does not block" list stands. **The owner's own answer (2026-10-30).**
**Resolution:** 🐞 BUG-968 (pattern `delete-ignores-dependents`; per BUG-948), frontend note BUG-969 (`refusal-reason-not-shown`). Rules: `delete_machine` R4, R4a, R4b unchanged.

### O2. "Overdue" ignores work orders that were never started — ✅ intended (owner's answer)
**Background:** The machines page has a maintenance filter: Overdue, Next 7 days, Next 30 days, No upcoming work. "Upcoming" counts open work orders (`DRAFT`, `IN_PROGRESS`). "Overdue" counts only `IN_PROGRESS` ones with a planned date before today (deliberate in the code, commit a043869). The upcoming-work panel (`GET /machines/upcoming-work/?include_overdue=true`) counts drafts as past-due work, so the two disagree.
**What happens today:** A machine whose only work is a draft planned for yesterday is not under "Overdue" and not under "Next 7 days"; it is listed under "No upcoming work" (verified).
**Example:** A monthly service draft for "Press 4" was planned for last Monday and nobody started it. The manager filters on "Overdue": "Press 4" is not there. It is exactly the machine the filter should show.
**Rules affected:** `search_machines` R10, R13
**Suggested answer:** `bug — overdue = any open work order (DRAFT or IN_PROGRESS) with a planned date before today`. Answer `intended` if a draft past its date is only a plan, not a missed job (recurring drafts may pile up).
**Answer:** intended — overdue counts only `IN_PROGRESS`; keep today's behaviour, no bug. **The owner's own answer (2026-10-30).**
**Resolution:** rules unchanged. Rules: `search_machines` R10 ✅, R13 ✅.

### O3. A machine in a deleted factory can still change status — 🐞 BUG-974 (owner's answer)
**Background:** The status of a machine changes in two ways through the same method: a user's click (`POST /machines/{id}/events/`), or a work order being started, completed or voided (which passes `work_order_id`). For edits and deletes of things inside a deleted factory the decision was "refuse" (BUG-926, BUG-927, P4, P5). Refusing here without care would also block open work orders in that factory.
**What happens today:** Both succeed (verified), and the event and `is_running` are written for a machine nobody can see.
**Example:** "Old Plant" was deleted with a work order in progress on "Press 4". A stale tab sends "Running": 201. Separately, restoring the factory later should let that work order be completed.
**Rules affected:** `create_machine_event` R3
**Suggested answer:** `bug — a manual change (no work_order_id) on a machine of a soft-deleted factory is refused with 400 "Cannot create event for a machine of a deleted factory"; a change driven by a work order stays allowed, so open orders can finish; an inactive-but-live factory is not refused`. Answer `intended` to leave both as they are.
**Answer:** bug — a manual status change on a machine in a soft-deleted factory gets 400 `Cannot create event for a machine of a deleted factory`; work-order-driven changes stay allowed so open orders can finish. **The owner's own answer (2026-10-30).**
**Resolution:** 🐞 BUG-974 (pattern `write-to-soft-deleted-related-row`; as BUG-926, BUG-964). "Manual" = called without `work_order_id`, which is how the two paths differ today: the service never passes it, `WorkOrderManager._set_machine_status` always does. An inactive-but-live factory is not refused (the suggested wording, as P4). Rules: `create_machine_event` R3 (tagged), R3a.

### O4. A machine with open work orders can be moved to another factory — 🐞 BUG-975 (owner's answer)
**Background:** A work order stores its own `factory_id` next to `machine_id`; parts for it are sourced from that factory. Moving a machine changes only the machine. Its stock (`machine_items`) stays with it. For sections the decision on a similar case was to refuse the move while dependents exist (BUG-928).
**What happens today:** The move succeeds; an open work order keeps the old factory (verified: `IN_PROGRESS`, `factory_id` unchanged). The maintenance filter then finds the machine under its new factory, while the work order is listed under the old one.
**Example:** "Press 4" moves from Main Plant to Second Plant with a service order in progress. The order still draws parts from Main Plant's store, and Main Plant's work-order list shows a machine that is no longer there.
**Rules affected:** `update_machine` R28
**Suggested answer:** `bug — a move is refused while the machine has an open work order: 400 "Machine has open orders", with the blocker list of delete_machine R4a (work orders only); renames and section changes are unaffected`. Alternative: move the open orders along with the machine. Answer `intended` if orders stay where they were raised.
**Answer:** move and update orders — a machine with open work orders may move factories, and its open work orders' factory changes to the new factory in the same transaction. **The owner's own answer (2026-10-30); not the suggested refusal.**
**Resolution:** 🐞 BUG-975 (pattern `move-ignores-dependents`). Rules: `update_machine` R28 (rewritten, tagged), R28a–R28f. Read from the models and `app/managers/work_order_manager.py`:
- **What stores the factory:** only `work_orders.factory_id` (NOT NULL). A work order has no section column. `work_order_events`, approvers, assignees and completers carry no factory.
- **Open:** `DRAFT`, `IN_PROGRESS` on a live order (`is_deleted = False`) — the same definition as the maintenance filter (`search_machines` R8) and `delete_machine` R4 (c). `COMPLETED`, `VOIDED` and soft-deleted orders stay in the old factory.
- **Lines that must stay:** a consumed line (`consumed_at` set) has already taken stock from its `source_location_id`, and voiding (`_reverse_item_consumption`) and a `BORROW` return at completion both go back to that location. Re-pointing it would put stock back in the wrong factory.
- **Follows by itself:** on completion a `REPLACE` line puts the removed part in the damaged bucket of `wo.factory_id`, so for a moved order it lands in the **new** factory. The title holds the machine's name, not the factory's, so it does not change. The machine's stock (`machine_items`) stays with the machine; purchase and transfer orders point at the machine id and store no factory.
- **Not touched, outside the owner's words:** a work order template (no factory column; a generated order takes `machine.factory_id` at generation, so new drafts are already right), `production_lines.factory_id` (FU-10).

**Sub-points — answered by the owner (2026-10-30).** The options below are kept as the record of why.
- **SP-1. Unconsumed lines still drawing on the old factory's store.** A line not yet consumed (`uses_inventory = True`, `consumed_at` NULL, `source_location_type = 'storage'`, `source_location_id` = the old factory) stays as it is: when the order starts or the line is posted, parts come out of the **old** factory's store, while the order is now in the new one. Template and sheet lines get that source automatically from the machine's factory at creation; manual lines were chosen by a user. *Options:* (a) leave them — **the default in the rule**; (b) re-point every such line to the new factory; (c) re-point only lines whose source equals the old factory and let the start fail if the new factory has no stock. Suggested: (b), with the source shown so the user can change it; on an `IN_PROGRESS` order the same question applies to lines added but not yet posted.
  **Owner's answer:** leave them. Unconsumed lines keep their source. Rules: `update_machine` R28d.
- **SP-2. Recorded approvals on a moved `DRAFT`.** Editing a draft's details (`machine_id`, type, cost, …) resets its approvals; `factory_id` is not in that list, and the move does not go through the order edit. *Default in the rule:* approvals stay. Suggested: leave them — the work is the same, on the same machine — unless SP-1 (b) changes where the parts come from.
  **Owner's answer:** keep recorded approvals unless the lines changed. Since SP-1 means a move never changes lines, a move never resets approvals. Rules: `update_machine` R28d.
- **SP-3. A trace on each moved order.** The order's append-only event log gets nothing, and `factory_id` is not among the logged fields, so an order's factory changes with no entry on the order; the machine's log shows only the machine's move. *Default in the rule:* no event. Suggested: one `updated` event per moved order, `changes` with `factory_id`, `metadata` naming the machine.
  **Owner's answer:** one `updated` event per moved order. Written the way `update_work_order` writes its `updated` event today; the "metadata naming the machine" of the suggestion is not added. Rules: `update_machine` R28e.
- **SP-4. Moved orders already `IN_PROGRESS`.** The owner said "open", which includes them, so they move. Stock already consumed stays booked out of the old factory (above), and their costs and order lists follow the new factory from now on (`orders_overview_service` sums cost by `WorkOrder.factory_id`). *Default in the rule:* they move like drafts. Confirm that is meant.
  **Owner's answer:** confirmed: `IN_PROGRESS` orders move; consumed parts stay booked out of the old factory while lists and cost totals follow the new one. Rules: `update_machine` R28, R28f.

### O5. A work order on a deleted machine can never finish — ✅ intended (owner's answer)
**Background:** Starting, completing or voiding an in-progress work order changes its machine's status through `WorkOrderManager._set_machine_status`, whose docstring says "best-effort". It calls `create_machine_event` with no error handling, and that refuses a deleted machine. BUG-968 stops new cases of an open order on a machine being deleted, but `create_work_order_from_template` still accepts a deleted machine, and rows from before the fix exist.
**What happens today:** `_set_machine_status` on a deleted machine raises 400 `Cannot create event for a deleted machine` (verified), so the whole work order transition fails.
**Example:** "Press 4" was deleted last month with an order in progress on it. A user presses "Void": 400 "Cannot create event for a deleted machine". The order can never be closed.
**Rules affected:** `create_machine_event` R2 (unchanged either way; the fix is in the work order manager)
**Suggested answer:** `bug in app/managers/work_order_manager.py — _set_machine_status skips the status change for a soft-deleted machine and the transition goes on`. `create_machine_event` keeps refusing. To be specified with the work order manager (FU-5).
**Answer:** intended — on a deleted machine a work order stays refused as today; no bug. **The owner's own answer (2026-10-30).**
**Resolution:** rule unchanged. Rules: `create_machine_event` R2 ✅. This spec calls for no docstring change: the `_set_machine_status` wording "best-effort" belongs to the work order manager (FU-5).

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation (2026-10-30))

### P1. Editing a machine with factory id `0` crashes — 🐞 BUG-961
**Background:** The edit checks a new factory only when the value is "truthy". `0` skips the check but is still written. Same root cause as BUG-923 (sections).
**What happens today:** `IntegrityError` on `machines_factory_id_fkey`: a 500 at the API (verified).
**Example:** A client sends `PUT /machines/5/` with `factory_id: 0`: internal server error instead of "factory not found".
**Rules affected:** `update_machine` R13
**Answer:** bug — per BUG-923 precedent: `factory_id=0` is checked like any id → 404 `Factory with ID 0 not found`, nothing written
**Resolution:** 🐞 BUG-961 (pattern `falsy-zero-treated-as-missing`) — decided by Claude under the reviewer's delegation (2026-10-30): the suggested precedent answer is accepted. Rules: `update_machine` R13.

### P2. Model number, manufacturer and note cannot be cleared — 🐞 BUG-962
**Background:** The edit drops every field sent as `null`. Only `factory_section_id` is read from the fields actually sent, so `null` clears the section but nothing else. Same root cause as BUG-608 / BUG-942. The edit form also never sends `null` for these (FU-6).
**What happens today:** `null` is ignored, the old value stays, 200 (verified). `""` is the only way to blank a value, and it is stored as `""`.
**Example:** A note "awaiting belt" is out of date. A client sends `note: null`: 200, and the note is still there.
**Rules affected:** `update_machine` R5
**Answer:** bug — per BUG-942 precedent: an explicit `null` clears `model_number`, `manufacturer` and `note`; `null` for `name` or `factory_id` is rejected with 422 by `MachineUpdate`; omitted fields stay unchanged; `factory_section_id: null` keeps meaning "clear the section"
**Resolution:** 🐞 BUG-962 (pattern `exclude-none-blocks-clear`) — decided by Claude under the reviewer's delegation (2026-10-30): the suggested precedent answer is accepted. Rules: `update_machine` R5.

### P3. A machine can be created in, or moved to, a deleted factory — 🐞 BUG-963
**Background:** The factory is read with the raw lookup, which also returns soft-deleted factories (factory manager FU-5). The sibling section manager refuses both cases with 400 (`create_factory_section` R4, `update_factory_section` R8); inventory refuses the create (BUG-715).
**What happens today:** The machine is created, or moved, and is then invisible (BUG-890) while it counts in the factory (verified).
**Example:** "Old Plant" was deleted. A stale form sends `POST /machines/` for it: 201, and the new machine never appears on the machines page.
**Rules affected:** `create_machine` R2, `update_machine` R12
**Answer:** bug — per `create_factory_section` R4 / R8 and BUG-715 precedent: 400 `Cannot create machine for deleted factory` / `Cannot move machine to deleted factory`, checked before the name, nothing written; an inactive-but-live factory is not refused
**Resolution:** 🐞 BUG-963 (pattern `write-to-soft-deleted-related-row`) — decided by Claude under the reviewer's delegation (2026-10-30): the suggested precedent answer is accepted. Rules: `create_machine` R2, `update_machine` R12.

### P4. A machine inside a deleted factory can still be edited — 🐞 BUG-964
**Background:** A machine of a deleted factory is hidden, by the factory's state alone. For sections, edits there were refused (BUG-926): a change made while hidden means a restore does not bring back what was hidden.
**What happens today:** Rename, edit and move out all succeed (verified).
**Example:** A stale tab renames "Press 4" of deleted "Old Plant"; when the factory is restored, the machine has another name.
**Rules affected:** `update_machine` R3
**Answer:** bug — per BUG-926 precedent: refused like a deleted machine, 400 `Cannot update a deleted machine`, checked right after the machine's own deleted flag; an inactive-but-live factory is not refused
**Resolution:** 🐞 BUG-964 (pattern `write-to-soft-deleted-related-row`) — decided by Claude under the reviewer's delegation (2026-10-30): the suggested precedent answer is accepted. Rules: `update_machine` R3.

### P5. A machine inside a deleted factory can still be deleted — 🐞 BUG-965
**Background:** As P4; for sections BUG-927.
**What happens today:** Deleted normally (verified); restoring the factory then leaves it out.
**Example:** A stale tab deletes "Press 4" of deleted "Old Plant". After the factory is restored, "Press 4" is the one machine missing.
**Rules affected:** `delete_machine` R3
**Answer:** bug — per BUG-927 precedent: 400 `Cannot delete a machine of a deleted factory`, nothing written, checked after "already deleted"; an inactive-but-live factory is not refused
**Resolution:** 🐞 BUG-965 (pattern `write-to-soft-deleted-related-row`) — decided by Claude under the reviewer's delegation (2026-10-30): the suggested precedent answer is accepted. Rules: `delete_machine` R3.

### P6. A machine inside a deleted factory can still be opened by id — 🐞 BUG-966
**Background:** The list hides such a machine (BUG-890); the lookup by id does not. For sections: BUG-925.
**What happens today:** 200 (verified).
**Example:** A bookmarked link to "Press 4" of deleted "Old Plant" still opens the machine.
**Rules affected:** `get_machine` R5
**Answer:** bug — per BUG-925 precedent: 404 `Machine with ID <id> not found` by default; returned with `include_deleted=True`; an inactive-but-live factory hides nothing
**Resolution:** 🐞 BUG-966 (pattern `join-ignores-soft-deleted`) — decided by Claude under the reviewer's delegation (2026-10-30): the suggested precedent answer is accepted. Rules: `get_machine` R5.

### P7. Model number and manufacturer keep their spaces; blank counts as a value — 🐞 BUG-967
**Background:** Machine DAO Q3 left this to this review (its FU-2): the "has a model number" filter is right to compare what is stored; the fix is to clean the value when saving. For item SKUs the decision was: trimmed, blank = no value (BUG-946). The web form already trims these two before sending; the API does not.
**What happens today:** `"   "` is stored as typed and counts as having a value (verified).
**Example:** An API client sends `model_number: "  "`; the machine shows up under "has a model number".
**Rules affected:** `create_machine` R7, `update_machine` R6
**Answer:** bug — per BUG-946 precedent: `model_number` and `manufacturer` are stored trimmed; empty / whitespace-only is stored as `NULL`; fix in `MachineCreate` / `MachineUpdate`. `note` is free text and stays as typed
**Resolution:** 🐞 BUG-967 (pattern `blank-optional-text-stored`) — decided by Claude under the reviewer's delegation (2026-10-30): the suggested precedent answer is accepted. Rules: `create_machine` R7, `update_machine` R6.

### P8. An unknown maintenance filter value means "all" — ✅ intended here
**Background:** `maintenance_window` is free text at `GET /machines/`. For `sort_by` / `sort_dir` the reviewer decided: lenient below, to be looked at in the machines endpoint review (machine DAO Q2, FU-1).
**What happens today:** `maintenance_window=OVERDUE` or `bogus` returns every machine with no error (verified).
**Example:** A client misspells the filter and believes the list is filtered.
**Rules affected:** `search_machines` R14
**Answer:** intended here — per machine DAO Q2 precedent; added to the endpoint review's list (FU-1)
**Resolution:** rule unchanged — decided by Claude under the reviewer's delegation (2026-10-30). Rules: `search_machines` R14 ✅.

### P9. One branch of the maintenance filter can never run — remove
**Background:** Inside the filter function a first check returns `True` for `"all"`, but the function is only used when the value is not `"all"`.
**What happens today:** The branch is never taken.
**Example:** No request can reach it.
**Rules affected:** none (Branch map line 306)
**Answer:** remove — logged in `docs/testing/dead-code-removal-checklist.md` — decided by Claude under the reviewer's delegation (2026-10-30). Not a bug — no BUG ID.

### New questions

### Q1. A moved machine keeps its old factory's section — 🐞 BUG-970
**Background:** A section belongs to one factory; a machine's section is an optional label held in a separate row. `update_machine` touches that row only when `factory_section_id` is in the request. The web form always sends it; API clients may not. The assignment manager would refuse this link if asked (assignment DAO FU-3 left the decision here). BUG-928 refused the mirror case (moving a section with machines).
**What happens today:** After `PUT` with only `factory_id`, the machine is in Second Plant and its section is still "Cut" of Main Plant (verified); the change log does not mention it.
**Example:** "Press 4" moves to Second Plant through the API. The machines page filtered on Main Plant's "Cut" still lists it.
**Rules affected:** `update_machine` R20
**Suggested answer:** `bug — moving to another factory without sending factory_section_id clears the section, and the change log records it`. A section is only a label, so refusing the move would be heavier than the harm. Alternative: `bug — refuse with 400`.
**Answer:** bug — the move clears the section and the change log records it — decided by Claude under the reviewer's delegation (2026-10-30).
**Resolution:** 🐞 BUG-970 (pattern `move-ignores-dependents`). Rules: `update_machine` R20.

### Q2. Editing a machine whose section was deleted fails — 🐞 BUG-971
**Background:** The web form sends the current section on every save, and `update_machine` validates whatever is sent. Today, deleting a section erases its links, so this only shows with left-over rows; once BUG-908 is fixed the links stay and **every** machine of a deleted section is affected (factory section manager FU-4 left this here).
**What happens today:** With a left-over link, an edit re-sending that section gets 400 `Cannot assign a machine to a deleted factory section` and nothing is saved (verified).
**Example (after BUG-908):** "Paint" is deleted. A user changes the note of a machine that was in "Paint": 400, although they never touched the section. Fixing the note requires clearing the section first.
**Rules affected:** `update_machine` R19
**Suggested answer:** `bug — a factory_section_id equal to the machine's current section is not a change: not validated, nothing written (with BUG-909), unless the factory changes too`.
**Answer:** bug — a `factory_section_id` equal to the current section, with no factory change, is not validated — decided by Claude under the reviewer's delegation (2026-10-30).
**Resolution:** 🐞 BUG-971 (pattern `unchanged-value-revalidated`). Rules: `update_machine` R19.

### Q3. An over-long model number or manufacturer crashes — 🐞 BUG-972
**Background:** Both columns are limited to 200 characters; the schemas have no limit.
**What happens today:** 201 characters → `DataError` at flush: a 500 (verified).
**Example:** A pasted spec sheet in "model number" gives "internal server error" instead of a validation message.
**Rules affected:** `create_machine` R8, `update_machine` R6a
**Suggested answer:** `bug — max_length=200 on both fields of MachineCreate / MachineUpdate: 422`. (Audit logs truncate, BUG-144, because they must not fail the operation; here the user can correct the input.)
**Answer:** bug — `max_length=200` on both fields: 422 — decided by Claude under the reviewer's delegation (2026-10-30).
**Resolution:** 🐞 BUG-972 (pattern `unchecked-column-length`). Rules: `create_machine` R8, `update_machine` R6a.

### Q4. The maintenance filter only sees 10 years back and 1 year ahead — 🐞 BUG-973
**Background:** To fill the filter, work order dates are read between today − 3650 days and today + 365 days. Nothing tells the user.
**What happens today:** Work planned 366 days ahead gives "No upcoming work" and no maintenance date in the sort; an in-progress order 3651 days old is not overdue (verified).
**Example:** An annual overhaul is planned 13 months ahead. The filter "No upcoming work" lists the machine.
**Rules affected:** `search_machines` R9
**Suggested answer:** `bug — every open work order with a planned date counts, however far away`.
**Answer:** bug — every open work order with a planned date counts, however far away — decided by Claude under the reviewer's delegation (2026-10-30).
**Resolution:** 🐞 BUG-973 (pattern `silent-result-cap`). Rules: `search_machines` R9.

## Follow-ups for other reviews
> Nothing below is a rule of this manager and no bug is logged for it here except where an ID is given. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Machine service / endpoints** (`app/services/machine_service.py`, `app/api/v1/endpoints/machines.py`) | (a) Translate `delete_machine`'s `ValueError` (R4a): raise `app.core.exceptions.ValidationError(detail=exc.args[0], errors=exc.args[1])`, so the 400 body carries the list. **Without this it is a 500:** every other refusal of this manager is an `HTTPException`, and the service only re-raises. (b) Expose `include_deleted` on `GET /machines/` and `GET /machines/{id}/` (BUG-956, BUG-955). (c) `sort_by`, `sort_dir` (machine DAO FU-1) **and `maintenance_window`** (P8) are free text; decide 422. (d) `MachineEventCreate.machine_id` is required in the body although the path overrides it. | HR-4 lines, P8, standing decision 3 |
| FU-2 | **Schemas** (`app/schemas/machine.py`) | All schema-side fixes go on `MachineCreate` / `MachineUpdate`: trim + non-blank `name` (BUG-950), `null` handling (BUG-962), trim / blank → `NULL` (BUG-967), `max_length=200` (BUG-972). `MachineCreate` inherits `MachineBase`; `MachineResponse` does not. | HR-1, P2, P7, Q3 |
| FU-3 | **Machine DAO** (`tests/unit/dao/machine.spec.md`, APPROVED, verified) | (a) **BUG-953 changes an approved rule:** with the unique index, `restore` R9 (succeeds with a duplicate name) must become the factory-style R9a (`IntegrityError`), and any `test_machine.py` setup with two live same-named machines of one factory must change. (b) BUG-951 needs an uncapped lookup; BUG-957 needs an `include_deleted` on `search_advanced` (R2 there says there is none); BUG-958 needs an unpaged form. (c) The DAO's cross-spec notes on the 100-row cap and `include_deleted` are answered here. | HR-2, HR-4, HR-5 lines |
| FU-4 | **"Restore machine" feature** (to build; machine DAO FU-3) | Must refuse a name now in use with 409 (BUG-953), and decide on a machine of a deleted factory. Deleted-machine list: BUG-956. | machine DAO Q5 |
| FU-5 | **Work order manager** (`app/managers/work_order_manager.py`, not yet specified) | O5 is `intended`: the transition fails on a deleted machine; `_set_machine_status`'s docstring "best-effort" is therefore inaccurate — wording only, no bug, to be settled in that review. `create_work_order_from_template` reads the machine with the raw lookup and accepts a deleted one. BUG-974: the work-order path relies on always passing `work_order_id`. R4 (c) (owner's gap 12 answer) lets a machine be deleted while an open order has a consumed line sourced from it; voiding that order, or a `BORROW` return, then posts stock back to the deleted machine, and the BUG-663 fix (404 for a soft-deleted machine as a stock location) would make that transition fail: to be settled in that review. BUG-975: `work_order_manager` imports `machine_manager`, so `MachineManager` cannot call it: the factory update goes through `app/dao/work_order.py` and the event (`update_machine` R28e) through `app/dao/work_order_event.py` or a direct `WorkOrderEvent` row, not through `WorkOrderManager.log_event`; a new order created while the move runs takes `machine.factory_id` as read. | O3, O4, O5 |
| FU-6 | **Frontend** (`frontend/src/components/newcomponents/customui/EditMachineDialog.tsx`) | Sends `model_number` / `manufacturer` / `note` as `… .trim() \|\| undefined`, so an emptied box is omitted and can never clear the value, even after BUG-962: it must send `null`. BUG-969: `MachinesPage.tsx` must show the blockers of a refused delete. | P2, O1 |
| FU-7 | **Purchase / transfer order managers, machine item and maintenance log managers** | Whether each refuses a deleted machine **after** it is deleted: BUG-663, BUG-684, BUG-822 cover stock posting; a new order on a deleted machine is for those reviews. **Cross-workspace rows must be refused where they are created** (owner, 2026-10-30): a work order's `machine_id`, a work order line's `source_location_id`, a purchase order's `destination_id`, a transfer's location ids and a `machine_items` row. `create_work_order` does not check its `machine_id`; each is for that manager's review. | O1 |
| FU-8 | **Machine activity manager / DAO** (`machine_activity_manager.py`, `machine_activity_event.py`, not yet specified) | `get_latest_status` has the comment "404 if missing" but raises nothing. `get_latest_status_map` picks latest by timestamp only (machine DAO cross-spec note). | `create_machine_event` |
| FU-10 | **Production line manager** | `production_lines` has its own `factory_id` next to `machine_id`; a moved machine leaves it on the old factory. Not a work order, not covered by the owner's O4 answer, not changed here. | O4 |
| FU-9 | **Product-wide** | `search_machines` uses the server's `date.today()`. Elsewhere timestamps are naive UTC, so around midnight the "today" of the filter may differ from the user's day. No rule here; to be settled once for all date filters. | R15 |

Answered here: machine DAO FU-2 (P7), assignment DAO FU-3 (Q1), factory section manager FU-4 (Q2), factory manager FU-5 (P3, P4, BUG-974), assignment manager FU-2 (a)–(e): (a), (b) `create_machine` R10, `update_machine` R17, (c) BUG-909 cited, (d) Q1, (e) P3, P4.

## Overview
`MachineManager` owns the machines of a workspace: create, edit, look up, list, soft delete, and the machine's status (a status change is a row of the activity log, and `is_running` follows it). It is called by `MachineService` behind `/machines/` and, for status changes, by `WorkOrderManager._set_machine_status`. It is meant to protect workspace isolation; one live machine per name in a factory; soft-delete semantics; `is_running` true exactly when the latest status is `RUNNING`; and an activity entry for every create, real edit, delete and status change. It never commits; DAOs and the activity manager flush. Every refusal is an `HTTPException`, except the intended in-use refusal of `delete_machine` (R4a).

**Callables:** 7 specified · 3 not specified
**Externals to mock:** `utcnow` (patch `app.dao.machine.utcnow`; `deleted_at` only). `date.today()` in `search_machines` is not mocked: see Notes. (`MachineActivityEvent.created_at` uses a Python default bound to `app.utils.time.utcnow` at import; patching does not change it, assert set / not set.)
**Integration-only behavior:** the HTTP status of the refusals; the 400 body of R4a (FU-1); schema validation becoming 422; the bounds on `GET /machines/` (`skip >= 0`, `1 <= limit <= 1000`); the service's commit / rollback and `db.refresh`.

**Facts for the test designer**
- Import: `from app.managers.machine_manager import MachineManager, machine_manager`. `MachineManager()` takes no arguments; the singleton holds no per-call state. All parameters are positional-or-keyword. Services call by keyword, except `get_machine(db, machine_id, workspace_id)`.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail` (a plain string). The in-use refusal is a `ValueError`: assert `exc.args[0]`, `exc.args[1]`, never `str(exc)`. Database errors are `sqlalchemy.exc.IntegrityError` / `DataError` with `.orig` a `psycopg2` error class. Schema errors are `pydantic.ValidationError`.
- Tables, columns, defaults, read-only `factory_section_id` / `factory_section_name`, assignment and activity rows, schemas: machine DAO spec, **Model facts**. Added here (verified): indexes `machines_pkey`, `ix_machines_id`, `ix_machines_workspace_id`, `ix_machines_factory_id`, **no unique index**; foreign keys `machines_created_by_fkey`, `machines_updated_by_fkey`, `machines_deleted_by_fkey`, `machines_factory_id_fkey`, `machine_activity_events_performed_by_fkey`.
- `MachineEventCreate` = `machine_id: int`, `event_type: MachineEventTypeEnum`, `note: str | None = None`. `MachineEventResponse` = `id`, `workspace_id`, `machine_id`, `event_type`, `started_at`, `initiated_by`, `note`, `created_at`, `created_by`.
- `MachineUpdate` has no `is_running`; unknown fields are ignored, on `MachineCreate` too. `model_fields_set` tells a sent `factory_section_id: null` from an omitted one.
- `MACHINE_LOG_FIELDS`, in order: `name` "Name", `factory_id` "Factory", `factory_section_id` "Section", `model_number` "Model number", `manufacturer` "Manufacturer", `note` "Note". Values in `changes` are strings (`"980003"`) or `None`.
- `MachineEventTypeEnum`: `IDLE`, `RUNNING`, `OFF`, `MAINTENANCE`. `WorkOrderStatusEnum`: `DRAFT`, `IN_PROGRESS`, `COMPLETED`, `VOIDED`.
- Collaborator rules cited, not repeated: machine DAO `get_by_factory`, `search_advanced`, `soft_delete`, inherited methods (`tests/unit/dao/machine.spec.md`); assignment manager `set_assignment` R1–R13 (`tests/unit/managers/machine_section_assignment_manager.spec.md`); factory DAO `get_by_id_and_workspace` R1–R5.

**Notes for the test designer**
- Workspaces and profiles from `tests/unit/factories.py`. Build `Factory`, `FactorySection`, `Machine`, `MachineSectionAssignment`, `MachineActivityEvent` rows directly (add + flush). `autoflush=False`: flush before calling the manager.
- **Reading rows:** assert activity events, links and columns with a fresh `SELECT`. After creating a link for a loaded machine call `db.expire_all()`. `db.refresh(machine)` before a call expected to write nothing, and before asserting `updated_at`. `updated_at`: `None` → not `None`, never "later than".
- **Activity metadata** is JSON: compare whole dicts, order of `changes` included (`MACHINE_LOG_FIELDS` order).
- **Refusals with nothing written** leave the session usable. **Refusals after a flush** (`create_machine` R12, `update_machine` R21) leave the rows flushed: wrap the call in `sp = db.begin_nested()`, assert the state, `sp.rollback()`. **Database errors** abort the transaction: `with db.begin_nested():` inside `pytest.raises(...)`.
- **Names:** cases not about duplicates use names that differ in more than case. Once BUG-953 is in place, two live same-named machines of one factory cannot be built; put them in different factories, or make one soft-deleted.
- **BUG-951 (cap):** the 100 rows returned are not predictable, so never aim at a particular machine. Bulk-insert 101 live machines with distinct names and ask `_check_name_exists_in_factory` for each name: intended all `True`; today exactly one `False` (verified; which one varies). The **count** is deterministic → strict xfail. 100 soft-deleted machines plus one live one do **not** reproduce it: the DAO filters before its limit.
- **BUG-953 database-level 409:** patch `MachineManager._check_name_exists_in_factory` to return `False`; wrap in `db.begin_nested()` inside `pytest.raises(HTTPException)`. A direct duplicate insert raises `IntegrityError` on flush once the index exists.
- **BUG-958 (10 000):** bulk `insert(Machine)` of 10 001 machines named `B00000` … `B10000` (`is_active=True, is_deleted=False, is_running=False`), a `DRAFT` work order for `B10000` planned tomorrow. Today `maintenance_window="next_7_days"` returns `[]`; `sort_by="maintenance_date", limit=1` returns `B00000`. Intended `[B10000]` both. About a second. Strict xfail.
- **Work orders:** `WorkOrderType` (`workspace_id`, `name`); `WorkOrder` (`workspace_id`, `work_order_number`, `work_order_type_id`, `title`, `factory_id`; `machine_id`, `planned_date`, `status`, `is_deleted` as needed).
- **Dates:** build `planned_date` relative to `date.today()` read in the test. Do not patch `date` in the manager (`date.max` and `date` arithmetic are used there).
- **Window results** are ordered by the list sort: use names that differ in more than case and assert lists.
- **BUG-960 (lock):** setup rows are uncommitted, so a second connection cannot see them. Capture statements with a `before_cursor_execute` listener on the session's connection and assert the machine `SELECT` carries `FOR UPDATE`. Today none does (verified) → strict xfail.
- **Classes (verified to insert).** Last column: NOT NULL columns without a default.
  | Table | Class | Import | Columns |
  |---|---|---|---|
  | `machine_items` | `MachineItem` | `app.models.machine_item` | `workspace_id`, `machine_id`, `item_id`; `qty` defaults 0 |
  | `purchase_orders` | `PurchaseOrder` | `app.models.purchase_order` | as below |
  | `transfer_orders` | `TransferOrder` | `app.models.transfer_order` | as below |
  | `work_orders` | `WorkOrder` | `app.models.work_order` | `workspace_id`, `work_order_number`, `work_order_type_id`, `title`, `factory_id` |
  | `work_order_types` | `WorkOrderType` | `app.models.work_order_type` | `workspace_id`, `name` |
  | `work_order_items` | `WorkOrderItem` | `app.models.work_order_item` | `workspace_id`, `work_order_id`, `item_id`, `quantity` |
  | `statuses` | `Status` | `app.models.status` | `workspace_id`, `name`, `comment` |
  | `work_order_approvers` | `WorkOrderApprover` | `app.models.work_order_approver` | `workspace_id`, `work_order_id`, `user_id`; unique (`work_order_id`, `user_id`) |
  | `work_order_assignees` | `WorkOrderAssignee` | `app.models.work_order_assignee` | `workspace_id`, `work_order_id`, `user_id`; unique (`work_order_id`, `user_id`) |
  | `work_order_events` | `WorkOrderEvent` | `app.models.work_order_event` | as `update_machine` R28e |
  | `machine_maintenance_logs` | `MachineMaintenanceLog` | `app.models.machine_maintenance_log` | `workspace_id`, `machine_id`, `maintenance_type` (`MaintenanceTypeEnum`), `maintenance_date`, `summary` |
  | `work_order_templates` | `WorkOrderTemplate` | `app.models.work_order_template` | `workspace_id`, `template_name`, `work_order_type_id`; `default_machine_id` names the machine |
  | `production_lines` | `ProductionLine` | `app.models.production_line` | `workspace_id`, `factory_id`, `name`; `machine_id` names the machine |
  | `production_formulas` | `ProductionFormula` | `app.models.production_formula` | `workspace_id`, `formula_code`, `name` |
  | `production_formula_stages` | `ProductionFormulaStage` | `app.models.production_formula_stage` | `workspace_id`, `formula_id`, `stage_order`, `name`; `machine_id` names the machine |
- **Recorded approval (`update_machine` R28d):** a `work_order_approvers` row with `approved = True` and `approved_at` set (`approved` is what the order manager tests); `approved` defaults `False`, `assigned_at` is set by default. The order's own `required_approvals`, `approved_by`, `approved_at` stay too. **Assignees (R28):** rows of `work_order_assignees`, plus the text column `work_orders.assigned_to`; a move changes neither.
- **Rows of another workspace (`delete_machine` R4).** Invalid data: built only to prove the refusal hides them. No foreign key stops it. Build the row with the other workspace's `workspace_id`. Verified buildable, each with today's delete succeeding: a `machine_items` row, a purchase order, a transfer order and a work order by `machine_id`, all in W2, and a W2 work order with a W2 line sourcing from the machine; parents in W2 (item, stage, work order type, factory). The line needs `uses_inventory=True` set explicitly. Intended: each gives `[{"type": "other_workspace"}]` (strict xfail); several give one entry; assert no id of W2 appears anywhere in `exc.value.args`.
- **Sourcing lines (`delete_machine` R4 (c)).** `WorkOrderItem.uses_inventory` defaults `False`: a blocking line must set `uses_inventory=True`, or it does not block. Verified in the `p9.py` run: a line left at the default matches nothing.
- **BUG-968 rows:** NOT NULL columns as in item manager spec Notes ("Rows for BUG-948"). A `PurchaseOrder` needs `workspace_id`, `po_number`, `destination_type`, `destination_id`, `current_status_id`, `created_by`; a `TransferOrder` `workspace_id`, `transfer_number`, `source_location_type`, `source_location_id`, `destination_location_type`, `destination_location_id`, `current_status_id`, `created_by`. `Status` needs `workspace_id`, `name`, `comment`. Verified to insert.
- Strict xfail (outcome does not depend on row order): BUG-950, BUG-951, BUG-952, BUG-953, BUG-954, BUG-955, BUG-957 (except the page-before-filter card, below), BUG-958, BUG-959, BUG-960, BUG-961, BUG-962, BUG-963, BUG-964, BUG-965, BUG-966, BUG-967, BUG-968, BUG-970, BUG-971, BUG-972, BUG-973, BUG-974, BUG-975, BUG-1000, BUG-909. BUG-956 is integration-only. Inherited DAO bugs (BUG-886 … BUG-892) are tested in the DAO; here one pass-through case each is enough, written to the intended behavior and marked xfail with that bug's ID, never a pass card on the buggy path: strict for BUG-886, BUG-888, BUG-889, BUG-890, BUG-891, BUG-892; **non-strict** for BUG-887 (collation order is not an order, standing decision 4).
- **Non-strict: BUG-957 page-before-filter (`search_machines` R21).** Today's result depends on which rows the unordered page holds, and physical order is not an order, so that one card is non-strict; never weaken the assertion. The cards on ignored filters and the window are strict.
- **BUG-975 (`update_machine` R28):** build one order per state on the machine, plus a `DRAFT` of another machine with a line sourcing from it. Today no order changes and no `work_order_events` row is written (verified) → strict xfail for R28, R28e, R28f. R28a, R28c and R28d pass today. Read events with a fresh `SELECT` on `work_order_events`; compare `metadata` as a whole dict. For "approvals stay" read `work_order_approvers` before and after. Use `WorkOrderEvent` from `app.models.work_order_event`.
- **BUG-974 (`create_machine_event` R3):** today accepted (verified) → strict xfail. R3a passes today.
- **BUG-1000 (`create_machine_event` R2a):** a case that passes `work_order_id` must build a real `WorkOrder` of the workspace; a made-up id (`77`, `0`) is refused once the bug is fixed.
- HR-10 applies only to `create_machine_event`.

## Not specified
- `MachineManager.__init__` — stores the model and collaborators, no logic
- `machine_manager` — module-level singleton, no logic
- Inner functions `matches_window`, `sort_key` of `search_machines` — specified through it

Dead branch (P9, `remove`, decided by Claude under the reviewer's delegation (2026-10-30); on the dead-code list): `if maintenance_window == "all": return True` (line 306). The checklist marks nothing of this file as possibly unused. No legacy test calls this manager.

---

## `MachineManager.create_machine(session, machine_data, workspace_id, user_id)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `MachineService.create_machine` ← `POST /machines/`)

**Purpose:** Create a machine in a factory of the workspace, optionally in a section, and log it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `machine_data` | `MachineCreate` | `name`, `factory_id` required; `factory_section_id`, `model_number`, `manufacturer`, `note` optional |
| `workspace_id` | int | caller's workspace; the factory must belong to it |
| `user_id` | int | creator; `created_by`, the link's `created_by`, the event's `performed_by` |

**Returns:** the new `Machine`, flushed, not committed; its `factory_section_id` reads the new section.

**Rules:**
- **R1.** No factory with that id (also `0`), or a factory of another workspace → 404 `Factory with ID <factory_id> not found`; nothing created. An unknown `workspace_id` ends here too.
- **R2.** [BUG-963] (P3) A soft-deleted factory → 400 `Cannot create machine for deleted factory`, before the name check; nothing created. A live but inactive factory is not refused. *(Today: created.)*
- **R3.** A live machine of the factory with the same name → 409 `Machine with name '<name>' already exists in this factory` (`<name>` = the name the manager receives: the submitted spelling, trimmed once BUG-950 is fixed, so `" Lathe "` gives `'Lathe'`; never the existing machine's spelling, so `"press"` against a live "Press" gives `'press'`); nothing created. Detection follows `_check_name_exists_in_factory` R1–R7.
- **R4.** The same name in another factory, in another workspace, or on a soft-deleted machine does not block.
- **R5.** One machine is created with `name`, `factory_id`, `model_number`, `manufacturer`, `note` from the input, `workspace_id` = the argument, `created_by = user_id`, `is_running = False`, `is_active = True`, `is_deleted = False`, `created_at` set, and `updated_at`, `updated_by`, `deleted_at`, `deleted_by` `None`. An `is_running` in the request is ignored.
- **R6.** [BUG-950] (HR-1) The name is stored trimmed, inner whitespace and case kept (`" Press "` → `"Press"`); a blank or whitespace-only name (`""`, `"   "`, `"\t"`) is rejected by `MachineCreate` (`ValidationError`, 422 at the API). *(Today: stored as typed; `""` and `"   "` created.)*
- **R7.** [BUG-967] (P7) `model_number` and `manufacturer` are stored trimmed; empty / whitespace-only is stored as `None`. `note` is stored as typed. *(Today: stored as typed, `"   "` stays.)*
- **R8.** [BUG-972] (Q3) A `model_number` or `manufacturer` over 200 characters is rejected by `MachineCreate` (`ValidationError`); exactly 200 is accepted. *(Today: `DataError` / `StringDataRightTruncation` at the flush.)*
- **R9.** [BUG-953] (HR-2) The database refuses a second live machine with the same normalised name (lower-case of the trimmed name) in one factory; a soft-deleted row or a row of another factory is accepted. When such a duplicate reaches the insert through the manager, the same 409 as R3 is raised, not a database error; nothing created. *(Today: no index, the duplicate is saved.)*
- **R10.** Given `factory_section_id`, the machine gets a link to that section, created by `user_id` (assignment manager `set_assignment` R1), and the returned machine's `factory_section_id` / `factory_section_name` read it. Without it (`None`) no link exists and both read `None`.
- **R11.** A refused section gives that method's error: 404 `Factory section with ID <id> not found` (also `0`), 400 `Cannot assign a machine to a deleted factory section`, 400 `Factory section does not belong to this machine's factory` (`set_assignment` R5–R9, BUG-910 cited).
- **R12.** On that refusal the machine row is already flushed and no activity event exists; rolling back (the service does) removes it. The manager itself does not undo it.
- **R13.** One activity event: `event_type = "created"`, `description = "Machine created: <name>"`, `performed_by = user_id`, `workspace_id` = the argument, `metadata_json = None`.
- **R14.** Unknown `user_id` → `IntegrityError` (`ForeignKeyViolation`, `machines_created_by_fkey`); nothing saved.
- **R15.** Flushed, not committed: rolling back a savepoint around the call removes the machine, its link and its event.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| factory missing / other workspace | `HTTPException` 404 | `Factory with ID <factory_id> not found` |
| [BUG-963] factory soft-deleted | `HTTPException` 400 | `Cannot create machine for deleted factory` |
| live duplicate name; same for the database violation [BUG-953] | `HTTPException` 409 | `Machine with name '<name>' already exists in this factory` |
| section refused | `HTTPException` 404 / 400 | as R11 |
| [BUG-950] blank name; [BUG-972] over 200 characters | `pydantic.ValidationError` building `MachineCreate` | not asserted |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `machines` row; optionally one `machine_section_assignments` row; one `machine_activity_events` row; all flushed. No commit.

---

## `MachineManager.update_machine(session, machine_id, machine_data, workspace_id, user_id)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `MachineService.update_machine` ← `PUT /machines/{id}/`)

**Purpose:** Change a machine's details, factory or section, and log what changed. Never changes `is_running`.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `machine_id` | int | machine to change |
| `machine_data` | `MachineUpdate` | all optional; a sent `factory_section_id: null` clears the section |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | editor; `updated_by`, the link's `created_by`, the event's `performed_by` |

**Returns:** the same `Machine` instance, flushed, not committed; its `factory_section_id` reads the current section.

**Rules:**
- **R1.** No machine with that id, or a machine of another workspace → 404 `Machine with ID <machine_id> not found`; nothing changes.
- **R2.** A soft-deleted machine → 400 `Cannot update a deleted machine`, whatever the input (before any factory or name check).
- **R3.** [BUG-964] (P4) A live machine whose factory is soft-deleted → the same 400, right after R2: rename, edit and move out are all refused. A live but inactive factory is not refused. *(Today: all succeed.)*
- **R4.** Each sent field with a new value is stored; an omitted field keeps its value.
- **R5.** [BUG-962] (P2) An explicit `null` clears `model_number`, `manufacturer`, `note`. `null` for `name` or `factory_id` is rejected by `MachineUpdate` (`ValidationError`, 422). *(Today: `null` is ignored for all five, the old value stays.)*
- **R6.** [BUG-967] (P7) `model_number` and `manufacturer` are stored trimmed; empty / whitespace-only is stored as `None`. `note` is stored as sent, `""` included. *(Today: stored as sent; `""` stored as `""`.)*
- **R6a.** [BUG-972] (Q3) Over 200 characters is rejected by `MachineUpdate`. *(Today: `DataError` at the flush.)*
- **R7.** [BUG-950] (HR-1) A sent name is stored trimmed, and `" Press "` on a machine named `"Press"` counts as equal (R9). Blank or whitespace-only is rejected by `MachineUpdate`. *(Today: stored as sent; `""` skips the duplicate check and is written.)*
- **R8.** A different name used by another live machine of the resulting factory → 409 `Machine with name '<name>' already exists in this factory` (`<name>` as in `create_machine` R3); nothing changes, other fields sent are not applied. Detection follows `_check_name_exists_in_factory` with the machine excluded. A name used only by a soft-deleted machine, or in another factory, is free.
- **R9.** A name equal to the current one is no change. Changing only the case of the own name succeeds, today and after BUG-952: the machine never conflicts with itself.
- **R10.** [BUG-954] (HR-2) Whenever the factory or the name changes, the resulting name is checked in the resulting factory: a plain move, or a move re-sending the same name, into a factory with a live machine of that name → the 409 of R8, nothing changes. *(Today: checked only when a different name is sent; the move is saved and two live machines share the name.)* A move with a new name that is free in the target succeeds, even if taken in the old factory.
- **R10a.** [BUG-953] (HR-2) A duplicate that reaches the flush gives the 409 of R8, not a database error; nothing changes. *(Today: no index.)*
- **R11.** A new `factory_id` of the workspace moves the machine. A missing factory, or one of another workspace → 404 `Factory with ID <factory_id> not found`; nothing changes.
- **R12.** [BUG-963] (P3) A soft-deleted target factory → 400 `Cannot move machine to deleted factory`, before the name check. A live but inactive target is accepted. *(Today: moved.)*
- **R13.** [BUG-961] (P1) `factory_id=0` is checked like any id → 404 `Factory with ID 0 not found`; nothing written. *(Today: `IntegrityError`, `machines_factory_id_fkey`.)*
- **R14.** `factory_id` equal to the current one: the factory is not looked up, nothing changes for that field.
- **R15.** Order of checks: R1, R2, R3, then the target factory (R11–R13), then the name (R8, R10). The section is checked last, after the fields are flushed (R21).
- **R16.** `factory_section_id` not in the request: the link is untouched (but see R20).
- **R17.** `factory_section_id` in the request: the section is set, moved or cleared through `set_assignment`, against the **resulting** factory; the returned machine reads the new value even if its link was loaded before the call. Clearing without a link is a no-op. A section of the old factory sent with a move → 400 `Factory section does not belong to this machine's factory`.
- **R18.** [BUG-909] (cited) Re-sending the section the machine already has writes nothing: same link `id`, `created_by`. *(Today: the link is deleted and re-created, `created_by` = the saver.)*
- **R19.** [BUG-971] (Q2) A `factory_section_id` equal to the current section, with no factory change, is not validated: an edit re-sending a link to a soft-deleted section succeeds and keeps the link. *(Today: 400 `Cannot assign a machine to a deleted factory section`; nothing saved.)* Clearing it, or omitting it, works today.
- **R20.** [BUG-970] (Q1) A move to another factory with `factory_section_id` not sent clears the link, and `changes` records `factory_section_id` from the old id to `None`. *(Today: the link stays on a section of the old factory; `changes` lists only `factory_id`.)*
- **R21.** On a refused section the field changes and `updated_by` are already flushed and no event exists; rolling back (the service does) undoes them.
- **R22.** Nothing else changes: `workspace_id`, `created_by`, `created_at`, `is_running`, `is_active`, `is_deleted`, `deleted_at`, `deleted_by`. An `is_running` in the request is ignored.
- **R23.** `updated_at` is set by the database whenever the machine row is written, that is, when a column value changes, the `updated_by` stamp included. A section-only change by the user already in `updated_by` changes no column of the row: `updated_by` and `updated_at` keep their values, while the link and the activity event record the change. (Holds today.)
- **R24.** [BUG-959] (HR-9) `updated_by` is written only when a field value or the section actually changes. Given `{}`, or values equal to the current ones, the call succeeds and `updated_by`, `updated_at` keep their values. A section-only change stamps `updated_by` when another user was stamped (R23 for the same user). *(Today: stamped on every successful call; `updated_at` with it whenever the stored `updated_by` differs.)*
- **R25.** When at least one logged field changed, one activity event: `event_type = "updated"`, `description = "Machine details updated"`, `performed_by = user_id`, `metadata_json = {"changes": [...]}`.
- **R26.** Each entry of `changes` is `{"field", "label", "from_value", "to_value"}` for a field of `MACHINE_LOG_FIELDS` whose value differs, in that order; values are strings or `None` (`factory_id` `"980003"` → `"980004"`; a section set from none: `None` → `"385108"`; cleared: `"385109"` → `None`).
- **R27.** Nothing changed, a re-sent section, or clearing an empty section: no event.
- **R28.** [BUG-975] (O4 — owner's answer) A machine with open work orders may move. In the same transaction, `work_orders.factory_id` becomes the new factory on **every** row with `workspace_id` = the argument, `machine_id` = the machine, `is_deleted = False` and `status` `DRAFT` or `IN_PROGRESS`; `updated_by = user_id` and `updated_at` is set on those rows (HR-9: a field changed). The title, status, dates, approvers, assignees and every other column stay. *(Today: the order keeps its `factory_id`, verified for `DRAFT` and `IN_PROGRESS`.)*
- **R28a.** [BUG-975] Closed orders stay: a row with `status` `COMPLETED` or `VOIDED`, or `is_deleted = True`, keeps its `factory_id`, `updated_by`, `updated_at`. So does an order of another machine, also one with a line sourcing parts from this machine, and an order with this `machine_id` in another workspace. (Holds today.)
- **R28b.** [BUG-975] It happens only on a real move: `factory_id` equal to the current one, a machine without open orders, or a refused call (R1–R3, R8, R10–R13) changes no work order and writes no `work_order_events` row. A section refused after the flush (R21) leaves the orders changed and their events written until the rollback, which undoes them with the machine. Rolling back a savepoint around the call restores the orders and removes the events.
- **R28c.** A consumed line (`work_order_items.consumed_at` set) is never changed: its `source_location_type` / `source_location_id` stay, because voiding the order and a `BORROW` return go back to that location. (Holds today.)
- **R28d.** (O4 SP-1, SP-2 — owner's answers) An unconsumed line keeps its source, also `source_location_type = 'storage'` with the old factory's id: parts of a moved order still come from the old factory's store when it is posted. A line sourcing from `'machine'` is unaffected. A move never changes a line, so it never resets approvals: recorded approvals, approver rows and `required_approvals` of a moved `DRAFT` stay. (Holds today.)
- **R28e.** [BUG-975] (O4 SP-3 — owner's answer) Each moved order gets exactly one `work_order_events` row: `work_order_id` = the order, `workspace_id` = the argument, `event_type = "updated"`, `description = "Order details updated"`, `performed_by = user_id`, `created_at` set, `metadata_json = {"changes": [{"field": "factory_id", "label": "Factory", "from_value": "<the order's own old factory_id>", "to_value": "<new factory id>"}]}` (ids as strings; that one entry, no other key). `from_value` is the order's own old `factory_id`, even when it differs from the machine's old factory (owner's answer, 2026-10-30). No event for an order R28a leaves alone, nor for any call of R28b that changes no work order: a refused or same-factory call writes none. The machine's own log records the move as in R25. *(Today: no event. `MachineManager` cannot call `WorkOrderManager.log_event`: that manager imports this one, so the row is written through `app/dao/work_order_event.py` or directly — FU-5.)*
- **R28f.** [BUG-975] (O4 SP-4 — owner's answer) `IN_PROGRESS` orders move like drafts. Parts already consumed stay booked out of the old factory (R28c, ledger rows untouched), while order lists and cost totals by factory follow the new one. *(Today: the order keeps its `factory_id`.)*
- **R29.** Unknown `user_id` → `IntegrityError` (`machines_updated_by_fkey`), nothing saved — today also for `{}`; after BUG-959 only when something changes.
- **R30.** Flushed, not committed: rolling back a savepoint restores the row and removes the event. The returned object is the instance read by the lookup.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| machine missing / other workspace | `HTTPException` 404 | `Machine with ID <machine_id> not found` |
| machine soft-deleted; [BUG-964] its factory soft-deleted | `HTTPException` 400 | `Cannot update a deleted machine` |
| target factory missing / other workspace; [BUG-961] `0` | `HTTPException` 404 | `Factory with ID <factory_id> not found` |
| [BUG-963] target factory soft-deleted | `HTTPException` 400 | `Cannot move machine to deleted factory` |
| name taken in the resulting factory | `HTTPException` 409 | `Machine with name '<name>' already exists in this factory` |
| section refused | `HTTPException` 404 / 400 | `create_machine` R11 |
| schema: blank name, `null` name / factory, over 200 characters | `pydantic.ValidationError` | not asserted |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** on a real change: the changed columns, `updated_by`, `updated_at`; at most one link row replaced or deleted; one `machine_activity_events` row; on a move, `factory_id`, `updated_by`, `updated_at` of each open work order of the machine (R28) and one `work_order_events` row per moved order (R28e); flushed. On a no-op nothing (intended). No commit.

---

## `MachineManager.get_machine(session, machine_id, workspace_id, include_deleted=False)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (used by: `MachineService.get_machine` ← `GET /machines/{id}/`)

**Purpose:** Fetch one machine of the caller's workspace.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `machine_id` | int | machine to fetch |
| `workspace_id` | int | caller's workspace |
| `include_deleted` | bool, default `False` | *(requires new parameter — BUG-955)* today it does not exist |

**Returns:** the `Machine`.

**Rules:**
- **R1.** A live machine of the workspace in a live factory is returned; `is_active` and `is_running` are not consulted.
- **R2.** No machine with that id, or one of another workspace → 404 `Machine with ID <machine_id> not found`.
- **R3.** [BUG-955] (HR-4) A soft-deleted machine → the same 404 by default. *(Today: returned.)*
- **R4.** [BUG-955] With `include_deleted=True` a soft-deleted machine of the workspace is returned; another workspace still gives 404. *(Requires the new parameter.)*
- **R5.** [BUG-966] (P6) A live machine whose factory is soft-deleted → the same 404 by default; returned with `include_deleted=True`. A live but inactive factory hides nothing. *(Today: returned.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace / hidden without `include_deleted` | `HTTPException` 404 | `Machine with ID <machine_id> not found` |

**Side effects:** none

---

## `MachineManager.search_machines(session, workspace_id, factory_id=None, factory_section_id=None, is_running=None, search=None, maintenance_window="all", has_model_number=None, has_manufacturer=None, latest_event_type=None, sort_by="name", sort_dir="asc", skip=0, limit=100, include_deleted=False)`
**Shape:** search
**Persistence:** reads
**Visibility:** public (used by: `MachineService.get_machines` ← `GET /machines/`, which passes everything except `include_deleted`)

**Purpose:** The machines page: filters, a maintenance filter based on open work orders, sorting including by next maintenance date, paging.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | workspace to list |
| `factory_id` … `latest_event_type` | as machine DAO `search_advanced` | handed to it unchanged |
| `maintenance_window` | str, default `"all"` | `"all"`, `"overdue"`, `"next_7_days"`, `"next_30_days"`, `"none_scheduled"`; free text |
| `sort_by` | str, default `"name"` | `"name"`, `"created_at"`, `"maintenance_date"`; others as DAO R13 |
| `sort_dir` | str, default `"asc"` | exactly `"desc"` = descending |
| `skip`, `limit` | int, defaults `0`, `100` | not validated here |
| `include_deleted` | bool, default `False` | never passed by the API today |

**Returns:** a `list` of `Machine` (possibly empty), each with its section readable.

**Rules:**
- **R1.** With `maintenance_window="all"` and `sort_by` other than `"maintenance_date"`, the result is exactly that of machine DAO `search_advanced` called with the same arguments: filters, sort, paging and all its rules and bugs (BUG-886, BUG-887, BUG-888, BUG-889, BUG-890, BUG-892 cited; `latest_event_type` raises `AttributeError` today).
- **R2.** Paging on that path is the DAO's: negative `skip` / `limit` → `DataError`.
- **R3.** On both paths, with `include_deleted=False`: only machines of `workspace_id` are returned, soft-deleted machines never, and a machine of a soft-deleted factory is hidden (BUG-890 cited, DAO R3a). A machine of a soft-deleted section follows DAO R6a (BUG-889 cited).
- **R4.** An unknown workspace id, or a workspace without machines, returns `[]` on both paths. `is_active` is never consulted; `is_running` only through its filter.
- **R5.** Any other window, or `sort_by="maintenance_date"`, takes the maintenance path: the same filters first, then the rules below. An empty result gives `[]`.
- **R6.** On that path the list keeps the DAO's order for `sort_by` / `sort_dir` (`"name"`, `"created_at"`), and `latest_event_type` raises the same `AttributeError` until BUG-886 is fixed.
- **R7.** [BUG-958] (HR-5) Every matching machine is considered, however many there are. *(Today: only the first 10 000 by the list order: given 10 001 machines, a machine past them with work due tomorrow is not found by `next_7_days`.)*
- **R8.** A machine's **work dates** are the `planned_date`s of work orders with that `machine_id`, in the workspace, `is_deleted = False`, status `DRAFT` or `IN_PROGRESS`, with a date. `COMPLETED`, `VOIDED`, soft-deleted, undated and other-workspace orders do not count. A soft-deleted machine has no work dates, whatever its orders. The factory's state is not looked at: a live machine of a soft-deleted factory keeps its work dates, and with `include_deleted=True` it is treated like any live machine. (Holds today.)
- **R9.** [BUG-973] (Q4) Work dates have no time limit. *(Today: only dates from today − 3650 days to today + 365 days inclusive count: +365 counts, +366 does not; −3650 counts, −3651 does not.)*
- **R10.** ✅ (O2) `overdue`: the machine has an `IN_PROGRESS` work date strictly before today. A `DRAFT` past its date does not count, nor does an `IN_PROGRESS` order dated today.
- **R11.** `next_7_days`: a work date from today to today + 7 inclusive (today and +7 yes, +8 no). A machine also overdue qualifies if it has such a date.
- **R12.** `next_30_days`: the same with 30 (+30 yes, +31 no).
- **R13.** ✅ (O2) `none_scheduled`: no work date on or after today. A machine with only past open work is listed here.
- **R14.** ✅ (P8) Any other value (`"bogus"`, `"OVERDUE"`, `""`) takes the maintenance path and filters nothing: every machine of the DAO's result, then paged. No error.
- **R15.** "Today" is the server's `date.today()`.
- **R16.** `sort_by="maintenance_date"`, ascending: by each machine's earliest work date on or after today, earliest first; machines with none come last. Past dates are ignored for the sort. Ties keep name order.
- **R17.** `sort_dir="desc"` (exactly): latest first; machines with none **still last**; ties keep name order **ascending**. Any other `sort_dir` (`"DESC"`) sorts ascending.
- **R18.** Ties inherit the DAO's name order (BUG-887: on a case-only tie, today "bolt" precedes "Bolt" whatever the `id`).
- **R19.** On the maintenance path, paging is applied last, in Python: `skip` matching machines skipped, at most `limit` returned; `limit=0` or `skip` past the end → `[]`. Negative values raise nothing (Python slice) and are unreachable through the API; no case.
- **R20.** [BUG-956] (HR-4) `include_deleted` is reachable from `GET /machines/` (fix in `MachineService.get_machines` and the endpoint — integration-only). *(Today: never passed.)*
- **R21.** [BUG-957] (HR-5, HR-6) With `include_deleted=True` soft-deleted machines of the workspace, and machines of soft-deleted factories, are listed with the live ones, and everything else behaves as with `False`: every filter of R1, the maintenance path, `sort_by` / `sort_dir`, and paging after filtering. A deleted machine has no work dates (R8). *(Today: one page is cut first, in no defined order; `factory_id`, `factory_section_id`, `is_running` and `search` are then applied in Python to that page; `has_model_number`, `has_manufacturer`, `latest_event_type`, `maintenance_window`, `sort_by`, `sort_dir` are ignored. Example, only while that row is physically last: 3 machines, the third in factory F4: `factory_id=F4, limit=2` → `[]`.)*

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| R2 negative `limit` / `skip` | `sqlalchemy.exc.DataError` (`InvalidRowCountInLimitClause` / `InvalidRowCountInResultOffsetClause`) | `LIMIT must not be negative` / `OFFSET must not be negative` |
| *(today only — BUG-886)* `latest_event_type` set | `AttributeError` | — |

**Side effects:** none

---

## `MachineManager.delete_machine(session, machine_id, workspace_id, user_id)`
**Shape:** soft-delete
**Persistence:** writes
**Visibility:** public (used by: `MachineService.delete_machine` ← `DELETE /machines/{id}/`, 200 with the machine)

**Purpose:** Soft-delete a machine that is not in use, and log it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `machine_id` | int | machine to delete |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | deleter; `deleted_by`, the event's `performed_by` |

**Returns:** the same `Machine` instance, soft-deleted and flushed, not committed.

**Rules:**
- **R1.** No machine with that id, or one of another workspace → 404 `Machine with ID <machine_id> not found`.
- **R2.** Already soft-deleted → 400 `Machine is already deleted`; the stamp stays, no event.
- **R3.** [BUG-965] (P5) A live machine whose factory is soft-deleted → 400 `Cannot delete a machine of a deleted factory`; nothing written. A live but inactive factory is not refused. *(Today: deleted normally.)*
- **R4.** [BUG-968] (standing decision 3; O1) A machine **in use** is not deleted: `ValueError` per R4a; nothing written, no event. Checked after R1–R3. The rows below belong to the machine's workspace. A row of another workspace pointing at this machine is **invalid data** that must never be created (FU-7); if one exists and meets a condition below, the machine is still in use and the refusal shows it only as the generic entry of R4a. **Of another workspace** means: the `machine_items` row, the purchase order or the transfer order has another `workspace_id`; for a work order, the order has, or for (c) (ii) the order or the sourcing line has. A foreign row that meets no condition (a purchase order at `Complete`, say) does not block. The state of what a blocker points at, other than this machine, is not looked at (owner's answer 2026-10-30, gap 12): a blocker still counts when the order's factory (`work_orders.factory_id`) or the other end of a transfer is soft-deleted. Purchase and transfer orders have no factory column of their own. In use when at least one holds:
  - **(a) Stock:** a `machine_items` row of the machine with `qty ≠ 0` (negative counts). Not `qty = 0`, whatever `req_qty` / `defective_qty` hold.
  - **(b) Purchase order:** `destination_type = 'machine'`, `destination_id` = the machine, `voided = False`, current stage (`current_status_id` → `statuses.name`) not `Complete`. Not `Complete`; not voided; not another `destination_type` with the same id.
  - **(c) Work order:** a work order with `is_deleted = False`, status `DRAFT` or `IN_PROGRESS`, and either (i) `machine_id` = the machine, whatever its lines, or (ii) a line still to draw on the machine: `work_order_items.is_deleted = False`, `uses_inventory = True`, `consumed_at` NULL, `source_location_type = 'machine'`, `source_location_id` = the machine. For (ii) the order's own `machine_id` does not matter: another machine, none, or a **soft-deleted machine** (owner's answer, gap 12). Not `COMPLETED` / `VOIDED`; not a soft-deleted order or line; **not a sourcing line already consumed (`consumed_at` set) or with `uses_inventory = False`** (owner's answer, gap 12), unless (i) or another line blocks that order.
  - **(d) Transfer order:** `completed_at` NULL, and source or destination is the machine (`source_location_type = 'machine'` with `source_location_id`, or `destination_location_type = 'machine'` with `destination_location_id`). The other end may be a soft-deleted factory or a soft-deleted machine (owner's answer, gap 12). Not completed ones; not another location type with the same id.

  *(Today: none of this is looked at; verified with stock, an in-progress work order, a purchase order and a transfer order on the machine.)*
- **R4a.** [BUG-968] **The refusal lists every blocker.** The `ValueError` has exactly two args: `args[0] == "Machine has stock or open orders"`; `args[1]` = a `list` of `dict`s with exactly the keys `"type"` and `"id"`, except the generic entry below:
  - `"type"`: `"machine_stock"` (a), `"purchase_order"` (b), `"work_order"` (c), `"transfer_order"` (d), and `"other_workspace"` (last bullet), which has no `"id"`;
  - `"id"`: the `machine_items` row id for `machine_stock`, the **order** id otherwise, never a line id;
  - one entry per stock row or order: an order that qualifies twice (a work order on the machine and sourcing from it; a transfer from and to it) appears once; a work order whose only link is a line R4 (c) excludes is not listed;
  - sorted by `"type"` in the order above, then `"id"` ascending;
  - only blocking rows; never empty when raised;
  - **rows of another workspace (R4) are never listed by id:** when at least one exists, the list ends with exactly one `{"type": "other_workspace"}`, the only key, however many such rows there are, sorted last. Nothing of the other workspace is exposed. A machine in use only through such rows gets a list of that one entry. An order of this workspace that qualifies through (c) (i) keeps its own entry even if a foreign line also points here, and that line adds the generic entry. A purchase order of this workspace on another workspace's stage is this workspace's row and is listed normally. (Owner's approved answer, 2026-10-30.)
  The 400 body is `MachineService`'s translation (FU-1); showing it is BUG-969.
- **R4b.** Nothing else blocks, and nothing else is written: maintenance logs (`machine_maintenance_logs.machine_id`), activity events, `machine_item_ledger` rows, a work order template naming the machine (`work_order_templates.default_machine_id`; BUG-340 cited), a production line (`production_lines.machine_id`) or formula stage (`production_formula_stages.machine_id`) naming it, a sourcing line already consumed or with `uses_inventory = False` (R4 (c)), its section link, `is_running = True`. The delete never changes stock rows or orders (holds today; after the fix they are only read).
- **R5.** Given a live machine not in use: `is_deleted = True`, `is_active = False`, `deleted_at` = `utcnow()`, `deleted_by = user_id`; no other column by the method (`updated_by` unchanged); `updated_at` set by the database (machine DAO `soft_delete` R1, R2).
- **R6.** The section link is kept; `factory_section_id` still reads it. `is_running` stays as it was (`soft_delete` R2, R3).
- **R7.** One activity event: `event_type = "deactivated"`, `description = "Machine deactivated: <name>"`, `performed_by = user_id`, `metadata_json = None`.
- **R8.** Afterwards, in the same session: not listed by `search_machines` by default; its name can be reused (`create_machine` R4); `update_machine` answers 400; a second delete answers R2; `get_machine` follows its R3 / R4.
- **R9.** Unknown `user_id` → `IntegrityError` (`machines_deleted_by_fkey`); the machine stays live, no event.
- **R10.** Flushed, not committed: rolling back a savepoint makes the machine live again and removes the event. The returned object is the instance read by the lookup.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `HTTPException` 404 | `Machine with ID <machine_id> not found` |
| already deleted | `HTTPException` 400 | `Machine is already deleted` |
| [BUG-965] factory soft-deleted | `HTTPException` 400 | `Cannot delete a machine of a deleted factory` |
| [BUG-968] in use | `ValueError` (two args, R4a) | `args[0] == "Machine has stock or open orders"`; `args[1]` = blocker list |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** nothing when refused. Otherwise one `machines` row updated, one `machine_activity_events` row; flushed. No commit.

---

## `MachineManager.create_machine_event(session, event_data, workspace_id, user_id, work_order_id=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `MachineService.create_machine_event` ← `POST /machines/{id}/events/`, which never passes `work_order_id`; `WorkOrderManager._set_machine_status`, which always does, on start, on complete, and on voiding an in-progress order)

**Purpose:** Record a status change in the activity log and keep `is_running` in step.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session; not committed here |
| `event_data` | `MachineEventCreate` | `machine_id`, `event_type`, optional `note` (not trimmed) |
| `workspace_id` | int | caller's workspace |
| `user_id` | int | `performed_by`, and `updated_by` when `is_running` changes |
| `work_order_id` | int \| `None` | must name a live work order of the workspace (R2a); stored in the metadata when not `None` |

**Returns:** a `MachineEventResponse` built from the new activity row.

**Rules:**
- **R1.** No machine with that id, or one of another workspace → 404 `Machine with ID <machine_id> not found`; nothing written.
- **R2.** ✅ (O5) A soft-deleted machine → 400 `Cannot create event for a deleted machine`; nothing written. Also when a work order is driving it: the work order transition then fails, as intended.
- **R2a.** [BUG-1000] (correction round, owner: cross-workspace links are refused) A `work_order_id` not `None` that names no live work order of `workspace_id` (another workspace's, unknown, `0`, or a soft-deleted order of the workspace — owner's answer, 2026-10-30/31) → 404 `Work order with ID <work_order_id> not found`; nothing written. Checked right after R2, before the current status. Apart from `is_deleted`, the order's state and its `machine_id` are not looked at. *(Today: not validated, the id is stored in the metadata; verified with another workspace's order and with an unknown id. No API path reaches it: the only caller passes its own order.)*
- **R3.** [BUG-974] (O3) A live machine whose factory is soft-deleted, with `work_order_id` `None` (a manual change) → 400 `Cannot create event for a machine of a deleted factory`; nothing written. Checked after R2, before the current status. A live but inactive factory is not refused. *(Today: accepted, event and `is_running` written.)*
- **R3a.** (O3) With a `work_order_id` that passes R2a the same machine is accepted and everything below applies, so open orders can finish. (Holds today.)
- **R4.** The **current status** is the `status` key of the metadata of the machine's newest activity row with `event_type = "status_updated"` in this workspace: newest `created_at`, ties to the highest `id`. Other event types, and rows of another workspace, are ignored even if they carry a `status`.
- **R5.** A new status equal to the current one → 400 `Machine is already in '<STATUS>' state` (`<STATUS>` upper-case); nothing written.
- **R6.** No status row, or a newest one with `NULL` metadata or no `status` key: there is no current status, any status is accepted, `from_value` is `None`. Older rows are not consulted.
- **R7.** `description` = `Status set to <status in lower case>`; with a truthy note, ` (<note>)` is appended. `""` adds nothing; `"   "` is appended as typed (`Status set to idle (   )`).
- **R8.** One activity event: `event_type = "status_updated"`, `performed_by = user_id`, `workspace_id` = the argument, `metadata_json = {"status": "<STATUS>", "note": <note as sent, None or "" included>, "changes": [{"field": "status", "label": "Status", "from_value": <current or None>, "to_value": "<STATUS>"}]}`.
- **R9.** A `work_order_id` that passes R2a adds `"work_order_id": <value>` to the metadata; `None` adds no key.
- **R10.** `RUNNING` → `is_running = True`; every other status → `is_running = False`.
- **R11.** When that changes the stored value, `updated_by = user_id` and `updated_at` is set.
- **R12.** When it does not (a first `IDLE` on a stopped machine, `OFF` after `MAINTENANCE`, a first `RUNNING` on a machine already `is_running = True`), the event is still written and `updated_by`, `updated_at` keep their values.
- **R13.** The response has `id` = the event's id, `workspace_id`, `machine_id`, `event_type` (a `MachineEventTypeEnum` member, the input's; a `str` enum, so it also equals `"IDLE"`), `note` from the input, `started_at` = `created_at` = the event's `created_at`, `initiated_by` = `created_by` = `user_id`.
- **R14.** [BUG-960] (HR-10) The machine row is read with a row lock (`SELECT … FOR UPDATE`) before the current status is read; the loser of a race sees the new status and gets R5. *(Today: no lock.)*
- **R15.** Unknown `user_id` → `IntegrityError` (`machine_activity_events_performed_by_fkey`); `is_running` unchanged, no event.
- **R16.** Flushed, not committed: rolling back a savepoint removes the event and restores `is_running`, `updated_by`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| missing / other workspace | `HTTPException` 404 | `Machine with ID <machine_id> not found` |
| soft-deleted | `HTTPException` 400 | `Cannot create event for a deleted machine` |
| [BUG-1000] `work_order_id` not a live work order of the workspace (soft-deleted included) | `HTTPException` 404 | `Work order with ID <work_order_id> not found` |
| [BUG-974] manual change, factory soft-deleted | `HTTPException` 400 | `Cannot create event for a machine of a deleted factory` |
| already in that status | `HTTPException` 400 | `Machine is already in '<STATUS>' state` |
| unknown `user_id` | `IntegrityError` / `ForeignKeyViolation` | — |

**Side effects:** one `machine_activity_events` row; `is_running`, `updated_by`, `updated_at` when `is_running` changes; flushed. No commit.

---

## `MachineManager._check_name_exists_in_factory(session, workspace_id, factory_id, name, exclude_id=None)`
**Shape:** validator
**Persistence:** reads
**Visibility:** internal (used by: `create_machine`; `update_machine` with `exclude_id` = the machine)

**Purpose:** Tell whether a live machine of a factory already uses a name.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `workspace_id` | int | workspace to check |
| `factory_id` | int | factory to check |
| `name` | str | name to look for |
| `exclude_id` | int \| `None` | machine id to ignore |

**Returns:** `True` if a matching live machine exists, else `False`. Never raises.

**Rules:**
- **R1.** A live machine of that factory and workspace with that name (in the sense of R4) → `True`.
- **R2.** A machine of another factory, or the factory id seen from another workspace → `False`.
- **R3.** A soft-deleted machine is ignored.
- **R4.** [BUG-952] (HR-2) Names match regardless of case and of surrounding whitespace (`str.strip()`): with a live "Press", `"press"`, `"PRESS"`, `"Press "`, `"\tPress"` → `True`; `"Press  2"`, `"Pres"` → `False`. *(Today: exact comparison.)*
- **R5.** [BUG-951] (HR-2) Every live machine of the factory is examined. *(Today: at most 100 live machines, in no defined order: given 101, exactly one name is not found; given 150, 50. Soft-deleted machines do not use up a place.)*
- **R6.** Given `exclude_id`, that machine is ignored; any other match still gives `True`. `None` ignores none.
- **R7.** No live machines, or an unknown factory → `False`.
- **R8.** [BUG-891] (cited) In a soft-deleted factory → `False` (machine DAO `get_by_factory` R3a). No caller reaches it after BUG-963 and BUG-964. *(Today: `True` for a live match.)*

**Errors:** none

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 61–68 | factory missing / other workspace → 404 | `create_machine` R1 |
| 61 (no `is_deleted` check) | soft-deleted factory accepted | `create_machine` R2 |
| 71–80 | name exists → 409 | `create_machine` R3, R4, R9 |
| 83–88 | dump without section; `workspace_id`, `created_by`, `is_running = False`; no normalisation; FK | `create_machine` R5–R8, R14 |
| 90–96 | section given → `set_assignment`, expire / `None` → skip | `create_machine` R10, R11, R12 |
| 98–105 | `created` event, always | `create_machine` R13, R15 |
| 117–124 | machine missing / other workspace → 404 | `update_machine` R1 |
| 125–129 | deleted → 400 | `update_machine` R2 |
| 125 (no factory check) | machine in a deleted factory accepted | `update_machine` R3 |
| 131 | fields sent | `update_machine` R16, R17 |
| 132 | `factory_id` truthy → it / else current (`0`, `None`) | `update_machine` R13, R14, R17 |
| 135 | truthy and different → validate / else skip (`0`, `None`, same) | `update_machine` R11, R13, R14 |
| 136–143 | target missing / other workspace → 404; no `is_deleted` check | `update_machine` R11, R12 |
| 146 | `name` truthy and different → check / else skip (`None`, `""`, same; plain move) | `update_machine` R7, R8, R9, R10 |
| 147–156 | name exists (self excluded) → 409 | `update_machine` R8 |
| 160 | `exclude_unset` / `exclude_none`: `null` dropped, `""` kept | `update_machine` R4, R5, R6 |
| 161–162 | section popped; `updated_by` always set | `update_machine` R24 |
| 164–169 | changelog; section only if sent | `update_machine` R25, R26, R27 |
| `machine_activity_manager.py` 57–71 | field absent → skip; equal → skip; else entry | `update_machine` R26, R27 |
| `machine_activity_manager.py` 39–48 | value formatting: `None`, else `str`; enum / date branches unused here | `update_machine` R26 |
| 170 | DAO update, flush | `update_machine` R4, R22, R23, R29 |
| 172–181 | section sent → `set_assignment`, expire / else skip | `update_machine` R16–R21 |
| — (no write) | a move leaves work orders and their events alone | `update_machine` R28, R28a–R28f |
| 183–192 | `changes` non-empty → event / else none | `update_machine` R25, R27 |
| 202–210 | missing / other workspace → 404; no `is_deleted` or factory check | `get_machine` R1–R5 |
| 231 | `include_deleted` true → raw path | `search_machines` R21 |
| 233–250 | raw page, then four Python filters; each `is not None` / truthy | `search_machines` R21 |
| 252–253 | no window and no maintenance sort → DAO | `search_machines` R1, R2 |
| 270–284 | maintenance path: `skip=0, limit=10_000`; `maintenance_date` → name asc | `search_machines` R5, R6, R7, R16 |
| 286–287, 292–293 | today; date range | `search_machines` R9, R15 |
| 288–294 | open-order dates; `ids` empty → `{}` | `search_machines` R5, R8 |
| 295–302 | `IN_PROGRESS` dates | `search_machines` R8, R10 |
| 306–307 | `"all"` inside the filter: never true | dead (P9) |
| 308–309 | `none_scheduled` | `search_machines` R13 |
| 310–311 | `overdue` | `search_machines` R10 |
| 312–313 | `next_7_days` | `search_machines` R11 |
| 314–315 | `next_30_days` | `search_machines` R12 |
| 316 | unknown value → keep | `search_machines` R14 |
| 318–319 | window ≠ `all` → filter (`all` + maintenance sort → no filter) | `search_machines` R5 |
| 321–334 | `maintenance_date`: key; `reverse`; second sort puts no-date last | `search_machines` R16, R17, R18 |
| 336 | Python slice | `search_machines` R19 |
| 346–353 | missing / other workspace → 404 | `delete_machine` R1 |
| 354–358 | already deleted → 400 | `delete_machine` R2 |
| — (no check) | factory state; stock and open orders; every blocker collected | `delete_machine` R3, R4, R4a, R4b |
| 360 | DAO soft delete, flush, FK | `delete_machine` R5, R6, R9 |
| 361–369 | `deactivated` event, always | `delete_machine` R7, R8, R10 |
| 386–393 | missing / other workspace → 404 | `create_machine_event` R1 |
| 394–398 | deleted → 400 | `create_machine_event` R2 |
| 394 (no factory check) | machine in a deleted factory accepted; `work_order_id` tells the two paths apart | `create_machine_event` R3, R3a |
| 386 (no lock) | read without `FOR UPDATE` | `create_machine_event` R14 |
| 400–403 / `machine_activity_manager.py` 153–157 / `machine_activity_event.py` 44–60 | latest status row; no row / empty metadata → `None`; `.get("status")` | `create_machine_event` R4, R6 |
| 405–409 | `prev_status` truthy and equal → 400 | `create_machine_event` R5, R6 |
| 411–413 | note truthy → appended | `create_machine_event` R7 |
| 415–426 | metadata | `create_machine_event` R8 |
| 427–428 | `work_order_id is not None` → key; not validated | `create_machine_event` R2a, R9 |
| 430–438 | event, flush, FK | `create_machine_event` R8, R15, R16 |
| 440–445 | `is_running` differs → update / else none | `create_machine_event` R10, R11, R12 |
| 447–457 | response | `create_machine_event` R13 |
| 470–473 / `dao/machine.py` | capped, unordered, live machines of factory and workspace | `_check_name_exists_in_factory` R2, R3, R5, R7, R8 |
| 474–477 | loop: empty / many; exact `==`; `exclude_id`; `True` on first / `False` at end | `_check_name_exists_in_factory` R1, R4, R6, R7 |

## Gap log
G1 (`machine_manager.cases.md` gap 1) — Fact — Notes: classes of `work_order_approvers` and `work_order_assignees`, a recorded approval defined (`approved = True`, `approved_at` set), assignees named. No order-workflow decision needed: R28d already holds the owner's answer.
G2 (gap 2) — Fact — `delete_machine` R4b names the columns; Notes table gives classes and required columns of the maintenance log, template, production line, formula and stage.
G3 (gap 3) — Intent, answered, then corrected — the first answer (the item carry-over "by machine id only, whatever `workspace_id`") is **withdrawn**: the owner never meant it as a normal state (2026-10-30). Now: a cross-workspace row is invalid data and must be refused at creation; `delete_machine` still refuses if one exists, with one generic `{"type": "other_workspace"}` entry, the owner's approved answer ("yeah i agree with your recommendations"). `delete_machine` R4, R4a; Notes "Rows of another workspace"; FU-1 point removed; FU-7. `update_machine` R28 is unaffected: it moves only orders of the caller's workspace, and a foreign order is not a valid state.
G4 (gap 4) — Intent — decided by Claude under the reviewer's delegation (2026-10-30), per factory manager `create_factory` R3 (department Q13): the 409 shows the submitted name as the manager receives it, trimmed once BUG-950 is fixed, never the existing spelling. `create_machine` R3, `update_machine` R8.
G5 (gap 5) — Intent — decided by Claude under the reviewer's delegation (2026-10-30), per the factory rule "`updated_at` with it whenever that changes the stored `updated_by`": a section-only change by the user already stamped writes no column, so `updated_by` and `updated_at` keep their values; holds today, no bug. `update_machine` R23, R24.
G6 (gap 6) — Contradiction — decided by Claude under the reviewer's delegation (2026-10-30): physical order is not an order (standing decision 4), so the BUG-957 page-before-filter card is non-strict; the ignored-filter and window cards stay strict. `search_machines` R21 example, Notes.
G7 (gap 7) — Fact plus Intent — decided by Claude under the reviewer's delegation (2026-10-30): R8 now states that a deleted machine has no work dates and that the factory's state is not looked at, so with `include_deleted=True` a live machine of a soft-deleted factory keeps its work dates (per R21, BUG-924). `search_machines` R8.
G8 (gap 8) — Intent — decided by Claude under the reviewer's delegation (2026-10-30): inherited DAO bugs are cards to the intended behavior, xfail with that bug's ID, strict except BUG-887 (non-strict, standing decision 4). Notes.
G9 (gap 9) — Fact — `MachineEventResponse.event_type` is a `MachineEventTypeEnum` member (verified). `create_machine_event` R13.
G10 (gap 10) — Fact — Notes table: classes and import paths of `machine_items`, `purchase_orders`, `transfer_orders`, `work_orders`, `work_order_items`, `statuses`.
G12 (gap 12) — Intent, answered — owner's answer 2026-10-30, verbatim choice "1 and 2 block, 3 not": a blocker counts when the order's factory or the other end of a transfer is soft-deleted; a sourcing line blocks when its order belongs to a soft-deleted machine; a sourcing line already consumed or with `uses_inventory = False` does not block. `delete_machine` R4 intro, R4 (c), (d), R4a, R4b (BUG-968); Notes "Sourcing lines"; FU-5.
G13 (correction round) — Fact plus owner's answer — the machine's own links checked: factory and section of another workspace refused today; `work_order_id` of another workspace or unknown is stored. `create_machine_event` R2a (new, BUG-1000), R3a, R9.
G14 (coordinator's relay of the owner's answer, 2026-10-30) — Intent, answered — in `update_machine` R28e, `from_value` is the order's own old `factory_id`, even when it differs from the machine's old factory. `update_machine` R28e (BUG-975).
G15 (coordinator's relay of the owner's answer, 2026-10-30/31) — Intent, answered — in `create_machine_event` R2a a soft-deleted work order of the workspace gets the same 404; the order's other state and its `machine_id` stay not looked at. `create_machine_event` R2a, Inputs, Errors (BUG-1000).
