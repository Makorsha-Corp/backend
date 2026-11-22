# Spec — `app/dao/project_event.py`

> **Status:** APPROVED (no questions; nothing open)
> **Source commit:** e48a092

> **Family.** One of eight tiny event DAOs (`expense_order_event`, `transfer_order_event`, `work_order_event`, `project_event`, `purchase_order_event`, `sales_order_event`, `project_component_activity_event`, `payment_transaction_event`). They share one shape: one read of one parent's log, written elsewhere, with no write of its own. The shared behaviour was verified once, looped over all eight. This module matches the family, and its parent is soft-deleted, not hard-deleted. The method is called `get_by_project`.

> **Standing reviewer decisions applied here (not asked again):**
> 1. Physical row order and collation order are **not** an order: a missing `ORDER BY` is a bug, and no order recipe is called deterministic unless it ends in `id`.
> 2. Event logs are history (the owner's ledger ruling, 2026-10-30): the state of a soft-deleted parent never hides or trims them.
> 3. Raw lookups stay raw (HR-4 scope; base DAO spec). This DAO adds no soft-delete column of its own.
> 4. HR-16: a row linking to another workspace's row is invalid data, and no response shows another workspace's ids or names.
>
> **Verified by running** once for the whole family (throwaway scripts `ev_1.py` … `ev_3.py` with the harness `ev_h.py` in `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\evdao\`, each transaction rolled back against `marker_test`; nothing committed): for all eight modules the table's columns, nullability, defaults, constraints, indexes, no trigger, no table references it; the order with a timestamp tie, also after the lower-`id` tied row was updated; another parent; right parent with another workspace; a row of workspace B on a parent of A; unknown id and `0`; a positional call; an unflushed row; metadata unset and `None`; `performer`; a default `created_at`; one query, no join, no `FOR UPDATE`; 158 rows. Also run: the log of a soft-deleted project through `ProjectManager.list_events`, with `can_access_project` patched to true. **BUG-1192:** `create_pending_attachment` + `confirm_attachment` with B's project from A (`model_construct`, Cloudinary patched). **Not run:** anything over HTTP; two concurrent transactions; the intended behavior of the bugs.

## Review
Checked and **not** a new line here: **HR-6** on `get_by_project` — ordered by `created_at` descending, then `id` descending. **HR-5, HR-8** — one query with equality filters, no `LIKE`. **HR-7** — the method does not page. **HR-4** — the table has no soft-delete column; the parent's state is standing decision 2. **HR-9, HR-10** — the DAO writes nothing and takes no lock. **HR-15** — no money is computed. **HR-1, HR-2, HR-3** — `event_type` is written by code, never typed by a user. **HR-16** — no response of this DAO is affected, see R2; the write side is BUG-1192 (FU-1).

No questions.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **`ProjectManager.log_event`** (`app/managers/project_manager.py`) | **BUG-1192 (HR-16), logged:** it stores any id under the caller's workspace. Signing and confirming an attachment on another workspace's project wrote `attachment_added` with the caller's `workspace_id` (verified at manager level). The row shows nowhere: the caller gets 404 and the owner of the project is filtered out by R2. The manager's spec must carry the rule and the tag: 404 `Project with ID <id> not found`, nothing written. | BUG-1091 note "other types not checked" |
| FU-2 | **`ProjectManager.list_events`** | Reads one profile per event with a performer, the pattern of BUG-1141 (read, not run). This list has no paging, so a long log costs one read per entry. Not logged here: it is the manager's. | BUG-1141 |
| FU-3 | **Project endpoint** (`GET` events) | The endpoint validates stored metadata with its schema (`ProjectEventMetadata`). Whether any writer stores a value of the wrong type, which would make the whole log a 500 as in machine FU-2 (b), was not checked here. | machine FU-2 |

## Overview
`ProjectEventDAO` reads `project_events`, the activity log of a project: one row per thing that happened to it. It has one read: one project's log, newest first. All writes go through `ProjectManager.log_event` and `log_for_component`, not this DAO; attachments reach it too (`AttachmentManager._log_attachment_entity_events`). It is meant to protect workspace isolation. It never writes, never commits and takes no lock.

**Callables:** 1 specified · 2 not specified
**Externals to mock:** none. No method reads the clock.
**Integration-only behavior:** none.

**Model facts (table `project_events`, class `app.models.project_event.ProjectEvent`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `project_id` | Integer NOT NULL, FK `projects.id` ON DELETE CASCADE | — |
| `event_type` | String(50) NOT NULL, no check constraint | — |
| `description` | Text NOT NULL | — |
| `metadata` (attribute `metadata_json`) | generic `JSON` (Postgres `json`), nullable | `NULL` |
| `performed_by` | Integer nullable, FK `profiles.id` ON DELETE SET NULL | `NULL` |
| `created_at` | `timestamp without time zone` NOT NULL, naive UTC by convention | Python default `utcnow`, no database default |

- No soft-delete column, no `updated_at`. Indexes: primary key, `ix_project_events_id`, `ix_project_events_project_id`, `ix_project_events_workspace_id`. No unique or check constraint, no trigger; no table references this one.
- "Append-only" is a convention: nothing in the database enforces it, and no application code updates or deletes these rows.
- `project_id` and `workspace_id` of a row are independent: the database does not require the project to belong to the row's workspace.
- Metadata set to Python `None` explicitly is stored as JSON `null`; left unset it is SQL `NULL`. Both read back as `None`.
- Relationship: `performer` (lazy, `Profile`).

**Notes for the test designer:**
- Use the module singleton `project_event_dao` (`from app.dao.project_event import project_event_dao`). Every parameter after `db` is keyword-only (a positional call raises `TypeError`).
- Workspaces and profiles from `tests/unit/factories.py`. Parents built directly (add + flush): `Factory(workspace_id, name, abbreviation)`, then `Project(workspace_id, factory_id, name, description)`. Events: `ProjectEvent(workspace_id, project_id, event_type, description, created_at, metadata_json)`. The session runs with `autoflush=False`: flush before calling the DAO (base spec `get` R5).
- Always give `created_at` explicitly, with distinct values unless the case is about a tie. Column defaults cannot be frozen by patching `utcnow`.
- Test the shape once here; the base behaviour is in `tests/unit/dao/base.spec.md` and is not repeated.

## Not specified
- `project_event_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — not overridden and with **no caller on this DAO**: the row is added directly by the writer. The base spec covers them.

The checklist (`docs/testing/unit-test-checklist-by-layer.md`) does not mark `get_by_project` as possibly unused.

---

## `ProjectEventDAO.get_by_project(db, *, project_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectManager.list_events` ← `GET /projects/{id}/events/`, after the project access check)

**Purpose:** One project's activity log, newest first.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `db` | `Session` | open session |
| `project_id` | int | equality on the row's `project_id`; not validated |
| `workspace_id` | int | equality on the row's `workspace_id` |

**Returns:** a `list` of `ProjectEvent` instances (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `project_id` and that `workspace_id`, of every event type. Rows of another project are never returned.
- **R2.** Workspace isolation follows the row: a call with the right project id and another workspace returns `[]`. Only the row's own `workspace_id` is compared, not the project's. A row with `workspace_id` = B on a project of workspace A is returned for B and not for A. (HR-16: that row is invalid data, and it cannot reach a response: the caller answers 404 for a project of another workspace before this method runs. The write side is BUG-1192.)
- **R3.** An unknown project id, `project_id=0`, an unknown workspace, or a project with no events returns `[]`.
- **R4.** ✅ (standing decision 2) The state of the project is not looked at: the events of a soft-deleted project (`is_deleted = True`; `delete_project` leaves `is_active` as it was) are all returned. `ProjectManager.list_events` keeps answering for it too (verified with `can_access_project` patched to true).
- **R5.** Rows are ordered by `created_at` descending, then `id` descending. Given 4 Mar, 5 Mar and two rows on 6 Mar, the result is the higher `id` of 6 Mar, the lower `id` of 6 Mar, 5 Mar, 4 Mar; updating the lower tied row does not change that.
- **R6.** Every matching row is returned: no `skip`, no `limit`, no cap. Given 158 rows, 158.
- **R7.** Rows come back as stored: `metadata_json` is the stored value, `None` for both SQL `NULL` and JSON `null`, and `performer` gives the profile, or `None` when `performed_by` is `None`. The call changes nothing.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 12–15 | keyword-only parameters | Notes for the test designer |
| 17–20 | parent AND workspace; no join to the parent | `get_by_project` R1, R2, R3, R4 |
| 21 | `created_at` desc, `id` desc | `get_by_project` R5 |
| 22 | no paging: all rows, as stored | `get_by_project` R6, R7 |
| 26 | module singleton | Not specified |
