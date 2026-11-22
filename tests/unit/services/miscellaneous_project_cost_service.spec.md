# Spec — `app/services/miscellaneous_project_cost_service.py`

> **Status:** APPROVED (2026-11-10; nothing open. Every item is a house rule, a precedent, or was decided by Claude under the reviewer's delegation (2026-11-10). No owner question: project costing is deferred until after launch.)
> **Source commit:** e48a092
> **Fill-gaps 2026-11-10** (case designer, `miscellaneous_project_cost_service.cases.md` gaps 1–3): BUG-100 is corrected to "still open", the refusal order of `create_cost` R2 is decided under delegation, and the BUG-1192 detail is stated. Status unchanged. See the Gap log.

> **Projects deferred (owner, 2026-11-10).** "Skip project, we will revisit this after launch." This spec describes **today's behaviour** of what a misc cost is and how it counts (sign and precision of `amount`, costs with no project or component, which costs belong to a project). Those rules are tagged *revisit after launch (owner 2026-11-10)*; no question is raised and no intent bug is logged for them (OQ-27, OQ-28 answered so). The bugs below are house-rule or precedent bugs about lists, access, ids, events and errors; they are logged with status *open — revisit after launch*, as BUG-2460 / BUG-2461 of the DAO, and their tests stay.

> **Form.** As `tests/unit/services/project_component_note_service.spec.md`. **Below:** `tests/unit/dao/miscellaneous_project_cost.spec.md` (`get_by_project`, `get_by_component`, inherited R1–R2b: raw lookups, amount stored rounded half up by the column, `update` drops `null`; BUG-2460, BUG-2461; OQ-28), `tests/unit/managers/project_manager.spec.md` (`can_access_project`, `require_project_access`, `require_component_access`, `log_for_component`, `log_event`), `tests/unit/dao/project_component.spec.md`, `tests/unit/dao/base.spec.md` (`get_by_workspace`, BUG-100; `get_by_id_and_workspace`, `create`, `update`, `remove`). All APPROVED; cited, not restated. This spec answers DAO FU-1 (a)–(g).
>
> **Not a `BaseService`.** The class commits and rolls back with `db.commit()` / `db.rollback()` itself. Its transaction rules are M-TC1 … M-TC6 below: the same outcomes as TC1–TC6 of `tests/unit/services/base_service.spec.md`, differences named.
>
> **Standing decisions applied here (not asked again):** BUG-1278 (a soft-deleted project answers 404 `Project with ID <id> not found` through `require_project_access` / `require_component_access`; workspace-wide lists leave its rows out). BUG-1013 (owner 2026-10-30, HR-16): every id sent on create is checked against the caller's workspace. OQ-18 (owner): a private project the caller may not open answers 403 here, kept.
>
> **Verified by running** (my own `v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\auth\misc\`, one outer transaction on `marker_test`, rolled back, private `COVERAGE_FILE`; nothing persisted), as a `ground-team` member `u`: own open project A + component of private project B (u may not open B) → 201-equivalent, cost stored with both, the `cost_added` event written on **project B** with B's component in its metadata; component of B alone → 403; `project_component_id=0` alone and `project_id=0` alone → `IntegrityError`; no project and no component, name `"  "`, amount `-5` → stored (`-5.00`), no event; amount `1e14` → `DataError`; a cost on a soft-deleted project → created; a stored cost whose component is in another workspace → returned by `get_by_id` to u, `update_cost` renames it and writes no event; `update_cost` with `{}` → one `cost_updated` event; `get_costs(project_id=0)` → the workspace-wide list; workspace-wide list keeps the deleted project's cost and hides the unlinked and the foreign-component ones; `get_costs(project_id=<deleted>)` → listed; unknown id → `None` / `None` / `False`; delete → `True`, last event `cost_deleted`; `limit=-1` → `DataError`. **Read, not run:** the endpoint `app/api/v1/endpoints/miscellaneous_project_costs.py`.

## Review
> Nothing open. Overwrite a pre-filled answer only if the house rule or the delegated decision should not apply here.

### House-rule violations — applied automatically
- **HR-1** `create_cost` R4, `update_cost` R3 — `name` is a plain `str` in `MiscellaneousProjectCostCreate` / `Update`: `""` and `"  "` are stored as typed (verified; DAO FU-1 (a)). Intended: trimmed; blank refused by the schema (422), nothing written.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** 🐞 BUG-2613 (pattern `blank-name-accepted`). Rules: `create_cost` R4, `update_cost` R3.
- **HR-5** `get_costs` R4 — without a project or component, the page is taken first (`get_by_workspace`) and costs the caller may not see are dropped in Python afterwards, with up to two reads per cost (DAO FU-1 (c)). Intended: the visibility filter is part of the query, before `skip` / `limit`; the number of statements does not grow with the rows (BUG-2293 precedent).
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-2611 (pattern `paginate-before-filter`). Rules: `get_costs` R4.
- **HR-6** `get_costs` R3 — the workspace-wide list has no order today (inherited `get_by_workspace`). Intended: `id` ascending before paging, as the DAO's lists (BUG-2460).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** 🐞 BUG-100 (existing and **still open**: `app/dao/base.py` `get_by_workspace` has no `ORDER BY` today, re-verified in `order_workflow_service.spec.md` this week; no new ID). Rules: `get_costs` R3. *(Corrected 2026-11-10, fill-gaps G1: an earlier line said "fixed".)*
- **HR-7** `get_costs` R7 — `GET /miscellaneous-project-costs/` declares `limit: Query(100, le=100)` with no lower bound: `0` → `[]`, negative → `DataError` (500) (verified at the service; DAO FU-1 (d)). Intended: `limit >= 1`, 422 otherwise; the cap of 100 stays.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** 🐞 BUG-2610 (pattern `missing-limit-lower-bound`). Endpoint rule; the service does not change.
- **HR-16** `get_by_id` R3 — a stored cost whose component is not in the caller's workspace (invalid data; new ones refused by BUG-1013) is returned to any member with no access check, and the response shows the other workspace's component id (verified). Intended: such a cost is treated as not found (`None`, the endpoint's 404), so `update_cost` and `delete_cost` refuse it too.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-2616 (pattern `cross-workspace-link-not-refused`). Rules: `get_by_id` R3; through it `update_cost` R1, `delete_cost` R1.

### Precedent matches — decided by Claude under the reviewer's delegation (2026-11-10)

### D1. Saving a cost unchanged writes "Updated cost" — 🐞 BUG-2617
**Background:** Every successful update writes one `cost_updated` project event. Same root cause as BUG-632 / BUG-2295.
**What happens today:** `PUT {}`, or the same values, logs `Updated cost "<name>"` (verified).
**Example:** Rafi opens the "Crane hire" cost and presses Save without typing; the project's activity tab shows "Updated cost 'Crane hire'".
**Rules affected:** `update_cost` R5
**Answer:** bug — per BUG-632 precedent: an update that changes no value writes no event; the cost is returned as usual.
**Resolution:** 🐞 BUG-2617 (pattern `audit-event-on-noop`).

### D2. Costs of a deleted project stay on the workspace-wide list — 🐞 BUG-2612
**Background:** BUG-1278 hides a deleted project's rows; the guard answers 404 when one project or component is asked for. The workspace-wide list does its own filter with a raw project read, which a deleted project passes.
**What happens today:** `GET /miscellaneous-project-costs/` lists the costs of soft-deleted projects (verified).
**Example:** Project "Line 3" is deleted; its 3 misc costs still appear on a workspace-wide cost view.
**Rules affected:** `_filter_accessible_costs` R3
**Answer:** bug — per BUG-2294 / BUG-1278 precedent: costs whose project is soft-deleted are not listed and take no place on the page; the rows stay.
**Resolution:** 🐞 BUG-2612 (pattern `join-ignores-soft-deleted`).

### D3. An id of `0` is treated as "not given" — 🐞 BUG-2614
**Background:** The service tests `project_id` and `project_component_id` for truthiness, so `0` takes the "not sent" path. Same root cause as BUG-1074 (`machine_id=0`).
**What happens today:** `GET …/?project_id=0` returns the workspace-wide list instead of a project's (verified). `POST` with `project_id: 0` or `project_component_id: 0` skips the access check and fails at the insert with `IntegrityError` (a 500) (verified).
**Example:** A client builds the URL from an empty select whose value is `0` and receives every cost the user can see, not "no such project".
**Rules affected:** `get_costs` R1, R2; `create_cost` R1
**Answer:** bug — per BUG-1074 precedent: an id is "given" when it is not `None`; `0` is an id that matches nothing, so the guard answers 404 (`Project with ID 0 not found` / `Project component not found`) and nothing is written.
**Resolution:** 🐞 BUG-2614 (pattern `falsy-zero-treated-as-missing`).

### D4. A cost can name a component of another project, bypassing that project's privacy — 🐞 BUG-2615
**Background:** A cost may carry a `project_id`, a `project_component_id`, or both. When `project_id` is sent, only that project is checked; the component is not looked at (BUG-1013 already covers a component of another *workspace*). The activity event goes to the **component's** project.
**What happens today:** a `ground-team` member who may open project A but not private project B posts `{"project_id": A, "project_component_id": <component of B>}`: the cost is saved, B's activity log gains "Added cost …" by them, and they can read the cost back (it is checked against A only) (verified).
**Example:** Sara can see the open project "Yard" but not the private "Bid 2027". She adds a 50.00 cost on "Yard" with the id of a "Bid 2027" component; the private project's log shows her entry and its component costs now include her row.
**Rules affected:** `create_cost` R1, R2
**Answer:** bug — per BUG-723 precedent (a child must belong to the parent named with it): when both ids are sent, the component is checked exactly as when sent alone (`require_component_access`: 404 / 403) **and** must belong to `project_id`; otherwise `HTTPException(400, "Project component does not belong to this project")`, nothing written.
**Resolution:** 🐞 BUG-2615 (pattern `missing-cross-entity-ownership-check`). Together with BUG-1013 (another workspace's component → 404).

### D5. An amount too large for the column gives a 500 — 🐞 BUG-2618
**Background:** `amount` is a `float`; the column is `Numeric(15,2)`, so 14 or more integer digits do not fit (DAO inherited R2). BUG-2274 refused such values for component budgets.
**What happens today:** `amount: 1e14` fails at the insert with `DataError` (22003), a 500 (verified).
**Example:** A typo of 100000000000000 in the amount field gives "Internal Server Error".
**Rules affected:** `create_cost` R5, `update_cost` R4
**Answer:** bug — per BUG-2274 precedent, limited to the overflow: more than 13 integer digits (after rounding to 2 places) is refused by the schema with 422, nothing written. The silent rounding of extra decimals and the sign (OQ-28) stay as today, *revisit after launch (owner 2026-11-10)*.
**Resolution:** 🐞 BUG-2618 (pattern `unbounded-decimal-input`).

Checked and **not** a new line: **HR-2** — cost names need not be unique. **HR-3, HR-8** — no grouping, no `LIKE`. **HR-4** — costs have no soft delete (hard delete); a deleted project is BUG-1278 / D2. **HR-9** — the table has no audit stamps; events are D1. **HR-10** — a misc cost is a hand-typed figure, no balance or stock moves; no lock. **HR-12, HR-13, HR-14** — no external system, no batch. **HR-15** — the column rounds half up (DAO inherited R2b). **HR-16** — create: BUG-1013 (existing); stored bad rows: BUG-2616; a project id of another workspace answers 404 through the guard. **Delete blockers** — nothing references a cost (no foreign key to `miscellaneous_project_costs`), so nothing blocks a delete.

**Permission checks:** only "may open the project" (`require_project_access` / `require_component_access`). Any such member may add, change or delete any cost, whoever entered it (no author column), and sees every amount. Recorded for the permissions feature (`docs/future/permissions.md`), not asked.

## Overview
`MiscellaneousProjectCostService` is the transaction boundary for hand-typed extra costs (name, description, amount) booked on a project, a project component, or both. The `/miscellaneous-project-costs/` endpoints call it; the web app's component panel creates costs with `project_component_id` only. It checks project access through `ProjectManager`, writes through the DAO, logs one project event per write, and commits.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** none (`created_at` is a Python column default: assert set).
**Integration-only behavior:** the endpoint's 404 `Miscellaneous project cost not found` for `None` / `False`; `skip >= 0`, `limit <= 100` (BUG-2610); schema validation (422).

### Transaction rules (M-TC) — this service's writes
`create_cost`, `update_cost`, `delete_cost` run their whole body in one `try`: on success `db.commit()` (then `db.refresh` for create and update); any exception → `db.rollback()` and re-raise.
- **M-TC1.** A write that succeeds is committed: the change (cost and event) survives a later rollback of the same session.
- **M-TC2.** Create and update return the row re-read after the commit (`created_at` loaded, not expired). Delete returns `True`, no re-read.
- **M-TC3.** Any exception inside the `try` (the guard's `HTTPException` 403/404, `IntegrityError`, `DataError`, anything) rolls the session back **once** and reaches the caller as the same object; every uncommitted change pending in the session is discarded; the session is usable afterwards.
- **M-TC4.** If `commit` raises: one rollback, the commit's exception reaches the caller unchanged, nothing saved.
- **M-TC5.** If the re-read after commit raises: that exception reaches the caller and the change stays saved.
- **M-TC6.** Reads (`get_costs`, `get_by_id`) neither commit nor roll back; their exceptions reach the caller unchanged. **Differs from TC:** `update_cost` / `delete_cost` that find nothing return `None` / `False` with **no commit and no rollback** (pending changes stay pending).

**Facts for the test designer**
- Import: `from app.services.miscellaneous_project_cost_service import MiscellaneousProjectCostService, miscellaneous_project_cost_service`. No constructor arguments. The endpoint passes `get_costs` and `get_by_id` by keyword, the writes positionally.
- Schemas: `from app.schemas.miscellaneous_project_cost import MiscellaneousProjectCostCreate, MiscellaneousProjectCostUpdate` (fields: DAO inherited R2b; `Update` has `name`, `description`, `amount`, all optional, no ids). Model: `app.models.miscellaneous_project_cost.MiscellaneousProjectCost`; events: `app.models.project_event.ProjectEvent`.
- Guard errors are `fastapi.HTTPException`: 404 `Project with ID <id> not found`, 404 `Project component not found`, 403 `You do not have access to this project` (project manager `require_project_access` R1–R4, `require_component_access` R1–R4).
- Event metadata: the service passes `{"cost_id", "cost_name"}`; through a component `log_for_component` R2 adds `component_id`, `component_name`; through a project only, the service adds `"component_id": None`.

**Notes for the test designer**
- Session and commits as `department_service.spec.md` Notes; on every raising path commit the setup first. Build projects and components as `project_manager.spec.md` Notes (a project needs a factory and `description`).
- A "stored bad row" (BUG-2616) is built directly: `MiscellaneousProjectCost(workspace_id=<own>, project_component_id=<other workspace's component>, ...)`, add + flush.
- **BUG-2611:** non-privileged caller; 3 costs on a private project they may not open created first, then 2 on an open project; `limit=2` → intended the 2 visible ones; today `[]` → strict xfail.
- **BUG-100 order:** BUG-100 is still open (G1). Today's order is physical, and it can match `id` order on fresh rows, so the case is a **non-strict** xfail (as BUG-2292). To make today's disorder likely, update the first row after inserting three (the order workflow verifier then saw `[B, A]`). A strict card must not depend on it.

## Not specified
- `miscellaneous_project_cost_service` — module-level singleton.

---

## `MiscellaneousProjectCostService._log_cost_activity(db, cost, workspace_id, user_id, event_type, description)`
**Shape:** event-log · **Persistence:** writes · **Visibility:** internal (used by: `create_cost`, `update_cost`, `delete_cost`)

**Rules:**
- **R1.** A cost with a `project_component_id` (truthy): one event through `log_for_component` R1–R2 — on the **component's** project, metadata `{"cost_id", "cost_name", "component_id", "component_name"}`, performer `user_id`. If that component is not in `workspace_id`, nothing is written and nothing raised. The cost's `project_id` is not used, even when set.
- **R2.** Otherwise, a cost with a `project_id` (truthy): one event through `log_event` on that project, metadata `{"cost_id", "cost_name", "component_id": None}`. A project not of the workspace follows `log_event` R2 (BUG-1192: `HTTPException(404, "Project with ID <project_id> not found")`, nothing written; today written). (G3: the detail is from `project_manager.spec.md` `log_event` R2.)
- **R3.** A cost with neither: no event. *(revisit after launch (owner 2026-11-10))*
- **R4.** Flushed, not committed; returns `None`.

---

## `MiscellaneousProjectCostService._filter_accessible_costs(db, costs, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `get_costs` without project or component)

**Returns:** the costs kept, in input order.

**Rules:**
- **R1.** A cost's project is its `project_id`; if that is empty and it has a component, the component's project (component looked up in `workspace_id`; not found → no project).
- **R2.** A cost with no project by R1 is dropped: costs with neither link, and component-only costs whose component is in another workspace. *(revisit after launch (owner 2026-11-10) for the unlinked ones)*
- **R3.** [BUG-2612] (D2) A cost whose project is soft-deleted is dropped. *(Today: kept; the project read is raw, verified.)*
- **R4.** Otherwise kept exactly when the project is found in the workspace and `can_access_project` (R1–R3 there) is true. A cost with both links is judged by its `project_id` only (BUG-2615 stops new mismatched rows).
- **R5.** Empty input → `[]`.

---

## `MiscellaneousProjectCostService.get_costs(db, workspace_id, user_id, project_id=None, project_component_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /miscellaneous-project-costs/`)

**Returns:** a `list` of `MiscellaneousProjectCost`.

**Rules:**
- **R1.** With `project_id` given: `require_project_access` first (404 / 403; deleted project → 404 per BUG-1278, today listed), then DAO `get_by_project` R1–R6 (BUG-2460, BUG-2461; *revisit after launch (owner 2026-11-10)*). `project_component_id` is then ignored. [BUG-2614] (D3) "Given" means not `None`: `0` → 404 `Project with ID 0 not found`. *(Today: `0` falls through to R2 / R3, verified.)*
- **R2.** Else with `project_component_id` given: `require_component_access` first (404 / 403), then DAO `get_by_component` R1–R4. [BUG-2614] `0` → 404 `Project component not found`. *(Today: falls through to R3.)*
- **R3.** Else: the workspace's costs (`workspace_id` match), then `_filter_accessible_costs`. [BUG-100] (HR-6) ordered `id` ascending before paging. *(Today: no order.)*
- **R4.** [BUG-2611] (HR-5) R3's filter (helper R1–R4) is applied before `skip` / `limit`: a page is short only at the end, and the statements do not grow with the rows. *(Today: page first, then filter in Python with up to two reads per cost.)*
- **R5.** R3 leaves out deleted projects' costs (BUG-2612, helper R3).
- **R6.** Read only (M-TC6).
- **R7.** Paging defaults `skip=0`, `limit=100`; `limit=0` → `[]`; negative values → `DataError`. The service sets no bound (endpoint, BUG-2610).

---

## `MiscellaneousProjectCostService.get_by_id(db, cost_id, workspace_id, user_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /miscellaneous-project-costs/{id}/`; `update_cost`, `delete_cost`)

**Returns:** the cost, or `None`.

**Rules:**
- **R1.** Unknown id, `0`, or another workspace's → `None` (endpoint 404); no access check runs.
- **R2.** The cost's project is found as `_filter_accessible_costs` R1. With a project, `require_project_access` runs (404 / 403; deleted project → 404 per BUG-1278, today returned); passed → the cost. A cost with both links is checked against its `project_id` only.
- **R3.** [BUG-2616] (HR-16) A cost whose `project_component_id` is set but not a component of the workspace, and which has no `project_id`, → `None`. *(Today: returned to any member with no check, verified.)*
- **R4.** A cost with neither link → returned to any member, no check. *(revisit after launch (owner 2026-11-10); DAO FU-1 (g))*
- **R5.** Read only (M-TC6).

---

## `MiscellaneousProjectCostService.create_cost(db, cost_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /miscellaneous-project-costs/`, 201)

**Rules:**
- **R1.** With `project_id` given: `require_project_access` (404 / 403; deleted project → 404, BUG-1278, today created). Else with `project_component_id` given: `require_component_access`. Refused → its `HTTPException`, nothing saved (M-TC3). [BUG-2614] (D3) "given" = not `None`; `0` → the guard's 404. *(Today: `0` skips the guard and the insert raises `IntegrityError`, verified.)*
- **R2.** [BUG-1013, BUG-2615] (HR-16, D4) When both ids are sent, the component is also checked: another workspace's or unknown → 404 `Project component not found`; a component of a project the caller may not open → 403; a component of a different project → `HTTPException(400, "Project component does not belong to this project")`; nothing written. **Order (G2, decided by Claude under the reviewer's delegation (2026-11-10), visibility first as attachment manager PR-4):** first `project_id`'s own guard, then the component's 404, then the component's 403 (its project may not be opened), and the 400 only last, for a component the caller may open. A component of a private project the caller may not open, sent with another project they may open, therefore gets the **403**, never the 400: the 400 would tell them which project that component belongs to. *(Today: the component is not looked at; verified stored, with the event on the component's project.)*
- **R3.** With neither id: no check; the cost is stored unlinked (no event, `_log_cost_activity` R3). *(revisit after launch (owner 2026-11-10))*
- **R4.** [BUG-2613] (HR-1) `name` stored trimmed; `""` or only spaces refused by `MiscellaneousProjectCostCreate` (422), nothing written. *(Today: as typed, verified `"  "`.)* `description` optional, as typed.
- **R5.** `amount` stored as DAO inherited R2a / R2b: rounded half up to 2 places by the column, negative and zero stored *(OQ-28, revisit after launch (owner 2026-11-10))*. [BUG-2618] (D5) More than 13 integer digits → 422 from the schema, nothing written. *(Today: `DataError` at the insert, verified.)*
- **R6.** One row: `workspace_id` = the caller's, `project_id`, `project_component_id`, `name`, `description`, `amount` from the input, `created_at` set.
- **R7.** One event `cost_added`, description `Added cost "<name>"`, performer `user_id`, as `_log_cost_activity` R1–R2.
- **R8.** Committed and returned re-read (M-TC1, M-TC2); failures M-TC3–M-TC5.

---

## `MiscellaneousProjectCostService.update_cost(db, cost_id, cost_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /miscellaneous-project-costs/{id}/`)

**Rules:**
- **R1.** The cost is found as `get_by_id` R1–R4 (BUG-2616). Not found → `None`, nothing written, no commit, no rollback (M-TC6); a guard refusal → its `HTTPException`, rolled back (M-TC3).
- **R2.** Only `name`, `description`, `amount` sent with a non-`null` value are applied (base `update`); `null` or omitted fields stay (description cannot be cleared, DAO FU-1 (f), intended). The links cannot be changed.
- **R3.** [BUG-2613] (HR-1) A sent `name` is stored trimmed; blank refused (422). *(Today: as typed.)*
- **R4.** A sent `amount` as `create_cost` R5 (BUG-2618; sign and rounding *revisit after launch*).
- **R5.** One event `cost_updated`, `Updated cost "<new name>"`, as `_log_cost_activity` R1–R2 (none for an unlinked cost or one whose component is not in the workspace). [BUG-2617] (D1) Only when at least one field changes value; otherwise no event. *(Today: always, verified.)*
- **R6.** Committed, returned re-read (M-TC1, M-TC2); failures M-TC3–M-TC5.

---

## `MiscellaneousProjectCostService.delete_cost(db, cost_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /miscellaneous-project-costs/{id}/`, 204)

**Returns:** `True` when deleted; `False` when not found.

**Rules:**
- **R1.** Found as `update_cost` R1 (BUG-2616); not found → `False`, nothing written, no commit, no rollback.
- **R2.** One event `cost_deleted`, `Deleted cost "<name>"`, as `_log_cost_activity` R1–R2, is written, then the row is hard-deleted. Nothing references a cost, so nothing blocks.
- **R3.** Committed (M-TC1; the event stays, the cost is gone); `True`; no re-read. Failures M-TC3, M-TC4.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 25 | metadata | `_log_cost_activity` R1, R2 |
| 26–36 | component truthy → `log_for_component` (component not found → nothing) | `_log_cost_activity` R1 |
| 37–47 | project truthy → `log_event` | `_log_cost_activity` R2 |
| 37 (false) | neither → no event | `_log_cost_activity` R3 |
| 51 | loop; empty | `_filter_accessible_costs` R5 |
| 53–57 | no project, component → its project (not found → `None`) | `_filter_accessible_costs` R1 |
| 58–59 | no project → skip | `_filter_accessible_costs` R2 |
| 60–66 | project found (raw, BUG-2612) and accessible | `_filter_accessible_costs` R3, R4 |
| 79 | `project_id` truthy (BUG-2614) | `get_costs` R1 |
| 80–89 | guard; DAO `get_by_project` | `get_costs` R1 |
| 90 | `project_component_id` truthy (BUG-2614) | `get_costs` R2 |
| 91–100 | guard; DAO `get_by_component` | `get_costs` R2 |
| 102–105 | `get_by_workspace` (no order, BUG-100), page then filter (BUG-2611) | `get_costs` R3–R5, R7 |
| 108–112 | not found → `None` | `get_by_id` R1 |
| 113–118 | component → project; not found → none (BUG-2616) | `get_by_id` R2, R3 |
| 119–122 | project → guard; none → no check | `get_by_id` R2, R4 |
| 133–136 | `project_id` truthy → project guard (BUG-2614, BUG-2615) | `create_cost` R1, R2 |
| 137–140 | elif component truthy → component guard | `create_cost` R1 |
| 137 (false) | neither → no check | `create_cost` R3 |
| 141–143 | dump + `workspace_id`; create | `create_cost` R4–R6 |
| 144–151 | event | `create_cost` R7 |
| 152–157 | commit, refresh / rollback | `create_cost` R8; M-TC |
| 168–170 | find; `None` | `update_cost` R1 |
| 171 | base update (`exclude_none`) | `update_cost` R2–R4 |
| 172–179 | event always (BUG-2617) | `update_cost` R5 |
| 180–185 | commit, refresh / rollback | `update_cost` R6 |
| 189–191 | find; `False` | `delete_cost` R1 |
| 192–200 | event; remove | `delete_cost` R2 |
| 201–205 | commit, `True` / rollback | `delete_cost` R3 |
| 208 | singleton | Not specified |

## Gap log
- G1 (miscellaneous_project_cost_service.cases.md gap 1) — Contradiction — BUG-100 is still open (no `ORDER BY` in `app/dao/base.py`; re-verified in `order_workflow_service.spec.md`). The HR-6 resolution line is corrected; the Notes say the case is non-strict and how to provoke disorder. `get_costs` R3 is unchanged.
- G2 (gap 2) — Intent, decided under delegation (2026-11-10) — `create_cost` R2 refusal order: visibility first (404, then 403), the 400 last, per PR-4. A private project's component sent with another project gives 403.
- G3 (gap 3) — Fact — BUG-1192's 404 detail `Project with ID <project_id> not found` added to `_log_cost_activity` R2.
