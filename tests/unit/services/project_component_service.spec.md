# Spec — `app/services/project_component_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. BUG-1196 is the owner's rule (2026-11-01), written here. Every other item was decided by Claude under the reviewer's delegation (2026-11-04) or is a house rule.)
> **Source commit:** e48a092

> **Revision 2026-11-05 (executor follow-up).** `delete_component` R5 split: attachment-link rows are now R5a, tagged BUG-2262 (logged by the executor). Stays APPROVED.

> **Revision 2026-11-04 (fill-gaps, `project_component_service.cases.md` gaps 1–5).** Model modules, blocker-table columns and date types added; `project_id` on update and the attachment-event comparison decided. No new bug, no question; stays APPROVED. See the Gap log.

> **Form.** As `tests/unit/services/department_service.spec.md`, with one difference: this class does **not** inherit `BaseService`. It calls `db.commit()`, `db.refresh()` and `db.rollback()` itself, so its transaction is written below as its own contract (**CT1–CT6**), stated against TC1–TC6 of `tests/unit/services/base_service.spec.md`. What the manager decides is **cited, not restated**: `tests/unit/managers/project_manager.spec.md` (`require_project_access`, `require_component_access`, `can_access_project`, `log_event`, `log_for_component`), `tests/unit/dao/project_component.spec.md`, `tests/unit/dao/base.spec.md`.
>
> **Routed here and written as rules:** BUG-1196 (owner, 2026-11-01: a component with history is refused, listing what blocks it; Resolution of Q1 in `tests/unit/dao/project_component_activity_event.spec.md`); BUG-1278 (deleted project) reached through the guard; project component DAO FU-1 (b)–(d) logged here as BUG-2277 … BUG-2279; BUG-1277 (endpoint `limit`) cited. BUG-1198 (a read of the component activity log, `GET /project-components/{id}/activity/`) adds a new method to this service; its rules are in the activity event DAO spec Q2 and the activity manager spec, and it is **not specified here** until it exists.
>
> **Standing decisions applied here (not asked again):** a refused delete lists what blocks it (owner, item manager Q2; BUG-1196). HR-16. Things of a soft-deleted parent are hidden (BUG-1278). OQ-18: a component of a private project the caller may not open answers 403 (manager `require_component_access` R3).
>
> **Verified by running** (`v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvc\forkA\`, one outer transaction rolled back against `marker_test`, session as the unit-test `db` fixture, private `COVERAGE_FILE`; nothing persisted): create with name `"  "` and budget `-5` stored as typed, `component_created` event written with `{"component_id", "component_name"}`; budget `1000.005` stored `1000.01`, `0.125` stored `0.13`; another workspace's project and an unknown project → 404 `Project with ID <id> not found`; a private project, `ground-team` caller → 403; create, get and update on a soft-deleted project succeed; `update` with `{}` writes a `component_updated` event; `description: null` leaves the old description; unknown id on update, get and delete → 404 `Project component not found` from the guard; `project_id=0` lists the whole workspace (10 of 10); the workspace-wide list for a `ground-team` caller made 31 statements for 10 components; delete with a task → `IntegrityError` (23502, the ORM nulls the task's link), component kept; a plain delete writes `component_deleted` and is committed; a failing `commit` → one rollback, nothing saved; a failing `refresh` → row saved; a read neither commits nor rolls back. **Read, not run:** the endpoints; the intended behaviour of the bugs.

## Review
> Nothing open. Overwrite a pre-filled answer only if the rule should not apply here.

### House-rule violations — applied automatically
- **HR-1** `create_component` R5, `update_component` R5 — `ProjectComponentCreate.name` / `ProjectComponentUpdate.name` are plain `str`: `"  "` is stored (verified). Intended: trimmed; blank refused by the schema (422).
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2272 (pattern `blank-name-accepted`). Fix in `app/schemas/project_component.py`. Rules: `create_component` R5, `update_component` R5.
- **HR-5** `get_components` R5 — without `project_id`, one page of the workspace's components is read and the ones the caller may not open are dropped afterwards, in Python, with two reads per component (31 statements for 10 components, verified). Pages come back short or empty though more visible components follow (DAO FU-1 (b), verified there: 3 visible, `limit=2` → 0).
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-2277 (pattern `paginate-before-filter`). Rules: `get_components` R5.
- **HR-6** `get_components` R6 — the workspace-wide list has no order of its own (inherited `get_by_workspace`; `id` once BUG-100 is fixed). Verified: rows came back out of `id` order after updates. Intended: `name` case-insensitive, then `id`, before paging, as the per-project list (BUG-1275).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-2279 (pattern `hr-6-non-default-list-order`). Rules: `get_components` R6.

### Precedent matches — all applied (decided by Claude under the reviewer's delegation, 2026-11-04)

### P1. A negative component budget is accepted — 🐞 BUG-2273
**Background:** `budget` is money (`Numeric(15,2)`). The project's own budget refuses negatives (BUG-1962).
**What happens today:** `budget: -5` is stored `-5.00` (verified).
**Example:** A typo gives component "Roof" a budget of −20 000.
**Rules affected:** `create_component` R6, `update_component` R6
**Answer:** bug — per BUG-1962 precedent: `ge=0` on `budget` of `ProjectComponentCreate` and `ProjectComponentUpdate` (not the response); `0` and `null` accepted; nothing written.
**Resolution:** 🐞 BUG-2273 (pattern `unvalidated-numeric-range`). Rules: `create_component` R6, `update_component` R6.

### P2. A component budget with more than 2 decimals is rounded silently — 🐞 BUG-2274
**Background:** The schemas type `budget` as `float`; the column keeps 2 decimals and Postgres rounds half up on store (HR-15 holds). Same root cause as BUG-1963 (project budget).
**What happens today:** `1000.005` is stored `1000.01`, `0.125` stored `0.13` (verified); a value of 10^13 or more fails at the flush (500).
**Example:** A budget typed `2500.505` is saved `2500.51` without a word.
**Rules affected:** `create_component` R6, `update_component` R6
**Answer:** bug — per BUG-1963 precedent: the schemas take `budget` as a decimal and refuse more than 2 decimal places or more than 13 integer digits (422), nothing written.
**Resolution:** 🐞 BUG-2274 (pattern `unbounded-decimal-input`). Rules: `create_component` R6, `update_component` R6.

### P3. Description, budget, deadline and dates cannot be cleared — 🐞 BUG-2275
**Background:** The update reads only the fields sent and drops every `null` (base `update`: `exclude_unset`, `exclude_none`). Same root cause as BUG-1953 (projects).
**What happens today:** `PUT {"description": null}` leaves the old description, 200 (verified).
**Example:** A manager empties the deadline of "Roof" and saves; the old deadline is still there.
**Rules affected:** `update_component` R3
**Answer:** bug — per BUG-1953 precedent: explicit `null` clears `description`, `budget`, `deadline`, `start_date`, `end_date`; `null` for `name` or `status` is refused by `ProjectComponentUpdate` (422); omitted fields unchanged.
**Resolution:** 🐞 BUG-2275 (pattern `exclude-none-blocks-clear`). Rules: `update_component` R3, R3a.

### P4. Saving a component without changes writes "Updated component" — 🐞 BUG-2276
**Background:** Every successful update writes a `component_updated` project event. Same root cause as BUG-632 and BUG-2118; the project's own update writes no event when nothing changes (manager `update_project` R4).
**What happens today:** `PUT {}` or the same values writes `Updated component "<name>"` (verified).
**Example:** Opening the edit dialog of "Roof" and pressing Save adds a line to the project's activity although nothing changed.
**Rules affected:** `update_component` R4
**Answer:** bug — per BUG-632 precedent: an update in which no field changes value writes no event; the component is returned as usual.
**Resolution:** 🐞 BUG-2276 (pattern `audit-event-on-noop`). Rules: `update_component` R4.

### P5. `project_id=0` lists the whole workspace — 🐞 BUG-2278
**Background:** `if project_id:` treats `0` like "no filter" (DAO FU-1 (c)). Same as BUG-1959, BUG-880.
**What happens today:** `project_id=0` returned all 10 components of the workspace (verified).
**Example:** A client sends `?project_id=0` and gets every project's components instead of none.
**Rules affected:** `get_components` R1
**Answer:** bug — per BUG-1959 precedent: only `None` means "no project filter"; `0` is looked up like any id and answers the guard's 404 `Project with ID 0 not found`.
**Resolution:** 🐞 BUG-2278 (pattern `falsy-zero-treated-as-missing`). Rules: `get_components` R1.

### D1. The "not found" branches after the guard are unreachable — `remove` (decided by Claude under the reviewer's delegation, 2026-11-04)
**Background:** `update_component` and `delete_component` look the component up again after `require_component_access`, which already answered 404 for the same lookup; `get_by_id` returns the second lookup and the endpoint checks it for `None`. Same as item service D3.
**What happens today:** `update_component` returning `None`, `delete_component` returning `False`, and the endpoints' three `if not …: 404` checks are never reached within one transaction (verified: unknown id → the guard's 404).
**Answer:** remove — dead branches (`project_component_service.py` 100–101, 134–135; `project_components.py` 48–49, 76–77, 91–92). The guard's 404 `Project component not found` is the one answer.
**Resolution:** not a bug; listed for the dead-code checklist. No rule for the branches.

Existing bugs written as rules here, no new ID: **BUG-1196** `delete_component` R2–R5; **BUG-1278** `get_components` R2, R4, `get_by_id` R2, `create_component` R2, `update_component` R2, `delete_component` R1. Cited: **BUG-1275** (per-project order), **BUG-1277** (endpoint `limit`), **BUG-1192** (`log_event`), **BUG-1197** (showing the blocker list, frontend).

Checked and **not** violated: **HR-2** — component names need not be unique. **HR-3, HR-8** — no grouping text, no `LIKE`. **HR-4** — components have no soft delete (hard delete, BUG-1196); the project's soft delete is BUG-1278. **HR-7** — BUG-1277 (endpoint). **HR-9** — components have no audit columns; the event is P4. **HR-10** — a hard delete of a component is not money, stock or a decision; the blocker check and the delete run in one transaction, and a stock ledger row or item line added in between still stops the delete at the database (foreign keys). **HR-15** — the database rounds half up; no Python rounding. **HR-16** — `create_component` checks the body's `project_id` in the caller's workspace (another workspace's → 404, verified); `ProjectComponentUpdate` has no `project_id`, so a component cannot be moved; every lookup is by the caller's workspace. **HR-11 … HR-14** — none.

**Permission checks:** none of its own. Anyone who may open the project may add, edit and delete its components (no role check). Recorded for `docs/future/permissions.md`, not asked.

## Overview
`ProjectComponentService` handles the parts of a project (components), behind `/project-components/`. It checks access through `ProjectManager`, writes components through the inherited DAO methods, logs `component_created` / `component_updated` / `component_deleted` into the **project's** activity log (`project_events`), and commits. It protects the private-project rule, workspace isolation and (BUG-1196) a component's history.

**Callables:** 5 specified · 2 not specified
**Externals to mock:** none. (`created_at` of components and events: Python column defaults; assert set, not value.)
**Integration-only behavior:** the HTTP mapping of `HTTPException` and `ValidationError`; the endpoint's `limit` bounds (BUG-1277); schema validation (400 today, BUG-461; 422 intended); the endpoints' dead 404 checks (D1).

### Transaction contract of this service (CT) — every write
Each write runs its checks and changes inside one `try`; on success `db.commit()`, then `db.refresh(row)` for create and update; any exception → `db.rollback()` once and re-raised. As outcomes, against TC1–TC6:
- **CT1.** As **TC1**: a write that succeeds is committed (survives a later rollback of the session).
- **CT2.** As **TC2** for `create_component` and `update_component`. `delete_component` returns `True` and re-reads nothing.
- **CT3.** As **TC3**, including the access refusals: the guard runs inside the `try`, so a 404 / 403 on a write also rolls the session back and discards every other uncommitted change pending in it. Same exception object.
- **CT4.** As **TC4**, with **exactly one** rollback (the service's own; `BaseService` gives two). Nothing saved. Verified.
- **CT5.** As **TC5** for create and update: a failing re-read leaves the change saved and reaches the caller (one rollback, nothing to undo). Verified.
- **CT6.** As **TC6**: `get_components` and `get_by_id` neither commit nor roll back; a refusal of the guard reaches the caller unchanged and pending changes stay. Verified.

**Facts for the test designer**
- Import: `from app.services.project_component_service import ProjectComponentService, project_component_service`. No constructor arguments; it uses the module singletons `project_component_dao` and `project_manager` directly (patch those names in `app.services.project_component_service` if needed).
- `ProjectComponentCreate`: `project_id` (required), `name` (required `str`), `description`, `budget` (`float`), `deadline` (all optional), `status` (`ProjectStatusEnum`, default `PLANNING`). `ProjectComponentUpdate`: `name`, `description`, `budget`, `deadline`, `start_date`, `end_date`, `status`, all optional; **no `project_id`**.
- Model: DAO spec Model facts; `budget` `Numeric(15,2)`; tables referencing a component, with their foreign-key action: `project_component_activity_events` (CASCADE), `project_component_attachments` (CASCADE), `project_component_items` (none), `project_component_tasks` (none; notes live here too, `is_note = True`), `project_component_item_ledger` (RESTRICT), `work_orders.project_component_id` (none, nullable), `miscellaneous_project_costs.project_component_id` (none, nullable).
- Event facts: `log_event` / `log_for_component` (manager spec). Created event: `event_type "component_created"`, description `Added component "<name>"`, performer `user_id`, metadata `{"component_id": <id>, "component_name": <name>}`.
- `ValidationError` is `app.core.exceptions.ValidationError` (400; `.detail`, `.errors`).
- **Model modules (gap 1):** `app.models.work_order.WorkOrder`, `app.models.work_order_type.WorkOrderType`, `app.models.item.Item`, `app.models.project_component_item.ProjectComponentItem`, `app.models.project_component_task.ProjectComponentTask`, `app.models.project_component_activity_event.ProjectComponentActivityEvent` (table `project_component_activity_events`), `app.models.project_event.ProjectEvent`. Schemas: `app.schemas.project_component` (`ProjectComponentCreate`, `ProjectComponentUpdate`).
- **Blocker tables (gap 2), NOT NULL columns without a default:**
  - `app.models.project_component_item_ledger.ProjectComponentItemLedger` (table `project_component_item_ledger`): `workspace_id`, `project_component_id` (the link; FK `ON DELETE RESTRICT`), `item_id` (FK `items`, RESTRICT), `transaction_type` (`String(50)`), `quantity` (int), `unit_cost`, `total_cost` (`Numeric(15,2)`), `qty_before`, `qty_after` (int), `source_type` (`String(50)`), `performed_by` (FK `profiles`). `performed_at` defaults to `utcnow`; every other column is nullable.
  - `app.models.miscellaneous_project_cost.MiscellaneousProjectCost` (table `miscellaneous_project_costs`): `workspace_id`, `name` (`String`), `amount` (`Numeric(15,2)`); `project_component_id` and `project_id` nullable (FK, no action); `created_at` defaults to `utcnow`.
  - `app.models.project_component_attachment.ProjectComponentAttachment` (table `project_component_attachments`): `workspace_id`, `project_component_id` (FK CASCADE), `attachment_id` (FK `attachments` CASCADE, so an `Attachment` row is needed), `attached_by` (FK `profiles`); `attached_at` has a server default. It never blocks (R5).
- **Dates (gap 3):** `deadline`, `start_date`, `end_date` are `datetime | None` in the schemas and `DateTime` columns (`timestamp without time zone`): a naive datetime is stored and read back as given (time of day kept). Use naive UTC values; aware values are not specified here.

**Notes for the test designer**
- Session mechanics as `department_service.spec.md` Notes (commit setup before an error path; patch `commit` / `refresh` / `rollback`).
- **BUG-2277:** a `ground-team` caller; 3 components of a private project they may not open created first, then 2 of a workspace-visible project; `limit=2` → intended the 2 visible → strict xfail. Statement count with a `before_cursor_execute` listener: intended a fixed number whatever the rows (≤ 3) → strict xfail.
- **BUG-2279:** names `"Zulu"`, `"apple"`, `"Banana"` inserted in that order → intended `apple`, `Banana`, `Zulu`; strict.
- **BUG-1196:** build each blocker kind directly (add + flush, commit before the call): `WorkOrder` with `project_component_id`, `ProjectComponentItemLedger`, `ProjectComponentItem`, `ProjectComponentTask` (and one with `is_note=True`), `MiscellaneousProjectCost`, `ProjectComponentActivityEvent` (`work_order_item_used`; and one `attachment_added`, which must **not** appear). Intended → strict xfail.

## Not specified
- `ProjectComponentService` class body — no `__init__`, no state.
- `project_component_service` — module-level singleton.

---

## `ProjectComponentService.get_components(db, workspace_id, user_id, project_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /project-components/`, always with every argument; `limit` ≤ 100 there)

**Purpose:** The components of one project, or every component of the workspace the caller may see.

**Returns:** a `list` of `ProjectComponent`.

**Rules:**
- **R1.** A `project_id` given → the project must pass `require_project_access` with this user (404 missing / other workspace; 403 private, OQ-18), then the rows are DAO `get_by_project` R1–R7 with `skip`, `limit` (BUG-1275 order). [BUG-2278] (P5) Only `None` means "no project filter": `project_id=0` answers 404 `Project with ID 0 not found`. *(Today: `0` lists the workspace, verified.)*
- **R2.** [BUG-1278] A `project_id` of a soft-deleted project → 404 `Project with ID <id> not found`. *(Today: its components are listed.)*
- **R3.** No `project_id` → the workspace's components the caller may see: those whose project is in the workspace and `can_access_project` allows (manager spec; workspace-visible projects for everyone; private ones for the workspace owner, an active `owner` / `ground-team-manager`, the creator and project members). A component whose project is not a project of the workspace (invalid data, HR-16) is left out.
- **R4.** [BUG-1278] No `project_id` → components of soft-deleted projects are left out and take no place on the page. *(Today: listed.)*
- **R5.** [BUG-2277] (HR-5) The access filter (R3, R4) is part of the query, before `skip` / `limit`: a page is short only at the end; the number of statements does not grow with the rows. *(Today: one page is read, then filtered in Python with two reads per component; pages come back short or empty.)*
- **R6.** [BUG-2279] (HR-6) No `project_id` → ordered by `name` case-insensitive, then `id`, before paging. *(Today: no order.)* Default page 100 (base `get_by_workspace`).
- **R7.** Read only (CT6).

**Errors:** R1, R2 (`HTTPException`); negative `skip` / `limit` → `DataError` when called directly (the endpoint refuses a negative `skip`; `limit` is BUG-1277).

**Side effects:** none.

---

## `ProjectComponentService.get_by_id(db, component_id, workspace_id, user_id)`
**Shape:** get-or-404 · **Persistence:** reads · **Visibility:** public (used by: `GET /project-components/{id}/`)

**Returns:** the `ProjectComponent`.

**Rules:**
- **R1.** The component must pass `require_component_access` R1–R4 with this user: 404 `Project component not found` (unknown, `0`, other workspace), 403 (private project, OQ-18); then it is returned.
- **R2.** [BUG-1278] A component of a soft-deleted project → 404 `Project with ID <project_id> not found`. *(Today: returned, verified.)*
- **R3.** Read only (CT6).

---

## `ProjectComponentService.create_component(db, component_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /project-components/`, 201)

**Returns:** the new `ProjectComponent`, committed and re-read (CT1, CT2).

**Rules:**
- **R1.** The body's `project_id` must pass `require_project_access` with this user: missing, `0` or another workspace's → 404 `Project with ID <project_id> not found` (HR-16, verified); private and not openable → 403. Nothing written (CT3).
- **R2.** [BUG-1278] A soft-deleted project → 404 `Project with ID <project_id> not found`, nothing written. *(Today: created, verified.)*
- **R3.** Otherwise one `project_components` row with every field of the body plus `workspace_id`; `start_date`, `end_date` empty; `status` default `PLANNING`; `created_at` set. Then one project event `component_created` on that project (Facts). Both committed (CT1); the component returned re-read (CT2).
- **R4.** Any status may be given (`COMPLETED` included); dates are not checked against each other.
- **R5.** [BUG-2272] (HR-1) `name` is stored trimmed; `""` or only spaces is refused by `ProjectComponentCreate` (422), nothing written. *(Today: stored as typed, verified.)* `description` kept as typed.
- **R6.** [BUG-2273] (P1) `budget < 0` refused (422); `0`, `null` accepted. [BUG-2274] (P2) more than 2 decimal places or more than 13 integer digits refused (422). *(Today: `-5` stored; `1000.005` stored `1000.01`, verified; 10^13 fails at the flush.)*
- **R7.** Commit and re-read failures follow CT4, CT5.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| project missing / other workspace / [BUG-1278] deleted | `HTTPException` 404 | `Project with ID <project_id> not found` |
| private project not openable | `HTTPException` 403 | `You do not have access to this project` |
| database error at flush or commit | the same `sqlalchemy.exc` error | — |

**Side effects:** one component and one project event, committed. On any error: rolled back (CT3).

---

## `ProjectComponentService.update_component(db, component_id, component_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /project-components/{id}/`)

**Returns:** the `ProjectComponent`, committed and re-read (CT1, CT2).

**Rules:**
- **R1.** The component must pass `require_component_access` R1–R4 (404 `Project component not found`; 403; 404 for its project); nothing written (CT3).
- **R2.** [BUG-1278] A component of a soft-deleted project → 404 `Project with ID <project_id> not found`, nothing written. *(Today: updated, verified.)*
- **R3.** Only fields sent with a value are applied (base `update`); fields not sent are unchanged. The project cannot be changed (no `project_id` in the schema). Any status may follow any status.
- **R3b.** (gap 4, decided by Claude under the reviewer's delegation, 2026-11-04) A `project_id` sent to `ProjectComponentUpdate` (in the body, or `ProjectComponentUpdate(project_id=…)`) is **ignored**, not refused: the schema keeps Pydantic's default extra-field policy, so it is dropped before the service (verified: `ProjectComponentUpdate(project_id=5, name="x").model_dump(exclude_unset=True) == {"name": "x"}`); the component keeps its project, the other fields are applied, 200. *Why:* every update schema of the app ignores unknown fields; HR-16 is not at stake because no link is written; refusing would need a schema policy change across the app, not a rule of this service. No bug.
- **R3a.** [BUG-2275] (P3) An explicit `null` clears `description`, `budget`, `deadline`, `start_date`, `end_date`; `null` for `name` or `status` is refused by `ProjectComponentUpdate` (422), nothing written. *(Today: every `null` is dropped and the old value stays, verified for `description`.)*
- **R4.** When at least one field changes value, one project event `component_updated`, description `Updated component "<name after the update>"`, performer `user_id`, metadata `{"component_id", "component_name"}` (log_for_component R2). [BUG-2276] (P4) When no field changes value (`{}`, or the same values), no event is written. *(Today: written on every update, verified.)*
- **R5.** [BUG-2272] (HR-1) A sent `name` is stored trimmed; blank refused (422). *(Today: as typed.)*
- **R6.** [BUG-2273, BUG-2274] `budget` as `create_component` R6.
- **R7.** Committed (CT1); returned re-read (CT2); commit and re-read failures follow CT4, CT5.

**Errors:** R1, R2; database errors unchanged.

**Side effects:** the changed fields and (R4) one project event, committed. On any error: rolled back.

---

## `ProjectComponentService.delete_component(db, component_id, workspace_id, user_id)`
**Shape:** delete (hard) · **Persistence:** writes · **Visibility:** public (used by: `DELETE /project-components/{id}/`, 204)

**Purpose:** Delete a component that has no history, or tell the user what stops it.

**Returns:** `True`. Nothing re-read.

**Rules:**
- **R1.** The component must pass `require_component_access` R1–R4 (404 / 403); [BUG-1278] a component of a soft-deleted project → 404 `Project with ID <project_id> not found`. Nothing written (CT3).
- **R2.** [BUG-1196] (owner, 2026-11-01) A component with history is refused, after the access check and before anything is written: `ValidationError` 400, `detail == "Component has history"`, `errors` == the list of blockers; the session is rolled back; no `component_deleted` event; the component and every linked row unchanged. *(Today: no refusal; see R6.)*
- **R3.** [BUG-1196] Blockers, one entry `{"type", "id"}` per row (the row's own `id`), rows of the component's workspace only:
  - `work_order` — a work order whose `project_component_id` is the component, in any state, a soft-deleted order included;
  - `ledger_entry` — a `project_component_item_ledger` row of the component;
  - `component_item` — a `project_component_items` row of the component;
  - `task` — a `project_component_tasks` row of the component, tasks and notes alike;
  - `misc_cost` — a `miscellaneous_project_costs` row with that `project_component_id`;
  - `activity_event` — a `project_component_activity_events` row of the component **other than** `attachment_added` / `attachment_removed`. (gap 5, decided by Claude under the reviewer's delegation, 2026-11-04) The exclusion compares `event_type` **exactly** (case-sensitive, no trimming): `"Attachment_added"`, `"attachment_added "` or `"attachment_add"` block like any other type. *Why:* the attachment code writes exactly these two codes; any other spelling did not come from it, so it is history to protect, and an exact compare is the rule the owner's BUG-1196 wording names.
  Sorted by type in the order above, then `id` ascending. The list is never empty when the refusal is raised.
- **R4.** [BUG-1196] (HR-16) Any such row whose `workspace_id` is not the component's is covered by exactly one `{"type": "other_workspace"}` (no `id`), last, however many there are; it shows nothing of the other workspace. Such a row alone also refuses the delete.
- **R5.** [BUG-1196] Rows that do **not** block, and go with the component: `attachment_added` / `attachment_removed` log rows (cascade) and the project's own events. A component with only those is deleted (R6a).
- **R5a.** [BUG-2262] `project_component_attachments` rows of the component do not block either: they are removed with the component, as their foreign key's `ON DELETE CASCADE` says, and the delete succeeds as R6a (one `component_deleted` event, `True`). *(Today: the ORM backref `ProjectComponent.attachments` has no `passive_deletes`, so it sets their `project_component_id` to NULL before the delete and the flush fails with `IntegrityError` (NOT NULL), 500, nothing saved — verified by the executor, PCS-D-06. No app code writes this table any more, so only old rows hit it.)* *(Fix in `app/models/project_component_attachment.py`, e.g. `passive_deletes=True` on the backref.)*
- **R6.** *(Today, for the record:)* with a work order or a misc cost the delete succeeds and their link is cleared; with an item line, a task or a ledger row it fails at the flush with `IntegrityError` (task: 23502, verified), nothing saved; the activity log goes by cascade.
- **R6a.** No blocker → one project event `component_deleted`, description `Deleted component "<name>"`, performer `user_id`, metadata `{"component_id", "component_name"}`, is written on the component's project, the component is deleted (hard), and both are committed (CT1, verified); returns `True`. The event stays after the component is gone.
- **R7.** A failing commit follows CT4.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| not found / other workspace | `HTTPException` 404 | `Project component not found` |
| project missing / [BUG-1278] deleted | `HTTPException` 404 | `Project with ID <project_id> not found` |
| private project not openable | `HTTPException` 403 | `You do not have access to this project` |
| [BUG-1196] has history | `ValidationError` 400 | `Component has history`; `.errors` = blockers |

**Side effects:** the component deleted (with its attachment links and attachment log rows), one project event, committed. On any error: rolled back.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21 | `if project_id:` (0 → workspace, BUG-2278) | `get_components` R1 |
| 22–31 | guard; DAO per project | `get_components` R1, R2 |
| 33–35 | workspace page first (BUG-2277, BUG-2279) | `get_components` R5, R6 |
| 37–45 | per row: project in workspace; access | `get_components` R3, R4, R5 |
| 48–53 | guard; re-read | `get_by_id` R1–R3; D1 |
| 62–65 | create: guard | `create_component` R1, R2 |
| 66–68 | dump + workspace; create | `create_component` R3–R6 |
| 69–77 | `component_created` event | `create_component` R3 |
| 78–80 | commit; refresh; return | CT1, CT2 |
| 81–83 | any exception → rollback, re-raise | CT3–CT5 |
| 94–99 | update: guard; re-read | `update_component` R1, R2 |
| 100–101 | `not component` → `None` (unreachable) | D1 |
| 102–104 | base update (`exclude_none`, BUG-2275) | `update_component` R3, R3a, R5, R6 |
| 105–112 | event always (BUG-2276) | `update_component` R4 |
| 113–118 | commit; refresh; except | `update_component` R7; CT1–CT5 |
| 128–133 | delete: guard; re-read | `delete_component` R1 |
| 134–135 | `not component` → `False` (unreachable) | D1 |
| 136–143 | `component_deleted` event (no blocker check, BUG-1196) | `delete_component` R2–R6a |
| 144–146 | remove; commit; `True` | `delete_component` R6, R6a, R7 |
| 147–149 | any exception → rollback, re-raise | CT3, CT4 |
| 152 | module singleton | Not specified |

## Gap log
G1 (`project_component_service.cases.md` gap 1) — Fact — Facts: model modules of `WorkOrder`, `WorkOrderType`, `Item`, `ProjectComponentItem`, `ProjectComponentTask`, `ProjectComponentActivityEvent`, `ProjectEvent`; schema module.
G2 (gap 2) — Fact — Facts: classes, modules and required columns of `ProjectComponentItemLedger` (link `project_component_id`), `MiscellaneousProjectCost`, `ProjectComponentAttachment`.
G3 (gap 3) — Fact — Facts: `deadline`, `start_date`, `end_date` are `datetime | None` / `DateTime` (timestamp without time zone); use naive UTC.
G4 (gap 4) — Intent, decided by Claude under the reviewer's delegation (2026-11-04) — `update_component` R3b: a sent `project_id` is ignored (Pydantic default; verified), not refused. Why: app-wide schema policy, no link written so HR-16 holds, and the 'cannot move' rule stands. No bug.
G5 (gap 5) — Intent, decided by Claude under the reviewer's delegation (2026-11-04) — `delete_component` R3: the `attachment_added` / `attachment_removed` exclusion is an exact, case-sensitive compare; other spellings block. Why: only the attachment code writes those codes.
G6 (executor DISCREPANCY-1, 2026-11-05) — Bug — `delete_component` R5a / 🐞 BUG-2262: attachment-link rows cascade with the component; today the ORM nulls their NOT NULL link and the delete fails with `IntegrityError`.
