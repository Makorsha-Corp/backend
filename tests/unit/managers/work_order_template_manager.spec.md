# Spec — `app/managers/work_order_template_manager.py`

> **Status:** APPROVED (2026-11-07; nothing open). OQ-19, OQ-20, OQ-21 answered by the owner on 2026-11-07 and applied.
> **Source commit:** e48a092

> **Revision 2026-11-07 (apply-review of the owner's answers; fill-gaps of `work_order_template_manager.cases.md` gaps 1–13).** Owner, 2026-11-07: OQ-19 bug → 🐞 BUG-2345 (`generate_drafts` R4); OQ-20 intended (`generate_drafts` R10 ✅); OQ-21 bug → 🐞 BUG-2346 (`create_template` R6, `update_template` R9). Decided by Claude under the reviewer's delegation (2026-11-07): how OQ-21 counts approvers and when it is checked (R6, R9); the approver refusal comes before anything is written (gap 8); a `REPLACE` line keeps its replaced item (gap 9, `update_item` R3); `cost` and line `quantity` beyond `Numeric(15, 2)` are refused by the schema → 🐞 BUG-2350 (gap 7); the 404 words and the merged-state 422 details (gaps 2, 3); the order of the reference checks. Facts added for gaps 1, 5, 6, 11, 12, 13; test mechanics for gaps 4, 10. Gap log at the end.

> **Review round 2026-11-06.** House-rule and precedent lines decided by Claude under the reviewer's delegation (2026-11-06): BUG-2334 … BUG-2344. Existing bugs whose rules land here: BUG-1015 (HR-16 links), BUG-1228 (owner, deleted type), BUG-360 … BUG-363 (recurrence fields; their rules live in `tests/unit/utils/work_order_recurrence.spec.md` and are cited, not repeated), BUG-340 / BUG-341 (default machine, in `tests/unit/utils/work_order_generation.spec.md`). Below the manager: `tests/unit/dao/work_order_template.spec.md` (written alongside), `tests/unit/dao/work_order_type.spec.md`, `tests/unit/dao/base.spec.md`. `WorkOrderManager` (no spec yet) makes the actual work orders; its behaviour is named here only as outcomes.
>
> **Verified by running** (`v1.py`, `v2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\A\`, one outer transaction rolled back against `marker_test`; nothing committed): blank `template_name` `"  "` stored as is; approvers `[u, u, suspended, non-member, unknown id]` → only `u` kept, no error, `approver_slot` `None`; `create_template` stores a `REPLACE` line with no replaced item, `add_item` refuses the same line (400 `Select the item being replaced`), and making a work order from that template fails with the same 400; an empty update stamps `updated_by`; `description: null`, `cost: null` leave the old values; `restore_template` of an active template stamps `updated_by`; `cost` `0.125` stored `0.13`; `approver_user_ids: null` clears the approvers; **a section-scoped `generate_drafts` made a draft for a weekly template of that section not due for six more days, again the next day, and left its next date unchanged; an unscoped run made none**; an overdue weekly template (due 03-16, run 03-30) got one draft, for 03-30, and its next date became 04-06; a non-recurring template with a default machine and no section gets nothing from an unscoped run; a template with `requires_approval = True` and no approvers gives a work order stamped approved at once (`approved_at` set). **Not run:** HTTP; concurrent requests; `generate_drafts_for_anchored_range` through the sheet; the intended behaviour of any bug.

## Review

### OWNER — answered 2026-11-07 (`docs/testing/owner-questions.md` OQ-19 … OQ-21)

### Q1. OWNER — A section's "Plan day" run makes drafts for recurring templates that are not due — OQ-19 — 🐞 BUG-2345
**Background:** `POST /work-order-templates/generate-drafts/` (`generate_drafts`) makes draft work orders for one day. It takes (a) recurring templates that are due that day and (b), when a section is given, every active template whose default section is that section. The endpoint is labelled deprecated ("range auto-generates on sheet anchor") and no screen of the web app calls it; it is reachable through the API.
**What happens today, verified:** a recurring template of the section that is **not due** is taken under (b) and gets a draft every time the section is planned; its next date does not move, so it is "due" again later as well. An unscoped run gives it nothing.
**Example:** "Weekly belt check", Mondays, next run 16 March, section Packing. Planning Packing for 10 March and 11 March makes a draft on each day, then another on the 16th.
**Rules affected:** `generate_drafts` R1, R4.
**Suggested answer:** bug — in a section run a recurring template gets a draft only when due (as in an unscoped run); only non-recurring templates of the section get one every run. Alternative: retire the deprecated endpoint and `generate_drafts` altogether (the sheet's anchored range already generates recurring drafts).
**Answer:** owner, 2026-11-07: suggested answer (a recurring template gets a draft only when due).
**Resolution:** 🐞 BUG-2345 (pattern `recurring-template-generated-when-not-due`). In a section run, (b) takes only the section's **non-recurring** active templates; recurring ones come only through (a), when due. Rules: `generate_drafts` R1, R4.

### Q2. OWNER — A late run skips the missed dates of a recurring template — OQ-20 — ✅ intended
**Background:** Same endpoint. A due template's next date is moved forward from the **run's** date, not from its own next date.
**What happens today, verified:** a weekly template due 16 March, planned on 30 March, gets one draft (30 March); 16 and 23 March get none, and its next date becomes 6 April.
**Example:** Nobody ran "Plan day" for two weeks. The oil change due on the 16th and the 23rd never appears; the next one is planned for 6 April.
**Rules affected:** `generate_drafts` R10.
**Suggested answer:** intended — the run plans the day asked for; catching up is a manual decision (and the endpoint is deprecated). Alternative: one draft per missed date up to the run's date, as `generate_drafts_for_anchored_range` does.
**Answer:** owner, 2026-11-07: suggested answer (intended: missed dates are skipped; catching up stays manual).
**Resolution:** rule unchanged, marked ✅: `generate_drafts` R10.

### Q3. OWNER — "Requires approval" with no approvers gives orders that are approved at once — OQ-21 — 🐞 BUG-2346
**Background:** A template has `requires_approval` and a list of default approvers. Making a work order from it copies the approvers only when `requires_approval` is true. A work order with no approvers is stamped "Ready to start — no approval required" (your BUG-1204 answer keeps that for orders that never had an approver).
**What happens today, verified:** `requires_approval: true` with no approvers (or with only approvers who are no longer active members, who are skipped) is accepted, and every work order made from it is approved on creation.
**Example:** "Boiler shutdown" is marked as needing approval but nobody was picked. Each generated order can be started at once.
**Rules affected:** `create_template` R6, `update_template` R9.
**Suggested answer:** bug — a template with `requires_approval: true` must have at least one approver: create and update refuse otherwise with 400 `Choose at least one approver, or turn off "requires approval"`, nothing written (checked on the merged state). Alternative: allow it, but the generated order is not approved until someone is added (as BUG-1204 for orders that lost their last approver).
**Answer:** owner, 2026-11-07: suggested answer (create and update refuse a template that requires approval but has no approvers, 400, nothing saved).
**Resolution:** 🐞 BUG-2346 (pattern `vacuous-approval-met`). Rules: `create_template` R6, `update_template` R9. **Details decided by Claude under the reviewer's delegation (2026-11-07):** the count is of the approvers the template will hold after the call. After BUG-2335 every approver accepted is an active member, so a list of only inactive people is refused by BUG-2335's 400 first. Approvers who were active when chosen and have since been suspended or removed still count: the template is not re-checked when a membership changes (FU-2), and `WorkOrderManager` skipping them when copying is its FU-1 (a). On update the check runs only when the request sends `requires_approval` or `approver_user_ids`, so a template stored before the fix can still be renamed or otherwise edited.

### House-rule violations — applied automatically

- **HR-1** `create_template` R2, `update_template` R4 — `template_name` is stored as sent: `"  "` accepted (verified), no trimming. Intended: trimmed; blank or whitespace-only rejected by `WorkOrderTemplateCreate` / `WorkOrderTemplateUpdate` (422), nothing written; `null` on update is rejected (422) with BUG-2339.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2334 (pattern `blank-name-accepted`). Fix in `app/schemas/work_order_template.py`.
- **HR-9** `update_template` R10, `restore_template` R2 — `updated_by` is written on every update, an empty one included, and on restoring a template that is already active (both verified). `delete_template` already skips an inactive template. Intended: written only when a template field or the approver set actually changes.
**Answer:** bug — per HR-9 (house rule)
**Resolution:** 🐞 BUG-2340 (pattern `audit-stamp-on-noop`).
- **HR-5** `generate_drafts` R3 — the section's templates are found by loading the workspace's first 1000 active templates (newest first) and filtering by section in Python. With more than 1000 active templates, a section's older templates are silently skipped. Intended: all active templates of the section, filtered in the query, no cap.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-2342 (pattern `paginate-before-filter`).
- **HR-10** `generate_drafts` R11, `generate_drafts_for_anchored_range` R6 — both read the template's `next_generation_date` and look for an existing order, then create drafts and move the date, without a lock. Two runs at once both see "no order yet" and both create a draft (duplicate side effects). Intended: the template row is read `FOR UPDATE` (refreshed) before the checks; the second run waits, then sees the moved date and the drafts already made, and creates nothing twice.
**Answer:** bug — per HR-10 (house rule)
**Resolution:** 🐞 BUG-2343 (pattern `hr-10-unlocked-state-transition`).
- **HR-14** `generate_drafts` R12 — one template's failure (a work order that cannot be made: e.g. after BUG-1228 a deleted type, an inactive approver set aside, a machine of another workspace before BUG-340) raises out of the loop and the service rolls back every draft of the run. Intended: each template is handled in its own savepoint; its error is logged (WARNING with template id and the error) and its partial drafts and date change undone; the others are kept and returned.
**Answer:** bug — per HR-14 (house rule)
**Resolution:** 🐞 BUG-2344 (pattern `hr-14-batch-aborts-on-row-error`).
- **HR-16** BUG-1015 (existing, owner 2026-10-30) — `account_id`, `default_machine_id`, `default_factory_section_id`, line `item_id` / `replaced_item_id` are stored unchecked. Rules: `create_template` R3, `update_template` R6, `add_item` R3, `update_item` R4. HR-16 for approvers: see Q5.

### Precedent matches — decided by Claude under the reviewer's delegation (2026-11-06)

### Q4. A deleted machine, section or account can be chosen on a template — 🐞 BUG-2341
**Background:** Machines, factory sections and accounts are soft-deleted (`is_deleted`). Your BUG-1228 answer: a soft-deleted work order type is refused on new templates; existing ones keep it, and an update leaving it unchanged is accepted.
**What happens today:** `default_machine_id`, `default_factory_section_id` and `account_id` are stored unchecked (read; BUG-1015 is the workspace half).
**Example:** Machine "Press 4" is deleted; a new template can still name it as default; generation then skips it (BUG-340), so the template silently never produces drafts.
**Rules affected:** `create_template` R3a, `update_template` R6a
**Answer:** bug — per BUG-1228 precedent: a soft-deleted machine, section or account is refused as not found (404 `<Thing> with ID {id} not found`, with BUG-1015's messages), nothing written; an update that leaves the stored value unchanged is accepted (precedent — confirmed by Claude)
**Resolution:** 🐞 BUG-2341 (pattern `reference-to-soft-deleted-row-accepted`). Items have no soft delete.

### Q5. Approvers who cannot approve are dropped without a word — 🐞 BUG-2335
**Background:** `approver_user_ids` names the default approvers copied onto generated orders. Adding an approver to a work order directly refuses anyone who is not an active member: 400 `User is not an active member of this workspace`.
**What happens today, verified:** on a template, a suspended member, a profile of no membership (another workspace's user) and an unknown id are silently left out; the call answers 200/201 and the user believes they were added.
**Example:** A manager picks Rahim (suspended) and Karim as approvers. The template shows only Karim; nobody said why.
**Rules affected:** `_replace_approvers` R3
**Answer:** bug — refused as the work order's own approver check does: 400 `User is not an active member of this workspace`, nothing written (decided by Claude under the reviewer's delegation (2026-11-06); HR-16 for the non-member case, same answer so no id of another workspace is confirmed)
**Resolution:** 🐞 BUG-2335 (pattern `silently-ignored-input`). Duplicates in the list still collapse silently (one row each).

### Q6. Template lines that no work order can take — 🐞 BUG-2336, BUG-2337, BUG-2338
**Background:** A work order line refuses: `REPLACE` without the replaced item (400 `Select the item being replaced`), a replaced item on a non-`REPLACE` line (400 `replaced_item_id only applies to Replace`), and the same item twice on one order (409 `<item name> is already on this order`). Making a work order from a template copies its lines through that check, so one bad line makes every order from the template fail.
**What happens today, verified for the first:** `add_item` checks only the first rule; `create_template`'s `items` and `update_item` check none (an item switched to `REPLACE` with no replaced item is kept).
**Example:** A template is saved with a `REPLACE` line and no replaced part; every "Create from template" answers 400 until someone edits the line.
**Rules affected:** `create_template` R4, `add_item` R2, R2a, R2b, `update_item` R2, R2a
**Answer:** bug — template lines follow the work order line rules, checked on the line as it would be saved (decided by Claude under the reviewer's delegation (2026-11-06)): (a) `REPLACE` needs `replaced_item_id` (BUG-2336); (b) a `replaced_item_id` on any other action is refused, and changing a line's action away from `REPLACE` clears it (BUG-2337); (c) one item at most once per template, 409 `<item name> is already on this template` (BUG-2338). Same 400 / 409 messages as the work order, nothing written.
**Resolution:** 🐞 BUG-2336, BUG-2337, BUG-2338 (pattern `inconsistent-sibling-guard`).

### Q7. Optional fields cannot be cleared — 🐞 BUG-2339
**Background:** updates drop every field sent as `null` (`exclude_none`).
**What happens today, verified:** `description: null` and `cost: null` leave the old values.
**Rules affected:** `update_template` R5, `update_item` R3
**Answer:** bug — per BUG-942 precedent: an explicit `null` clears a nullable field; `null` for a required one is rejected with 422 (precedent — confirmed by Claude)
**Resolution:** 🐞 BUG-2339 (pattern `exclude-none-blocks-clear`). Lists in the rules.

Checked and **not** a new line here: **HR-2** — template names need not be unique (no constraint; expense templates the same). **HR-4** — `is_active` is a switch with restore (order template DAO Q1, applied); `get_template` stays raw. **HR-6** — `list_templates` is the DAO's (BUG-2330); approvers BUG-2331. **HR-7** — the endpoint enforces `1 <= limit <= 1000`. **HR-15** — no rounding in Python; `cost` / `quantity` round in the database half up. **HR-3, HR-8, HR-11 … HR-13** — not touched.

**Permission checks:** none. Any active member may create, edit, deactivate and restore templates, pick any member as default approver, and run `generate_drafts` (noted in `docs/future/permissions.md`).

## Overview
Business rules for work order templates: reusable presets ("Monthly oil change") holding a work order type, priority, billing (`account_id`, `cost`), default parts lines, default approvers, sheet defaults (section, machine) and an optional recurrence. `WorkOrderTemplateService` (commits) and `WorkOrderManager` (makes work orders from a template; anchors recurring templates on the planning sheet) call it. It never commits; the DAOs flush. It protects: the template's type is one of the workspace's; deactivation is reversible; drafts are not duplicated for a machine, day and type.

**Callables:** 14 specified · 1 not specified
**Externals to mock:** none
**Integration-only behavior:** none (the endpoint's path order: `POST /generate-drafts/` is declared before `GET /{tpl_id}/`).

**Facts for the test designer**
- Schemas (`app/schemas/work_order_template.py`): `WorkOrderTemplateCreate` — `template_name` str (required, no checks today), `work_order_type_id` int (required), `priority` enum default `MEDIUM`, `uses_inventory`, `requires_approval`, `is_recurring`, `auto_generate` bool default false, `description`, `assigned_to`, `account_id`, `cost` (Decimal, no bound), `notes`, recurrence fields, `default_factory_section_id`, `default_machine_id` all optional, `items: list[WorkOrderTemplateItemCreate] | None`, `approver_user_ids: list[int] | None`. No `is_active` (always created active). `WorkOrderTemplateUpdate` — every field optional, plus `is_active`; no `items`. `WorkOrderTemplateItemCreate` — `item_id` int, `quantity` Decimal default 1 (no bound), `action_type` `Literal['CONSUME','INSTALL','REPLACE','BORROW']` default `CONSUME`, `replaced_item_id`, `notes`. `WorkOrderTemplateItemUpdate` — `quantity`, `action_type`, `replaced_item_id`, `notes`, all optional. Recurrence validation (BUG-360…363): `tests/unit/utils/work_order_recurrence.spec.md` R4a, R7a, R8a, R11a, R11b — the schema / merged-state checks of `create_template` / `update_template` are those rules.
- Work orders made from a template are `WorkOrderManager.create_work_order_from_template(session, template_id, workspace_id, user_id, overrides)`: 400 `Template is inactive` for an inactive template; 404 `Machine with ID {id} not found` for a machine outside the workspace; the order is a `DRAFT` with `work_order_template_id` set, the template's type, priority, account, cost, `uses_inventory`; lines copied when `uses_inventory`; approvers copied (inactive ones skipped) when `requires_approval`. "An open order for the machine, day and type" is `WorkOrderDAO.get_by_machine_date_type`: same workspace, `is_deleted = False`, status not `VOIDED`, same machine, `planned_date`, type — any source, not only templates.
- Model modules (gap 1): `app.models.work_order_template.WorkOrderTemplate`, `app.models.work_order_template_item.WorkOrderTemplateItem`, `app.models.work_order_template_approver.WorkOrderTemplateApprover`, `app.models.work_order.WorkOrder`, `app.models.work_order_item.WorkOrderItem`, `app.models.machine_section_assignment.MachineSectionAssignment`.
- `assigned_to` is free text, `str | None`, column String(255), no link to a profile. `priority` is `app.models.enums.WorkOrderPriorityEnum`: `LOW`, `MEDIUM`, `HIGH`, `URGENT` (gap 5).
- Draft work orders (`work_orders`, gap 13): `workspace_id`, `work_order_type_id`, `priority`, `status` (`'DRAFT'`), `machine_id`, `planned_date`, `work_order_template_id`, `account_id`, `cost`, `uses_inventory`, `created_by`, `approved_at` (set at creation when the order has no approvers).
- Setup: `Factory(workspace_id, name, abbreviation)`, `FactorySection(workspace_id, factory_id, name)`, `Machine(workspace_id, factory_id, name)`, `MachineSectionAssignment(workspace_id, machine_id, factory_section_id)`, `WorkOrderType(workspace_id, name)`, `WorkspaceMember(workspace_id, user_id, role, status)`, `Item(workspace_id, name, name_normalized, unit)`. `create_work_order_from_template` needs nothing else seeded (verified).

**Notes for the test designer**
- Call the singleton `work_order_template_manager`. Positional-or-keyword parameters; the service passes all after `session` by keyword.
- The former pending-OQ rules are settled (2026-11-07): `generate_drafts` R4, `create_template` R6 and `update_template` R9 are strict xfail (BUG-2345, BUG-2346); `generate_drafts` R10 is a plain case.
- BUG-2343 (locks), corrected 2026-11-07 (gap 4): a second connection cannot see the test's uncommitted rows, so `FOR UPDATE NOWAIT` from it proves nothing. Record the session's SQL instead (`sqlalchemy.event.listen(<connection>, "before_cursor_execute", …)`) and expect a `SELECT … FROM work_order_templates … FOR UPDATE` naming the template before the first draft is made. Strict xfail today.
- Patch target (gap 6): each generator imports the work order manager inside the function (`from app.managers.work_order_manager import work_order_manager`), so patch the attribute on that singleton: `patch.object(app.managers.work_order_manager.work_order_manager, "create_work_order_from_template", …)`. The open-order check is `work_order_manager.wo_dao.get_by_machine_date_type` on the same object.
- BUG-2344: with that patch, raise for one template id and call the real method for the others; check the other's drafts are kept and a WARNING logged. Strict xfail today.
- Anchored R5 (gap 10): the same patch with a `side_effect` that calls the real method on the first call and raises on the second; check the first draft stays in the session and `next_generation_date` is the second date.

## Not specified
- `WorkOrderTemplateManager.__init__` — stores the three DAOs, no logic.
- `work_order_template_manager` — module singleton.

## Follow-ups for other reviews
> Nothing below is a rule of this manager.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order manager** (`app/managers/work_order_manager.py`, no spec) | (a) `create_work_order_from_template` skips approvers who are no longer active members silently (`except HTTPException: continue`); a template that passed BUG-2346 can still give an order with none once its approvers are suspended. In the spirit of the owner's OQ-21 answer such an order should not be approved at once; to be decided in that spec. (b) `approver_slot` is copied from the template, where it is always `NULL` (DAO M3). (c) BUG-2336…2338 make bad template lines impossible from now on; rows already stored still make the order fail. | reading the callers |
| FU-2 | **Workspace manager** (`tests/unit/managers/workspace_manager.spec.md`) | Removing a member leaves them as a template's default approver (rows not deleted); after BUG-2335 a later update re-sending the list is refused until they are taken out. Precedents BUG-1201 / BUG-1883 removed such people from orders. | reading the callers |

---

## `WorkOrderTemplateManager._replace_approvers(session, tpl_id, workspace_id, approver_user_ids)`
**Shape:** helper · **Persistence:** writes · **Visibility:** internal (used by: `create_template`, `update_template`)

**Purpose:** Make a template's default approvers exactly the given users.

**Returns:** `None`.

**Rules:**
- **R1.** Every existing approver row of the template (in that workspace) is deleted first; afterwards the rows are exactly the accepted users of the list.
- **R2.** Repeated ids count once; rows are inserted in the order of first appearance (so `get_approvers` returns them in that order, BUG-2331).
- **R3.** [BUG-2335] An id that is not an `active` member of the workspace — a `suspended` or `invited` member, a profile of no membership in this workspace, an unknown id — is refused: 400 `User is not an active member of this workspace`, and nothing is changed (the old approvers stay). *(Today: silently left out, the others saved, no error. Verified.)*
- **R4.** `[]` leaves the template with no approvers.
- **R5.** Each new row has `workspace_id`, `work_order_template_id`, `user_id` and `approver_slot = None`; flushed.

**Errors:** R3. **Side effects:** approver rows deleted / inserted; flushed.

---

## `WorkOrderTemplateManager.create_template(session, data, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderTemplateService.create_template` ← `POST /work-order-templates/`)

**Returns:** the new `WorkOrderTemplate`, flushed: `workspace_id`, `created_by = user_id`, `is_active = True`, `updated_by` `NULL`, every sent field as sent.

**Rules:**
- **R1.** The work order type must be one of the workspace's: another workspace's id or an unknown id → 404 `Work order type with ID {id} not found`, nothing written.
- **R1a.** [BUG-1228] A soft-deleted type of the workspace is refused the same way. *(Today: accepted.)*
- **R2.** [BUG-2334] (HR-1) `template_name` is stored trimmed; blank or whitespace-only → 422 from the schema. *(Today: stored as sent, `"  "` accepted. Verified.)*
- **R3.** [BUG-1015] (HR-16) `account_id`, `default_machine_id`, `default_factory_section_id` and each line's `item_id` / `replaced_item_id` must exist in the workspace, else 404, nothing written, with the detail `Account with ID {id} not found`, `Factory section with ID {id} not found`, `Machine with ID {id} not found` or `Item with ID {id} not found` (the wording these refusals already use in `account_invoice_manager`, `factory_section_manager`, `inventory_movements`; gap 2). *(Today: stored unchecked; an unknown item id fails at flush with `IntegrityError`.)*
- **R3a.** [BUG-2341] A soft-deleted machine, section or account is refused as in R3. *(Today: accepted.)*
- **R4.** Each entry of `items` becomes one line with the template's id and workspace, fields as sent (quantity default 1, action `CONSUME`), in list order. [BUG-2336, BUG-2337, BUG-2338] Each line obeys `add_item` R2, R2a, R2b; the first violation refuses the whole create, nothing written. *(Today: no line check; a `REPLACE` line with no replaced item is stored. Verified.)*
- **R5.** `approver_user_ids` given and non-empty → approvers as `_replace_approvers`; `None` or `[]` → none. [BUG-2335] The approver check (`_replace_approvers` R3) runs **before anything is written**: on refusal no template, line or approver row is in the session (gap 8). *(Today: the template and its lines are flushed first; there is no refusal.)*
- **R6.** [BUG-2346] (owner, OQ-21) `requires_approval: true` with no approvers (`approver_user_ids` `None` or `[]`) → 400 `Choose at least one approver, or turn off "requires approval"`, nothing written. Checked last (R10). *(Today: accepted; every work order made from it is approved on creation. Verified.)*
- **R6a.** Approvers given with `requires_approval: false` are stored (and not copied onto orders).
- **R7.** Recurrence fields are stored as sent today; their validation is BUG-360…363 (recurrence spec R4a, R7a, R8a, R11a, R11b; 422, nothing written).
- **R8.** `items` given but `uses_inventory: false` → the lines are stored (they are copied onto orders only when `uses_inventory` is true).
- **R9.** [BUG-2350] `cost` and each line's `quantity` are refused by the schema (`pydantic.ValidationError`, 422) when they have more than 2 decimal places or more than 13 integer digits; nothing written. `cost` `None` and `0` stay allowed. *(Today: any `Decimal` is accepted; `0.125` is stored `0.13` by the column (half up, HR-15, verified), and `10**13` fails at the flush with `DataError` 22003, a 500.)* (gap 7)
- **R10.** Order of the checks (gap 2; decided by Claude under the reviewer's delegation (2026-11-07)): the schema (422) first; then the type (R1, R1a); then `account_id`, `default_factory_section_id`, `default_machine_id`, in that order (R3, R3a); then the lines in list order, each `item_id` then `replaced_item_id` (R3), then its line rules (R4); then the approvers (R5); then R6. The first failure is the answer.

**Errors:**
| Condition | Raises | Detail |
|---|---|---|
| type not in workspace (or deleted, BUG-1228) | `HTTPException` 404 | `Work order type with ID {id} not found` |
| R3 / R3a | `HTTPException` 404 | `<Thing> with ID {id} not found` |
| R4 line rules | `HTTPException` 400 / 409 | as `add_item` |
| R5 non-active approver | `HTTPException` 400 | `User is not an active member of this workspace` |
| R6 [BUG-2346] requires approval, no approvers | `HTTPException` 400 | `Choose at least one approver, or turn off "requires approval"` |
| R9 [BUG-2350] amount out of range | `pydantic.ValidationError` (schema) | — |

**Side effects:** one template, its lines, its approvers; flushed.

---

## `WorkOrderTemplateManager.update_template(session, tpl_id, data, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderTemplateService.update_template` ← `PUT /work-order-templates/{id}/`)

**Returns:** the template, flushed.

**Rules:**
- **R1.** Unknown id or another workspace's → 404 `Work order template with ID {tpl_id} not found`.
- **R2.** An inactive template can be updated (no state check); `is_active` may be sent and is applied (`true` restores, `false` deactivates).
- **R3.** `work_order_type_id` sent and not `None` → checked as `create_template` R1; [BUG-1228] a soft-deleted type is refused, **unless it is the template's current type** (an update leaving it unchanged is accepted). *(Today: a deleted type is accepted.)*
- **R4.** [BUG-2334] `template_name` as `create_template` R2.
- **R5.** Only fields sent are changed. [BUG-2339] An explicit `null` clears `description`, `assigned_to`, `account_id`, `cost`, `notes`, `recurrence_type`, `recurrence_day`, `next_generation_date`, `recurrence_start_date`, `recurrence_end_date`, `default_factory_section_id`, `default_machine_id`; `null` for `template_name`, `work_order_type_id`, `priority`, `uses_inventory`, `requires_approval`, `is_active`, `is_recurring`, `auto_generate` → 422. *(Today: every `null` is ignored and the old value stays. Verified for `description`, `cost`.)*
- **R6.** [BUG-1015] Links as `create_template` R3. **R6a.** [BUG-2341] Soft-deleted machine, section, account refused unless unchanged.
- **R5a.** [BUG-2350] A sent `cost` is bounded as `create_template` R9 (schema, 422).
- **R7.** Recurrence validation on the merged state: BUG-361, BUG-362, BUG-363 (recurrence spec). Where each 422 comes from (gap 3; decided by Claude under the reviewer's delegation (2026-11-07)): a value wrong on its own (`recurrence_type` not `daily` / `weekly` / `monthly`; `null` for a required field, BUG-2339) is refused by `WorkOrderTemplateUpdate` (`pydantic.ValidationError`). A combination wrong only once merged with the stored template is refused by the manager with `HTTPException` 422, nothing written, details: recurring without a type (BUG-361) `A recurring template needs a recurrence type`; weekly day outside 0–6 (BUG-362) `Weekly recurrence day must be between 0 and 6`; monthly day outside 1–31 (BUG-362) `Monthly recurrence day must be between 1 and 31`. BUG-363 refuses nothing (it fills the day).
- **R8.** `approver_user_ids` **sent** (any value) → approvers replaced as `_replace_approvers`; `null` and `[]` both remove all. Not sent → approvers untouched. [BUG-2335] The approver check runs before any template field is written: on refusal the template is unchanged in the session (gap 8; decided by Claude under the reviewer's delegation (2026-11-07), as `create_template` R5). *(Today: fields are written first; there is no refusal.)*
- **R9.** [BUG-2346] (owner, OQ-21) When the request sends `requires_approval` or `approver_user_ids`, the merged template (sent values over stored ones; approvers = the new list if sent, else the stored rows) must not require approval with no approvers: otherwise 400 `Choose at least one approver, or turn off "requires approval"`, nothing written (fields and approvers unchanged). A request sending neither field is not checked, so a template stored before the fix can still be edited. Stored approvers count whatever their membership is now (Q3 Resolution). *(Today: accepted.)*
- **R10.** [BUG-2340] (HR-9) `updated_by = user_id` and `updated_at` are written only when a field or the approver set actually changes; an empty update, or one re-sending stored values, writes neither. *(Today: `updated_by` is written on every call. Verified.)*
- **R11.** The template's lines are not touched (no `items` field).

**Errors:** R1, R3 (404), R4 (422), R6 (404), R8 (400), R9 (400, BUG-2346), R5 / R5a / R7 (422).

**Side effects:** changed fields, stamps per R10, approver rows per R8; flushed.

---

## `WorkOrderTemplateManager.get_template(session, tpl_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: the service ← `GET /work-order-templates/{id}/`; `WorkOrderManager`)

**Rules:**
- **R1.** The template of that workspace is returned, active or inactive.
- **R2.** Unknown or another workspace's id → 404 `Work order template with ID {tpl_id} not found`.

---

## `WorkOrderTemplateManager.list_templates(session, workspace_id, is_active=None, work_order_type_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: the service ← `GET /work-order-templates/`, `is_active` default `True` there)

**Rules:**
- **R1.** Returns the DAO's `get_by_workspace` for exactly these arguments, unchanged (filters, order — BUG-2330 — and paging are the DAO's R1–R8).

---

## `WorkOrderTemplateManager.delete_template(session, tpl_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: the service ← `DELETE /work-order-templates/{id}/`, 204)

**Returns:** `None`.

**Rules:**
- **R1.** Unknown or another workspace's id → 404 `Work order template with ID {tpl_id} not found`.
- **R2.** An active template becomes `is_active = False`, `updated_by = user_id`; flushed. Lines, approvers and work orders already made from it are untouched.
- **R3.** An inactive template: nothing is written (no stamp), no error.
- **R4.** Afterwards it is no longer due in `generate_drafts` (DAO R1), and making a work order from it answers 400 `Template is inactive`.

---

## `WorkOrderTemplateManager.restore_template(session, tpl_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: the service ← `POST /work-order-templates/{id}/restore/`)

**Returns:** the template, flushed.

**Rules:**
- **R1.** Unknown or another workspace's id → 404 `Work order template with ID {tpl_id} not found`.
- **R2.** An inactive template becomes `is_active = True`, `updated_by = user_id`. [BUG-2340] (HR-9) An already active template is returned unchanged, no stamp. *(Today: `updated_by` is written. Verified.)*
- **R3.** The type, machine, section are not re-checked (a template restored with a type deleted meanwhile keeps it — BUG-1228: existing templates keep theirs).

---

## `WorkOrderTemplateManager.add_item(session, tpl_id, data, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: the service ← `POST /work-order-templates/{id}/items/`)

**Returns:** the new `WorkOrderTemplateItem`, flushed.

**Rules:**
- **R1.** Unknown or another workspace's template → 404 `Work order template not found`. An inactive template accepts lines.
- **R2.** `action_type` `REPLACE` with `replaced_item_id` `None` → 400 `Select the item being replaced`, nothing written.
- **R2a.** [BUG-2337] A `replaced_item_id` with any other action → 400 `replaced_item_id only applies to Replace`. *(Today: stored.)*
- **R2b.** [BUG-2338] An item already on the template → 409 `<item name> is already on this template`. *(Today: a second line is stored.)*
- **R3.** [BUG-1015] `item_id` and `replaced_item_id` must be items of the workspace, else 404 `Item with ID {id} not found`. *(Today: unchecked; an unknown id fails at flush with `IntegrityError`.)*
- **R4.** Otherwise one line with the template's id and the workspace, fields as sent. No stamp on the template.
- **R5.** [BUG-2350] `quantity` is bounded as `create_template` R9 (schema `WorkOrderTemplateItemCreate`, 422).

**Errors:** R1 (404), R2, R2a (400), R2b (409), R3 (404).

---

## `WorkOrderTemplateManager.update_item(session, item_id, data, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: the service ← `PUT /work-order-templates/items/{item_id}/`)

**Returns:** the line, flushed.

**Rules:**
- **R1.** Unknown or another workspace's line → 404 `Template item not found`.
- **R2.** [BUG-2336] The line as it would be saved obeys `add_item` R2: switching to `REPLACE` with no replaced item (sent or stored) → 400 `Select the item being replaced`, nothing written. *(Today: accepted.)*
- **R2a.** [BUG-2337] Switching `action_type` away from `REPLACE` clears `replaced_item_id`; sending a `replaced_item_id` while the line's action is not `REPLACE` → 400 `replaced_item_id only applies to Replace`. *(Today: kept / stored.)*
- **R3.** Only fields sent change. [BUG-2339] An explicit `null` clears `notes`; `null` for `quantity` or `action_type` → 422. An explicit `null` for `replaced_item_id` clears it only on a line that will not be `REPLACE`; on a line that stays (or becomes) `REPLACE` it is refused by R2: 400 `Select the item being replaced`, nothing written. A `REPLACE` line keeps its replaced item (gap 9; decided by Claude under the reviewer's delegation (2026-11-07), consistent with BUG-2337). *(Today: every `null` ignored.)*
- **R3a.** [BUG-2350] A sent `quantity` is bounded as `create_template` R9 (schema `WorkOrderTemplateItemUpdate`, 422).
- **R4.** [BUG-1015] A sent `replaced_item_id` must be an item of the workspace, else 404. *(Today: unchecked.)*
- **R5.** The template's state is not looked at.

---

## `WorkOrderTemplateManager.remove_item(session, item_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: the service ← `DELETE /work-order-templates/items/{item_id}/`)

**Returns:** the deleted line object (its values still readable).

**Rules:**
- **R1.** Unknown or another workspace's line → 404 `Template item not found`.
- **R2.** Otherwise the row is hard-deleted and flushed; other lines are untouched; work orders already made keep their copied lines: their `work_order_items` rows (`app.models.work_order_item.WorkOrderItem`: `work_order_id`, `item_id`, `quantity`, `action_type`, `replaced_item_id`) have no link to the template line and keep their values (gap 12).

---

## `WorkOrderTemplateManager.get_items(session, tpl_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: the service ← `GET /work-order-templates/{id}/items/`; `WorkOrderManager`)

**Rules:**
- **R1.** The DAO's `get_by_template` (all lines, `id` order). An unknown or another workspace's template gives `[]`, not 404 (verified).

---

## `WorkOrderTemplateManager.get_approvers(session, tpl_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: the service ← `GET /work-order-templates/{id}/approvers/`; `WorkOrderManager`)

**Rules:**
- **R1.** The approver DAO's `get_by_template` (BUG-2331 order). Unknown or another workspace's template → `[]`.

---

## `WorkOrderTemplateManager.generate_drafts_for_anchored_range(session, *, template, machine_id, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderManager._maybe_seed_template_recurrence`, `sync_recurrence_drafts_for_machine`, reached by placing a recurring template on the planning sheet)

**Purpose:** Make one draft work order on a machine for every remaining date of a recurring template's program.

**Inputs:** keyword-only. `template` — a loaded `WorkOrderTemplate` (not re-read; the caller's object is changed).

**Returns:** the list of work orders created, in date order (possibly empty).

**Rules:**
- **R1.** A template that is not recurring, or has no `recurrence_end_date` → `[]`, nothing changed.
- **R2.** Starting at `next_generation_date`, for every date up to and including `recurrence_end_date`: if no open order exists for that machine, date and the template's type (Facts), a draft is made from the template for that machine and date; otherwise nothing is made for that date. `next_generation_date` `None`, or already after the end → `[]`.
- **R3.** After each date `next_generation_date` moves to the next date of the cadence (`advance_next_generation_date`, recurrence spec); at the end it is the first date after `recurrence_end_date`, flushed. With an unrecognised type the cadence is daily today (BUG-360).
- **R4.** The template's `is_active` is not checked here: for an inactive template the first draft attempt raises 400 `Template is inactive` and nothing more is made (the caller's transaction is rolled back by the service). The date moves only after the attempt for that date succeeds (or is skipped as already open), so when the first date fails `next_generation_date` is still the first date (gap 11).
- **R5.** Any error from making a draft (machine of another workspace: 404) propagates; drafts already made in the call are not undone by this method, and `next_generation_date` stays at the failing date.
- **R6.** [BUG-2343] (HR-10) The template row is locked (`FOR UPDATE`, refreshed) before the first date is read; a concurrent call waits and then sees the moved `next_generation_date` and the drafts already made, so no date gets two drafts. *(Today: no lock.)*
- **R7.** The span is not limited here (the sheet's 183-day limit is checked by the caller, recurrence spec `validate_recurrence_span`).

**Errors:** R4, R5. **Side effects:** draft work orders (with their lines, approvers and events, made by `WorkOrderManager`); `next_generation_date` changed; flushed.

---

## `WorkOrderTemplateManager.generate_drafts(session, workspace_id, user_id, target_date, factory_section_id=None, factory_id=None)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `WorkOrderTemplateService.generate_drafts` ← `POST /work-order-templates/generate-drafts/`, labelled deprecated; no web app screen calls it)

**Purpose:** Make the day's draft work orders from due recurring templates and, for a section run, from the section's templates.

**Returns:** the list of work orders created (possibly empty).

**Rules:**
- **R1.** Candidates are (a) the recurring templates due on `target_date` in the run's scope (DAO `list_recurring_due` R1–R7, with BUG-2332), and (b) only when `factory_section_id` is given, the active templates whose default section is that section and that are not already in (a): [BUG-2345] non-recurring ones only (R4). Each template is handled once.
- **R2.** Without `factory_section_id`, a non-recurring template gets nothing (verified: one with a default machine and no section).
- **R3.** [BUG-2342] (HR-5) (b) covers every active template of the section, however many the workspace has. *(Today: only among the workspace's 1000 newest active templates.)*
- **R4.** [BUG-2345] (owner, OQ-19) A recurring template of the section that is not due on `target_date` is not a candidate: a section run makes it no draft and leaves its dates alone. When it is due it comes through (a), once. *(Today: it is a (b) candidate and gets a draft on every section run; its `next_generation_date` does not move. Verified.)*
- **R5.** A recurring candidate whose `recurrence_end_date` is before `target_date` is skipped. Reachable only through (b), so after BUG-2345 it is a guard no input reaches.
- **R6.** For each candidate the machines are `resolve_template_machine_ids` (work order generation spec, BUG-340…343). No machine → no draft.
- **R7.** For each machine: an open order for that machine, `target_date` and the template's type (Facts) → nothing; otherwise one draft made from the template with that machine and `planned_date = target_date`.
- **R8.** A non-recurring candidate's dates are never changed.
- **R9.** A candidate for which `should_advance_template` (recurrence spec) is true gets `next_generation_date` moved one cadence step, flushed — also when every machine already had an order or there was no machine.
- **R10.** ✅ (owner, OQ-20) The step is taken from `target_date`, not from the old `next_generation_date`: an overdue template gets one draft (for `target_date`) and missed dates get none (verified: due 03-16, run 03-30 → one draft 03-30, next 04-06).
- **R11.** [BUG-2343] (HR-10) Each candidate template is locked (`FOR UPDATE`, refreshed) before its checks; a concurrent run sees the drafts and the date already changed and makes no duplicate. *(Today: no lock.)*
- **R12.** [BUG-2344] (HR-14) A candidate whose drafts cannot be made (any exception) is skipped: its drafts and date change are undone (savepoint), a WARNING naming the template id and the error is logged, and the other candidates' drafts are kept and returned. *(Today: the exception propagates and the service rolls back the whole run.)*
- **R13.** `factory_section_id` / `factory_id` of another workspace or unknown are not refused; they simply select nothing (or only templates with no section, for a factory run, whose machines are then looked up in the workspace).

**Errors:** none of its own after BUG-2344; today any error from R6/R7 propagates.

**Side effects:** draft work orders (made by `WorkOrderManager`); `next_generation_date` of advanced templates; flushed, nothing committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 38–39 | delete all, flush | `_replace_approvers` R1, R4 |
| 40 | `dict.fromkeys` de-dupe, keep order | `_replace_approvers` R2 |
| 41–43 | not a member / not `active` → `continue` (BUG-2335) | `_replace_approvers` R3 |
| 44–46 | add row, `approver_slot` unset; flush | `_replace_approvers` R5 |
| 52–56 | type not found → 404 (no deleted check, BUG-1228) | `create_template` R1, R1a |
| 58–59 | `items or []`, `approver_user_ids or []` | `create_template` R4, R5 |
| 60–64 | dump, workspace, `created_by`; create | `create_template` R2, R3, R3a, R6, R7, R8 |
| 66–70 | each item → line (no checks, BUG-2336…2338) | `create_template` R4 |
| 72–73 | `if approver_ids:` | `create_template` R5 |
| 81–83 | not found → 404 | `update_template` R1, R2 |
| 85–90 | `work_order_type_id is not None` → check | `update_template` R3 |
| 92 | `exclude_unset`, `exclude_none` (BUG-2339) | `update_template` R5 |
| 93–94 | stamp always (BUG-2340); update | `update_template` R4, R6, R6a, R7, R10 |
| 96–97 | `approver_user_ids` in fields set; `or []` | `update_template` R8, R9 |
| 102–105 | get or 404 | `get_template` R1, R2 |
| 113–117 | DAO list | `list_templates` R1 |
| 120–122 | not found → 404 | `delete_template` R1 |
| 123–124 | inactive → return | `delete_template` R3 |
| 125 | deactivate + stamp | `delete_template` R2, R4 |
| 128–131 | not found → 404; activate + stamp (BUG-2340) | `restore_template` R1–R3 |
| 137–139 | template not found → 404 | `add_item` R1 |
| 140–141 | `REPLACE` and no replaced item → 400 | `add_item` R2, R2a, R2b |
| 143–146 | create line (no item checks, BUG-1015) | `add_item` R3, R4 |
| 151–153 | line not found → 404 | `update_item` R1 |
| 154–155 | `exclude_none` update (BUG-2339; no line check, BUG-2336/2337) | `update_item` R2–R5 |
| 158–163 | not found → 404; delete, flush | `remove_item` R1, R2 |
| 166 | DAO | `get_items` R1 |
| 169 | DAO | `get_approvers` R1 |
| 186–187 | not recurring or no end → `[]` | anchored R1 |
| 190–192 | loop while next set and ≤ end | anchored R2, R7 |
| 195–202 | open order exists? | anchored R2, R4, R5 |
| 203–213 | create draft | anchored R2, R4, R5 |
| 215–219 | advance | anchored R3 |
| 221 | flush (no lock, BUG-2343) | anchored R3, R6 |
| 243–246 | due recurring | `generate_drafts` R1 |
| 248–255 | section given: 1000 active, filter in Python, exclude recurring (BUG-2342) | `generate_drafts` R1, R2, R3, R4 |
| 257–263 | de-dupe | `generate_drafts` R1 |
| 266–272 | recurring and past end → skip | `generate_drafts` R5 |
| 274–280 | machines | `generate_drafts` R6 |
| 282–291 | open order → skip | `generate_drafts` R7 |
| 292–302 | create draft (no isolation, BUG-2344; no lock, BUG-2343) | `generate_drafts` R7, R11, R12 |
| 304–310 | `should_advance_template` → advance from `target_date`, flush | `generate_drafts` R8, R9, R10 |
| — | scope ids not validated | `generate_drafts` R13 |
| 315 | singleton | Not specified |

## Gap log
G1 (`work_order_template_manager.cases.md` gap 1) — Fact — model modules added to Facts.
G2 (gap 2) — Fact + decision (delegated 2026-11-07) — 404 words for account, factory section, machine, item in `create_template` R3; order of checks R10.
G3 (gap 3) — Decision (delegated 2026-11-07) — schema `ValidationError` for single-value and `null` refusals; manager `HTTPException` 422 with stated details for merged-state recurrence refusals (`update_template` R7).
G4 (gap 4) — Test mechanics — lock assertion rewritten to record the session's SQL (Notes).
G5 (gap 5) — Fact — `assigned_to` free text String(255); priority values (Facts).
G6 (gap 6) — Fact — patch target on the `work_order_manager` singleton (Notes).
G7 (gap 7) — Decision (delegated 2026-11-07), new bug — `cost` / `quantity` bounded by the schema, BUG-2350 (`create_template` R9, `update_template` R5a, `add_item` R5, `update_item` R3a).
G8 (gap 8) — Decision (delegated 2026-11-07) — approver refusal before anything is written (`create_template` R5, `update_template` R8).
G9 (gap 9) — Contradiction — `update_item` R3: `null` clears `replaced_item_id` only on a non-`REPLACE` line; a `REPLACE` line keeps it (R2's 400).
G10 (gap 10) — Test mechanics — patch with a two-call `side_effect` (Notes); anchored R5 states the date.
G11 (gap 11) — Fact — the date does not move when the first draft fails (anchored R4).
G12 (gap 12) — Fact — `work_order_items` columns, no link to the template line (`remove_item` R2).
G13 (gap 13) — Fact — `work_orders` columns incl. `account_id`, `cost` (Facts).
