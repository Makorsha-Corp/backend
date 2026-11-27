# Spec — `app/dao/project_component_activity_event.py`

> **Status:** APPROVED (2026-11-01; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-01.** **Owner's answer (Q1):** bug: a component with history is refused, listing what blocks it (precedent `item_manager` R9b; HR-16 generic entry). BUG-1196, frontend part BUG-1197. **Delegated:** Q2 bug, add `GET /project-components/{id}/activity/` with HR-7 limits, decided by Claude under the reviewer's delegation (2026-11-01): BUG-1198. None of Q2 is the owner's own answer. **Claude's reading, not the owner's words:** which rows count as history, the Q1 Resolution. Neither rule tags a rule of this DAO: they belong to the project component service.

> **Family.** One of eight tiny event DAOs (`expense_order_event`, `transfer_order_event`, `work_order_event`, `project_event`, `purchase_order_event`, `sales_order_event`, `project_component_activity_event`, `payment_transaction_event`). They share one shape: one read of one parent's log, written elsewhere, with no write of its own. The shared behaviour was verified once, looped over all eight. **This module differs from the family in two ways:** it pages (`skip`, `limit`), and it has no live reader until BUG-1198.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Physical row order and collation order are **not** an order: a missing `ORDER BY` is a bug, and no order recipe is called deterministic unless it ends in `id`.
> 2. Event logs are history (the owner's ledger ruling, 2026-10-30): the state of a soft-deleted parent never hides or trims them.
> 3. Raw lookups stay raw (HR-4 scope; base DAO spec). This DAO adds no soft-delete column of its own.
> 4. HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** once for the whole family (throwaway scripts `ev_1.py` … `ev_3.py` with the harness `ev_h.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\evdao\`, each transaction rolled back against `marker_test`; nothing committed): for all eight modules the table's columns, nullability, defaults, constraints, indexes, no trigger, no table references it; the order with a timestamp tie, also after the lower-`id` tied row was updated; another parent; right parent with another workspace; a row of workspace B on a parent of A; unknown id and `0`; a positional call; an unflushed row; metadata unset and `None`; `performer`; a default `created_at`; one query, no join, no `FOR UPDATE`; 158 rows. Also run: default and caps (101 rows → 100; `limit=1000` → 101); `limit=0`; `skip` at and past the end; negative paging errors; windows partition the rows; `ProjectComponentActivityManager.list_events` on a real and an unknown id; the hard delete with a linked work order (`project_component_dao.remove`, with `log_for_component` before it, not through the service). **BUG-1192:** `create_pending_attachment` + `confirm_attachment` with B's component from A (`model_construct`, Cloudinary patched). Also run (`ev_4.py`): today's result of the delete with a task, a misc cost, an item line and a ledger row. **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of the bugs.

## Review
> All answered; applied 2026-11-01.

Checked and **not** a new line here: **HR-6** on `get_by_component` — ordered by `created_at` descending, then `id` descending, before paging. **HR-5, HR-8** — one query with equality filters, no `LIKE`. **HR-7** — `get_by_component` has no endpoint yet; the endpoint of BUG-1198 enforces it. **HR-4** — the table has no soft-delete column; the parent's state is standing decision 2. **HR-9, HR-10** — the DAO writes nothing and takes no lock. **HR-15** — no money is computed. **HR-1, HR-2, HR-3** — `event_type` is written by code, never typed by a user. **HR-16** — no response of this DAO is affected, see R2; the write side is BUG-1192 (FU-1).

### New questions

### Q1. Deleting a project component erases its activity log, work order entries included — OWNER — 🐞 BUG-1196
**Background:** A project component has no soft delete: `DELETE /project-components/{id}/` removes the row, and the database removes its activity log with it. That log holds attachments and, from work orders, `work_order_item_used` and `work_order_completed`. The project's own log gets a `component_deleted` row, which survives. The owner ruled that a ledger is history; that ruling did not cover a hard delete.
**What happens today:** The component's whole log is gone. A work order linked to the component does not stop the delete: the link on the work order is cleared and the order stays (verified, FU-2). A stock ledger row on the component does stop it at the database (read from the foreign key, not run). Stock: no quantity changes, but the entries saying which work order used which items on this component are lost.
**Example:** Component "Roof" has a completed work order that used 40 bolts from storage. Someone deletes "Roof". The work order now has no component, the `work_order_item_used` entry is gone, and the project log says only `Deleted component "Roof"`.
**Rules affected:** `get_by_component` R4
**Suggested answer:** `bug — a component with work order entries in its log cannot be deleted: refuse the delete and list what blocks it`, because the code keeps stock history (the ledger foreign key refuses) and these entries are the same history in words. Alternative: `intended — the project log's component_deleted row is record enough`.
**Answer:** bug — a component with history is refused, listing what blocks it (precedent `item_manager` R9b; HR-16 generic entry) (owner, 2026-11-01)
**Resolution:** BUG-1196 (pattern `delete-ignores-dependents`); showing the list is BUG-1197 (`refusal-reason-not-shown`). `ProjectComponentService.delete_component` refuses with 400, message `Component has history`, and `errors` = the blocker list, after the access check and before anything is written, so no `component_deleted` row. Blockers, each `{"type", "id"}`, one per row, sorted by type in this order and then `id` ascending: `work_order` (any state, a soft-deleted order included), `ledger_entry` (`project_component_item_ledger`), `component_item` (`project_component_items`), `task` (`project_component_tasks`), `misc_cost` (`miscellaneous_project_costs`), `activity_event` (a log row other than `attachment_added` / `attachment_removed`). Any such row of another workspace is covered by one `{"type": "other_workspace"}`, no id, last (HR-16). The list is never empty when the refusal is raised. **Claude's reading, not the owner's words:** attachment rows of the log do not block, because a user can never clear them, so one attachment would block the component forever; they go with the component. Items, tasks and misc costs count though they are not history in the strict sense: items and tasks make the delete a database error today, and a misc cost is silently unlinked (verified, `ev_4.py`), and a user can clear all three. Rules: the project component service's spec (FU-2). `get_by_component` R4 ✅ holds for the components that may still be deleted.

### Q2. The component activity log is written but nothing can read it — 🐞 BUG-1198
**Background:** Attachments and work orders write to this log. `get_by_component` is its only reader, through `ProjectComponentActivityManager.list_events`, which pages and adds the performer's profile, the same shape as the machine activity log. Nothing calls `list_events`: no service, no endpoint, and the frontend has no such request.
**What happens today:** Every entry is stored and no user can ever see one. The method's paging has never been used.
**Example:** A work order uses 40 bolts on component "Roof". The row is stored, but no page or API shows it.
**Rules affected:** `get_by_component` R1–R9
**Suggested answer:** `bug — add GET /project-components/{id}/activity/ with skip >= 0 and 1 <= limit <= 1000 (HR-7), the access check of the component, and the machine panel's shape`: the manager method is ready and the log is being written on purpose. Alternative: `remove` for `get_by_component` and `list_events`, which leaves a log nobody can read.
**Answer:** bug — add `GET /project-components/{id}/activity/` with HR-7 limits
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-01). BUG-1198 (pattern `log-without-reader`). New endpoint: `skip >= 0` default 0, `1 <= limit <= 1000` default 100 (HR-7; below 1 is 422), the component access check first (`require_component_access`: 404 `Project component not found`, 403 for a project the user cannot access), then `ProjectComponentActivityManager.list_events`. Response items as the machine panel: `id`, `workspace_id`, `project_component_id`, `event_type`, `description`, `metadata`, `performed_by`, `performer_name`, `created_at`. No date or type filter: none was asked for. No frontend panel was decided. Rules: `get_by_component` R1–R9 stay; the endpoint's rule belongs to the endpoint and service review (FU-3).

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **`ProjectComponentActivityManager.log_event`** (`app/managers/project_component_activity_manager.py`) | **BUG-1192 (HR-16), logged:** it stores any id under the caller's workspace. Signing and confirming an attachment on another workspace's project component wrote `attachment_added` with the caller's `workspace_id` (verified at manager level). The row shows nowhere: the caller gets 404 and the owner of the project component is filtered out by R2. The manager's spec must carry the rule and the tag: 404 `Project component with ID <id> not found`, nothing written. | BUG-1091 note "other types not checked" |
| FU-2 | **Project component service** (`delete_component`) | **BUG-1196 and BUG-1197, logged (Q1):** the rule and the tag belong to that spec. Today the delete clears `work_orders.project_component_id` on linked work orders (verified on a soft-deleted order; the code treats a live one the same) and on misc costs (verified): SQLAlchemy nulls the backrefs, so the foreign key never refuses. Items, tasks and ledger rows give `IntegrityError`, also nulled first (verified): a 500 today. | Q1, `ev_3.py`, `ev_4.py` |
| FU-3 | **Project component endpoint and service** (`app/api/v1/endpoints/project_components.py`) | **BUG-1198, logged (Q2, delegated):** the endpoint in the Q2 Resolution, with a new response schema. | Q2 |

## Overview
`ProjectComponentActivityEventDAO` reads `project_component_activity_events`, the activity log of a project component: one row per thing that happened to it. It has one read: one project component's log, newest first. All writes go through `ProjectComponentActivityManager.log_event`, not this DAO; attachments reach it too (`AttachmentManager._log_attachment_entity_events`). It is meant to protect workspace isolation. It never writes, never commits and takes no lock.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none. No method reads the clock.
**Integration-only behavior:** none.

**Model facts (table `project_component_activity_events`, class `app.models.project_component_activity_event.ProjectComponentActivityEvent`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `project_component_id` | Integer NOT NULL, FK `project_components.id` ON DELETE CASCADE | — |
| `event_type` | String(50) NOT NULL, no check constraint | — |
| `description` | Text NOT NULL | — |
| `metadata` (attribute `metadata_json`) | generic `JSON` (Postgres `json`), nullable | `NULL` |
| `performed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_at` | `timestamp without time zone` NOT NULL, naive UTC by convention | Python default `utcnow`, no database default |

- No soft-delete column, no `updated_at`. Indexes: primary key, `ix_project_component_activity_events_project_component_id`, `ix_project_component_activity_events_workspace_id`. No unique or check constraint, no trigger; no table references this one.
- "Append-only" is a convention: nothing in the database enforces it, and no application code updates or deletes these rows.
- `project_component_id` and `workspace_id` of a row are independent: the database does not require the project component to belong to the row's workspace.
- Metadata set to Python `None` explicitly is stored as JSON `null`; left unset it is SQL `NULL`. Both read back as `None`.
- Relationship: `performer` (lazy, `Profile`).

**Notes for the test designer:**
- Use the module singleton `project_component_activity_event_dao` (`from app.dao.project_component_activity_event import project_component_activity_event_dao`). Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py`. Parents built directly (add + flush): `Factory(workspace_id, name, abbreviation)`, `Project(workspace_id, factory_id, name, description)`, then `ProjectComponent(workspace_id, project_id, name)`. Events: `ProjectComponentActivityEvent(workspace_id, project_component_id, event_type, description, created_at, metadata_json)`. The session runs with `autoflush=False`: flush before calling the DAO (base spec `get` R5).
- Always give `created_at` explicitly, with distinct values unless the case is about a tie. Column defaults cannot be frozen by patching `utcnow`.
- Test the shape once here; the base behaviour is in `tests/unit/dao/base.spec.md` and is not repeated.

## Not specified
- `project_component_activity_event_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — not overridden and with **no caller on this DAO**: the row is added directly by the writer. The base spec covers them.

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) does not mark `get_by_component` as possibly unused.

---

## `ProjectComponentActivityEventDAO.get_by_component(db, *, project_component_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectComponentActivityManager.list_events`, which **nothing calls today**; `GET /project-components/{id}/activity/` will, BUG-1198)

**Purpose:** One project component's activity log, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `project_component_id` | int | equality on the row's `project_component_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |
| `skip` | int, default `0` | rows to skip; not validated |
| `limit` | int, default `100` | max rows; not validated |

**Returns:** a `list` of `ProjectComponentActivityEvent` instances (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `project_component_id` and that `workspace_id`, of every event type. Rows of another project component are never returned.
- **R2.** Workspace isolation follows the row: a call with the right project component id and another workspace returns `[]`. Only the row's own `workspace_id` is compared, not the project component's. A row with `workspace_id` = B on a project component of workspace A is returned for B and not for A. (HR-16: that row is invalid data, and it cannot reach a response, because nothing reads this log today, and the endpoint of BUG-1198 answers 404 for a component of another workspace before this method runs. The write side is BUG-1192.)
- **R3.** An unknown project component id, `project_component_id=0`, an unknown workspace, or a project component with no events returns `[]`.
- **R4.** The project component has no soft-delete column. A hard delete (`ProjectComponentService.delete_component`) removes its rows too, through `ON DELETE CASCADE`: the call then returns `[]`. ✅ (Q1: only a component without blockers can be deleted, BUG-1196, a rule of the service.)
- **R5.** Rows are ordered by `created_at` descending, then `id` descending, before `skip` / `limit`. Given 4 Mar, 5 Mar and two rows on 6 Mar, the result is the higher `id` of 6 Mar, the lower `id` of 6 Mar, 5 Mar, 4 Mar; updating the lower tied row does not change that.
- **R6.** At most `limit` rows are returned after skipping `skip`; with the defaults at most 100: given 101 rows, exactly 100; with `limit=1000`, 101. Consecutive windows partition the rows with no repeats or gaps.
- **R7.** `limit=0` returns `[]`; `skip` at or past the number of matching rows returns `[]`.
- **R8.** A negative `limit` or `skip` makes Postgres reject the query (see Errors).
- **R9.** Rows come back as stored: `metadata_json` is the stored value, `None` for both SQL `NULL` and JSON `null`, and `performer` gives the profile, or `None` when `performed_by` is `None`. The call changes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| negative `limit` | `sqlalchemy.exc.DataError`; `.orig.pgcode == "2201W"` | `LIMIT must not be negative` |
| negative `skip` | `sqlalchemy.exc.DataError`; `.orig.pgcode == "2201X"` | `OFFSET must not be negative` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13–22 | keyword-only parameters; defaults `skip=0`, `limit=100` | Notes for the test designer; `get_by_component` R6 |
| 24–27 | parent AND workspace; no join to the parent | `get_by_component` R1, R2, R3, R4 |
| 28 | `created_at` desc, `id` desc | `get_by_component` R5 |
| 29–30 | offset / limit; `limit=0`; negative values; empty / many | `get_by_component` R6, R7, R8, Errors |
| 31 | rows as stored | `get_by_component` R9 |
| 35 | module singleton | Not specified |
