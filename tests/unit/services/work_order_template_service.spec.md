# Spec — `app/services/work_order_template_service.py`

> **Status:** APPROVED (2026-11-07; nothing open). The manager's OWNER questions OQ-19, OQ-20, OQ-21 were answered on 2026-11-07 (manager spec: BUG-2345, R10 ✅, BUG-2346); they reach this service only as pass-through.
> **Source commit:** e48a092

> **Revision 2026-11-07 (owner's answers to OQ-19 … OQ-21 reached through the manager; fill-gaps of `work_order_template_service.cases.md` gaps 1–2).** One pass-through rule added per answered bug (`create_template` R2a, BUG-2346; `generate_drafts` R1a, BUG-2345). Facts added: model modules, draft work order columns. No rule renumbered; no new bug of the service's own.

> **Form.** As `tests/unit/services/work_order_type_service.spec.md`: this spec covers what the service adds. The **Transaction contract TC1–TC6 is defined in `tests/unit/services/base_service.spec.md`** and cited here. The manager's rules are in `tests/unit/managers/work_order_template_manager.spec.md` (written alongside) and appear here only as values that must pass through unchanged.
>
> **Verified by running** (`v2.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tpl\A\`, one outer transaction rolled back against `marker_test`, session as the `db` fixture; nothing persisted): create returns the template with `created_at` loaded and `updated_at` `None`; `remove_item` returns the deleted line with `id` and `quantity` still readable after the commit; `delete_template` returns `None` and a later `get_template` shows `is_active = False`; `get_items` / `get_approvers` of an unknown template return `[]`; update loads `updated_at`; an update to an unknown type passes the manager's 404 `Work order type with ID 999999999 not found`; `generate_drafts` with nothing due returns `[]`. **Not run:** HTTP; TC4 / TC5 patching (the code is the department service's pattern line for line).

## Review
> No questions.

No house-rule violation of the service's own. Reached through the manager and cited, each with one pass-through case: BUG-1228, BUG-2334, BUG-2335, BUG-2340 (create / update), BUG-2344 (`generate_drafts`). All other template bugs are the manager's or the DAO's.

Checked and **not** violated here: **HR-7** — `GET /work-order-templates/` enforces `1 <= limit <= 1000`, `skip >= 0`. **HR-10** — locking is the manager's (BUG-2343). **HR-14** — isolation per template is the manager's (BUG-2344); the service commits once, after the whole run. **HR-1 … HR-6, HR-8, HR-9, HR-15, HR-16** — the manager's / DAO's.

**Permission checks:** none; any active member may use every method (`docs/future/permissions.md`).

## Overview
`WorkOrderTemplateService` is the transaction boundary for `/work-order-templates/`. Each write calls `WorkOrderTemplateManager`, commits, re-reads and returns, rolling back and re-raising on any error; reads call the manager and return. It adds no check, translation or shaping.

**Callables:** 12 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** the endpoints' response shaping (`GET …/approvers/` adds `user_name` from the profile; DELETE endpoints answer 204 with no body).

**Facts for the test designer**
- Import: `from app.services.work_order_template_service import WorkOrderTemplateService, work_order_template_service`; the manager is the attribute `manager`. Schemas as the manager spec's Facts; `GenerateWorkOrderDraftsRequest(target_date: date, factory_section_id: int | None = None, factory_id: int | None = None)`.
- Setup and the manager's refusals: manager spec, Facts and Errors.
- Model modules (gap 1): `app.models.work_order_template.WorkOrderTemplate`, `app.models.work_order_template_item.WorkOrderTemplateItem`, `app.models.work_order_template_approver.WorkOrderTemplateApprover`, `app.models.machine_section_assignment.MachineSectionAssignment`, `app.models.work_order.WorkOrder` (the `app.models.<snake_case name>` convention holds for all four).
- Draft work order columns (gap 2): `workspace_id`, `work_order_type_id`, `status` `'DRAFT'`, `machine_id`, `planned_date`, `work_order_template_id`, `created_by` (the caller), plus `priority`, `account_id`, `cost`, `uses_inventory` copied from the template (manager spec Facts).

**Notes for the test designer**
- Session, commits, TC4 / TC5 patching: as `base_service.spec.md` Notes.
- TC2, TC4, TC5: one case each on one write method (the pattern is identical in all of them); TC1 and TC3 one case per write method. `remove_item` and `delete_template` do not re-read (R below).
- Pass-through bug cases are strict xfail on the cited ID.

## Not specified
- `WorkOrderTemplateService.__init__` — stores the manager.
- `work_order_template_service` — module singleton.

---

## `WorkOrderTemplateService.create_template(db, tpl_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /work-order-templates/`)

**Returns:** the new template, committed and re-read (TC1, TC2).

**Rules:**
- **R1.** The manager's `create_template` with these arguments; its lines and approvers are committed with it (TC1); the template returned re-read (TC2).
- **R2.** The manager's refusals (404 type, 400 line / approver rules, 409 duplicate line, 404 links) reach the caller unchanged and nothing is saved — no template, no line, no approver (TC3). Pass-through: BUG-1228 (deleted type), BUG-2335 (non-active approver).
- **R2a.** [BUG-2346] (pass-through; owner, OQ-21) `requires_approval: true` with no approvers → the manager's 400 `Choose at least one approver, or turn off "requires approval"` reaches the caller and nothing is saved (TC3). The same holds for `update_template` (manager R9). *(Today: created.)*
- **R3.** Commit / re-read failures: TC4, TC5.

---

## `WorkOrderTemplateService.update_template(db, tpl_id, tpl_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /work-order-templates/{id}/`)

**Returns:** the template, committed and re-read (`updated_at` loaded).

**Rules:**
- **R1.** The manager's `update_template`; committed (TC1); re-read (TC2).
- **R2.** Any refusal reaches the caller unchanged; nothing of the call is saved, **including the template fields already written before an approver refusal** (TC3; manager `update_template` R8).
- **R3.** Pass-through: BUG-2340 — an empty update leaves `updated_by` as it was.
- **R4.** TC4, TC5.

---

## `WorkOrderTemplateService.get_template(db, tpl_id, workspace_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /work-order-templates/{id}/`)

**Rules:**
- **R1.** The manager's result, active or inactive; its 404 unchanged.
- **R2.** Read only (TC6).

---

## `WorkOrderTemplateService.list_templates(db, workspace_id, is_active=None, work_order_type_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /work-order-templates/`, `is_active` default `True` at the endpoint)

**Rules:**
- **R1.** The manager's list for exactly these arguments, unchanged.
- **R2.** Read only (TC6).

---

## `WorkOrderTemplateService.delete_template(db, tpl_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `DELETE /work-order-templates/{id}/`, 204)

**Returns:** `None` (no re-read).

**Rules:**
- **R1.** The manager deactivates the template; committed (TC1). Deleting an inactive template commits nothing new and returns `None`.
- **R2.** The manager's 404 reaches the caller unchanged (TC3). Commit failure: TC4.

---

## `WorkOrderTemplateService.restore_template(db, tpl_id, workspace_id, user_id)`
**Shape:** state-transition · **Persistence:** writes · **Visibility:** public (used by: `POST /work-order-templates/{id}/restore/`)

**Returns:** the template, committed and re-read, `is_active = True`.

**Rules:**
- **R1.** The manager's `restore_template`; committed; re-read (TC1, TC2).
- **R2.** 404 unchanged (TC3); TC4, TC5.

---

## `WorkOrderTemplateService.add_item(db, tpl_id, item_in, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /work-order-templates/{id}/items/`)

**Returns:** the new line, committed and re-read.

**Rules:**
- **R1.** The manager's `add_item`; committed; re-read (TC1, TC2).
- **R2.** The manager's 404 / 400 (`Select the item being replaced`) / 409 unchanged; nothing saved (TC3). TC4, TC5.

---

## `WorkOrderTemplateService.update_item(db, item_id, item_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /work-order-templates/items/{item_id}/`)

**Rules:**
- **R1.** The manager's `update_item`; committed; returned re-read (TC1, TC2).
- **R2.** Refusals unchanged; nothing saved (TC3). TC4, TC5.

---

## `WorkOrderTemplateService.remove_item(db, item_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /work-order-templates/items/{item_id}/`, 204)

**Returns:** the deleted line object, **not** re-read; its values stay readable after the commit (verified).

**Rules:**
- **R1.** The line is deleted by the manager and the delete committed (TC1): a re-select finds nothing.
- **R2.** 404 `Template item not found` unchanged; nothing deleted (TC3). Commit failure: TC4.

---

## `WorkOrderTemplateService.get_items(db, tpl_id, workspace_id)` and `get_approvers(db, tpl_id, workspace_id)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET …/items/`, `GET …/approvers/`)

**Rules:**
- **R1.** The manager's lists, unchanged (unknown template → `[]`; approvers in BUG-2331 order).
- **R2.** Read only (TC6).

---

## `WorkOrderTemplateService.generate_drafts(db, body, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /work-order-templates/generate-drafts/`, 201, deprecated; no screen calls it)

**Returns:** the list of draft work orders, committed, **each** re-read.

**Rules:**
- **R1.** `body.target_date`, `body.factory_section_id`, `body.factory_id` are passed to the manager's `generate_drafts` with `workspace_id` and `user_id`; the drafts and the templates' moved dates are committed together (TC1).
- **R1a.** [BUG-2345] (pass-through; owner, OQ-19) A section run commits no draft for a recurring template of the section that is not due, and its `next_generation_date` is unchanged after the commit. *(Today: a draft is made and committed on every section run.)*
- **R2.** Every returned work order is re-read after the commit (TC2); an empty result returns `[]` and commits nothing new.
- **R3.** Any exception from the manager rolls back every draft and date change of the run and reaches the caller unchanged (TC3). [BUG-2344] (pass-through) after the fix a failing template no longer reaches here: the others are committed and returned. *(Today: the whole run is undone.)*
- **R4.** If the re-read of one work order raises, that exception reaches the caller and the run **stays committed** (TC5).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 31–35 | create: manager → commit → refresh → return | `create_template` R1 |
| 36–38 | create: exception → rollback, re-raise | `create_template` R2, R3 |
| 44–48 | update: manager → commit → refresh | `update_template` R1, R3 |
| 49–51 | update: exception | `update_template` R2, R4 |
| 54 | get | `get_template` R1, R2 |
| 62–66 | list | `list_templates` R1, R2 |
| 69–71 | delete: manager → commit, no refresh | `delete_template` R1 |
| 72–74 | delete: exception | `delete_template` R2 |
| 77–81 | restore: manager → commit → refresh | `restore_template` R1 |
| 82–84 | restore: exception | `restore_template` R2 |
| 90–94 / 95–97 | add item / exception | `add_item` R1, R2 |
| 102–106 / 107–109 | update item / exception | `update_item` R1, R2 |
| 112–115 / 116–118 | remove item: commit, no refresh / exception | `remove_item` R1, R2 |
| 121, 124 | reads | `get_items` / `get_approvers` R1, R2 |
| 130–137 | generate: manager → commit | `generate_drafts` R1 |
| 138–139 | refresh each (empty → none) | `generate_drafts` R2, R4 |
| 141–143 | generate: exception | `generate_drafts` R3 |
| `base_service.py` | commit / rollback helpers | TC1–TC6 |
| 146 | singleton | Not specified |

## Gap log
G1 (`work_order_template_service.cases.md` gap 1) — Fact — model modules (Facts).
G2 (gap 2) — Fact — draft work order column names (Facts).
