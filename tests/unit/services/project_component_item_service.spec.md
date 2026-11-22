# Spec — `app/services/project_component_item_service.py`

> **Status:** APPROVED (2026-11-04; nothing open. No rule moves stock or money (see "Stock and money" below), so no owner question; every item is a house rule, an existing owner decision (BUG-1012) or was decided by Claude under the reviewer's delegation (2026-11-04).)
> **Source commit:** e48a092

> **Revision 2026-11-04 (fill-gaps, `project_component_item_service.cases.md` gaps 1).** Schema module named. No new bug, no question; stays APPROVED. See the Gap log.

> **Form.** As `tests/unit/services/department_service.spec.md`. **Below:** `tests/unit/managers/project_manager.spec.md` (`require_component_access`, `can_access_project`, `log_for_component`), `tests/unit/dao/project_component_item.spec.md` (`get_by_component`; Model facts), `tests/unit/dao/base.spec.md` (`get_by_workspace`: `id` order after BUG-100; raw `get_by_id_and_workspace`, `create`, `update`, `remove`). All APPROVED; cited, not restated. This spec answers item DAO FU-1 (a)–(c) and writes the existing owner bug BUG-1012 as a rule.
>
> **Not a `BaseService`.** Own transaction rules I-TC1 … I-TC6, as N-TC1–N-TC6 of `project_component_note_service.spec.md`.
>
> **Standing decisions applied here (not asked again):** BUG-1012 (owner, 2026-10-30: the item must be in the caller's workspace, else 404 `Item with ID {item_id} not found`). BUG-1278 (rows under a deleted project → 404 through the guard; workspace-wide list leaves them out; this service is named in that bug). OQ-18: 403 for a private project, kept. HR-16.
>
> **Verified by running** (`v1.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvc\forkB\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): another workspace's item accepted; a deleted item (`is_active = False`) accepted; `qty = -3` and `qty = 0` accepted, the same item twice on one component accepted; an unknown `item_id` → `IntegrityError` (FK) at the flush; `PUT {}` logs `item_updated` "Updated component item (qty -3)"; `qty = 3000000000` → `DataError` (integer out of range); `project_component_id=0` listed the workspace (4 rows). **Read, not run:** the endpoint; `item_summary_service`.

### Stock and money
A project component item is a **planned** quantity of an item for a component ("items required for a project component"). Read across `app/` (2026-11-04): creating, changing or deleting one changes no stock (`inventory`, `machine_items`), writes no ledger (`project_component_item_ledger` is written by work orders, not from these rows), and touches no price or cost. No trigger or migration reads the table. The only reader besides this service is `ItemSummaryService` (`app/services/item_summary_service.py` ~679, ~744): it counts an item's component rows and lists up to the preview limit of projects / components using it. So `qty` is a plan figure only, and its validation is decided under the reviewer's delegation (D2), not asked of the owner. If a later feature consumes these rows for stock or cost, D2 must be revisited.

## Review
> Nothing open. Overwrite a pre-filled answer only if the rule should not apply here.

### House-rule violations — applied automatically
- **HR-16** `create_component_item` R3 — `item_id` is not looked up: another workspace's item is linked (verified); an unknown id fails at the flush with `IntegrityError` (500). Existing owner bug.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1012 (existing; no new ID). Rules: `create_component_item` R3.
- **HR-5** `get_items` R4 — without a component, rows the caller may not see are dropped after paging, two reads per row (item DAO FU-1 (b)). Intended: in the query, before paging.
**Answer:** bug — per HR-5 (house rule)
**Resolution:** 🐞 BUG-2308 (pattern `paginate-before-filter`).
- **HR-7** `get_items` R7 — `GET /project-component-items/` has no lower bound on `limit`. Existing.
**Answer:** bug — per HR-7 (house rule)
**Resolution:** 🐞 BUG-1277 (existing). Endpoint rule.

### Precedent matches — all applied (decided by Claude under the reviewer's delegation, 2026-11-04)

### P1. `project_component_id=0` lists the whole workspace — 🐞 BUG-2309
**Background:** `if project_component_id:` (item DAO FU-1 (c)); same as BUG-1959.
**What happens today:** `?project_component_id=0` returns the workspace-wide list (verified).
**Example:** A client sends `0` for "no component" and gets every planned item of every visible project.
**Rules affected:** `get_items` R1
**Answer:** bug — per BUG-1959 precedent: only `None` means "no component"; `0` → guard → 404 `Project component not found`.
**Resolution:** 🐞 BUG-2309 (pattern `falsy-zero-treated-as-missing`).

### P2. A deleted item can be planned on a component — 🐞 BUG-2306
**Background:** Items are soft-deleted (`is_active = False`) and hidden from the catalog. A deleted item is treated as not found when edited (BUG-938) and a deleted tag cannot be newly linked (BUG-943).
**What happens today:** `POST` with a deleted item's id → 201 (verified).
**Example:** "Old bolt M8" was deleted from the catalog last month; a planner still adds it to "Conveyor" by id, and the component lists an item nobody can open.
**Rules affected:** `create_component_item` R3a
**Answer:** bug — per BUG-938 / BUG-943 precedent: a deleted item is refused as not found, 404 `Item with ID {item_id} not found`, nothing written. Rows already planned with an item deleted later stay as they are.
**Resolution:** 🐞 BUG-2306 (pattern `unvalidated-stored-reference`).

### P3. Saving an item line unchanged writes "Updated component item" — 🐞 BUG-2310
**Background:** As BUG-632 / BUG-2118.
**What happens today:** `PUT {}` or the same `qty` logs `item_updated` (verified).
**Example:** The qty dialog is saved with 5 → 5; the activity tab shows "Updated component item (qty 5)".
**Rules affected:** `update_component_item` R3
**Answer:** bug — per BUG-632 precedent: no value changed → no event.
**Resolution:** 🐞 BUG-2310 (pattern `audit-event-on-noop`).

### New items

### D1. A planned quantity can be zero, negative or too large — 🐞 BUG-2307
**Background:** `qty` is a plain `int` (column `Integer`); it plans how many units a component needs and moves no stock (Stock and money above). Negative quantities on entry were refused for stock and costs (BUG-711, BUG-1962).
**What happens today:** `qty = -3` and `qty = 0` are stored and logged (verified); `3000000000` fails at the flush (`DataError`, 500).
**Example:** A typo plans −3 bearings for "Gearbox"; the item's usage page counts the line.
**Rules affected:** `create_component_item` R4, `update_component_item` R2
**Answer:** bug — `ProjectComponentItemCreate.qty` and `ProjectComponentItemUpdate.qty` require `1 <= qty <= 2147483647` (422), nothing written; `null` on update keeps today's "unchanged". Rows already stored are not touched (decided by Claude under the reviewer's delegation (2026-11-04); plan figure only, no stock or money).
**Resolution:** 🐞 BUG-2307 (pattern `unvalidated-numeric-range`).

### D2. One item may be planned twice on one component — ✅ intended
**Background:** No unique constraint on (component, item) (item DAO Model facts); nothing consumes these rows for stock.
**What happens today:** a second row for the same item is created (verified).
**Answer:** intended — two lines may plan the same item for different uses; no stock or money follows (decided by Claude under the reviewer's delegation (2026-11-04)). Rule `create_component_item` R5 ✅.

Checked and **not** violated: **HR-1 … HR-3, HR-8** — no names, no `LIKE`. **HR-4** — the table has no soft delete; deleted items P2; deleted project BUG-1278. **HR-6** — one component's list is `id` order (BUG-1276), and the workspace-wide list is base `id` order (BUG-100): the same order, as the rows have no name. **HR-9** — no audit stamps on the table; events P3. **HR-10** — no stock or money moves (Stock and money). **HR-15** — no money. **HR-16** — component through the guard; item BUG-1012; `ProjectComponentItemUpdate` has only `qty`, so neither the component nor the item can be changed after creation.

**Permission checks:** only `require_component_access`. Any member who may open the project may plan, change and remove items. Recorded for the permissions feature, not asked.

## Overview
`ProjectComponentItemService` is the transaction boundary for the planned items of a project component. The `/project-component-items/` endpoints call it. It checks access through `ProjectManager`, writes through the base DAO, logs one project event per write, and commits.

**Callables:** 7 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** the endpoints' 404 `Project component item not found` for `None` / `False`; `limit` bounds (BUG-1277); schema validation (400 today, BUG-461).

### Transaction rules (I-TC)
As N-TC1–N-TC6 of `project_component_note_service.spec.md`, for `create_component_item`, `update_component_item`, `delete_component_item`, and the reads `get_items`, `get_by_id`.

**Facts for the test designer**
- Import: `from app.services.project_component_item_service import ProjectComponentItemService, project_component_item_service`.
- Guard errors: project manager `require_component_access` R1–R4.
- Event metadata: service passes `{"item_id": <catalog item id>, "qty": str(qty)}` (create, update) or `{"item_id"}` (delete); `log_for_component` R2 adds `component_id`, `component_name`. `item_id` in metadata is the catalog item's id, not the row's.
- Build an item: `Item(workspace_id, name, name_normalized, unit)`; deleted: `is_active=False`.
- Schemas (gap 1): `from app.schemas.project_component_item import ProjectComponentItemCreate, ProjectComponentItemUpdate`. Models: `app.models.project_component_item.ProjectComponentItem`, `app.models.item.Item`.

**Notes for the test designer**
- Session, commits, setup as `department_service.spec.md` Notes.
- **BUG-1012:** another workspace's item and an unknown id → intended 404 `Item with ID {item_id} not found`, nothing written; today 201 / `IntegrityError` → strict xfail.
- **BUG-2308:** as note service Notes (BUG-2293), with item rows.

## Not specified
- `project_component_item_service` — module-level singleton.

---

## `ProjectComponentItemService._guard_component(db, component_id, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal

**Rules:**
- **R1.** As note service `_guard_component` R1.

---

## `ProjectComponentItemService._filter_accessible_items(db, items, workspace_id, user_id)`
**Shape:** helper · **Persistence:** reads · **Visibility:** internal (used by: `get_items` without a component)

**Rules:**
- **R1.** As note service `_filter_accessible_notes` R1, R2, R4.
- **R2.** [BUG-1278] A row whose project is soft-deleted is dropped. *(Today: kept.)*

---

## `ProjectComponentItemService.get_items(db, workspace_id, user_id, project_component_id=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /project-component-items/`)

**Rules:**
- **R1.** A truthy `project_component_id` → guard first (403/404), then item DAO `get_by_component` R1–R7 (BUG-1276 order). [BUG-2309] (P1) `0` too → 404 `Project component not found`. *(Today: workspace-wide list, verified.)*
- **R2.** Without a component: the workspace's rows (base `get_by_workspace`, `id` order per BUG-100), then `_filter_accessible_items`.
- **R3.** [BUG-1278] R2 leaves out rows of deleted projects.
- **R4.** [BUG-2308] (HR-5) R2's filter is applied before `skip` / `limit`; statements do not grow with the rows. *(Today: after paging.)*
- **R5.** Read only (I-TC6).
- **R6.** Rows under a component in another workspace (invalid data) are skipped in R2.
- **R7.** Paging defaults `skip=0`, `limit=100`; `limit=0` → `[]`; negative → `DataError` (endpoint bound BUG-1277).

---

## `ProjectComponentItemService.get_by_id(db, item_id, workspace_id, user_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /project-component-items/{id}/`; update, delete)

`item_id` here is the **row's** id.

**Rules:**
- **R1.** Unknown id, `0`, another workspace's → `None` (endpoint 404 `Project component item not found`); no access check.
- **R2.** Found → guard on its component (403 / 404; deleted project → 404, BUG-1278); passed → the row.
- **R3.** Read only.

---

## `ProjectComponentItemService.create_component_item(db, item_in, workspace_id, user_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /project-component-items/`, 201)

**Rules:**
- **R1.** Guard on `item_in.project_component_id` first; refused → its `HTTPException`, nothing saved (I-TC3). Deleted project → 404 (BUG-1278; today created).
- **R2.** The guard runs before the item check: a private project's component with a foreign item answers 403.
- **R3.** [BUG-1012] (HR-16) The item must be an item of `workspace_id`: another workspace's or an unknown id → `HTTPException(404, "Item with ID {item_id} not found")`, nothing written. *(Today: another workspace's item stored, 201; unknown id → `IntegrityError` at the flush, verified.)*
- **R3a.** [BUG-2306] (P2) A deleted item (`is_active = False`) → the same 404, nothing written. *(Today: stored, verified.)* An inactive item is the deleted state; there is no other.
- **R4.** [BUG-2307] (D1) `qty` must be `1 … 2147483647`, else 422 from `ProjectComponentItemCreate`, nothing written. *(Today: `0` and negatives stored; above the range `DataError` at the flush.)*
- **R5.** One row: `workspace_id`, `project_component_id`, `item_id`, `qty`. The same item may already be on the component ✅ (D2). No stock, ledger or money row is written.
- **R6.** One event `item_added`, description `Added item to component (qty <qty>)`, performer `user_id`, metadata Facts.
- **R7.** Committed and re-read (I-TC1, I-TC2); failures I-TC3–I-TC5.

---

## `ProjectComponentItemService.update_component_item(db, item_id, item_in, workspace_id, user_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /project-component-items/{id}/`)

**Rules:**
- **R1.** Found as `get_by_id` R1, R2; not found → `None`, nothing written, no commit or rollback; guard refusal → rolled back.
- **R2.** Only `qty` can change; `null` or omitted → unchanged. [BUG-2307] a sent `qty` outside `1 … 2147483647` → 422, nothing written. *(Today: any int stored; above the range `DataError`, rolled back, verified.)*
- **R3.** One event `item_updated`, `Updated component item (qty <qty>)`, metadata Facts. [BUG-2310] (P3) Only when `qty` changes value. *(Today: always, verified.)*
- **R4.** Committed, re-read (I-TC1, I-TC2); failures I-TC3–I-TC5. No stock or money changes.

---

## `ProjectComponentItemService.delete_component_item(db, item_id, workspace_id, user_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /project-component-items/{id}/`, 204)

**Rules:**
- **R1.** Found as `get_by_id`; not found → `False`, nothing written, no commit or rollback.
- **R2.** One event `item_removed`, `Removed item from component`, metadata `{"item_id", "component_id", "component_name"}`; then the row is hard-deleted. Nothing references the row; nothing blocks; no stock or money changes.
- **R3.** Committed, `True`, no re-read; failures I-TC3, I-TC4.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–17 | guard | `_guard_component` R1 |
| 21–26 | component not in workspace → skip | `_filter_accessible_items` R1; `get_items` R6 |
| 27–33 | project found and accessible (raw, BUG-1278) | `_filter_accessible_items` R1, R2 |
| 45 | `if project_component_id:` (0, BUG-2309) | `get_items` R1 |
| 46–53 | guard; by component | `get_items` R1 |
| 55–58 | workspace page; filter after (BUG-2308) | `get_items` R2–R4, R7 |
| 61–65 | not found → `None` | `get_by_id` R1 |
| 66–67 | guard; return | `get_by_id` R2 |
| 77–79 | guard | `create_component_item` R1, R2 |
| 80–82 | dump; create (no item check BUG-1012, BUG-2306; no qty bound BUG-2307) | `create_component_item` R3–R5 |
| 83–91 | event | `create_component_item` R6 |
| 92–97 | commit, refresh / rollback | `create_component_item` R7 |
| 108–110 | find; `None` | `update_component_item` R1 |
| 111 | base update (`exclude_none`) | `update_component_item` R2 |
| 112–120 | event always (BUG-2310) | `update_component_item` R3 |
| 121–126 | commit, refresh / rollback | `update_component_item` R4 |
| 132–134 | find; `False` | `delete_component_item` R1 |
| 135–144 | event; remove | `delete_component_item` R2 |
| 145–149 | commit, `True` / rollback | `delete_component_item` R3 |
| 152 | singleton | Not specified |

## Gap log
G1 (`project_component_item_service.cases.md` gap 1) — Fact — Facts: `app.schemas.project_component_item` (`ProjectComponentItemCreate`, `ProjectComponentItemUpdate`).
