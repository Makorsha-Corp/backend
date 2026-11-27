# Spec — `app/managers/project_component_activity_manager.py`

> **Status:** APPROVED (2026-11-04; the former Q1 is a work order manager question, OQ-10, and does not block this spec)
> **Source commit:** e48a092

> **Family.** The project component twin of `app/managers/machine_activity_manager.py`, minus filters, status and field changes: `log_event` and `list_events` are the same code with `machine` read as `project_component`. The approved `tests/unit/managers/machine_activity_manager.spec.md` (`log_event`, `list_events`) was the model, and its reviewer answers are applied here as precedent. **Below:** `tests/unit/dao/project_component_activity_event.spec.md` (APPROVED; the table, `get_by_component` R1–R9), `tests/unit/dao/project_component.spec.md`, `tests/unit/dao/profile.spec.md`, `tests/unit/dao/base.spec.md` (`get`, `get_by_id_and_workspace`: raw). This spec answers that DAO's FU-1.
>
> **Read, not run.** The DAO spec ran `list_events` on a real and an unknown id, and BUG-1192 (an attachment on another workspace's component) through `log_event`; the rest is read.

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · or a question back.
> Then run the describer in `apply-review` mode.

### House-rule violations — applied automatically
- **HR-16** `log_event` R6 — the component is not checked against the workspace: a row of workspace A can be stored on a component of workspace B. Intended: 404 `Project component with ID <id> not found`, nothing written.
**Answer:** bug — per HR-16 (house rule)
**Resolution:** 🐞 BUG-1192, already logged from the DAO's FU-1; no new ID. Rules: `log_event` R6.

Checked and **not** violated: **HR-1 … HR-3** — `event_type` and `description` are composed by callers, never typed by a user. **HR-4** — neither the log nor a component has a soft-delete column. **HR-5, HR-6** — DAO `get_by_component` R5, R6 (one query, ordered `created_at` desc, `id` desc, before paging). **HR-7** — `list_events` has no endpoint yet; BUG-1198's endpoint enforces it. **HR-8** — no `LIKE`. **HR-9, HR-10** — nothing stamps or locks. **HR-11 … HR-15** — no external system, batch or money. **HR-16** on reads — `list_events` answers a foreign component exactly as an unknown one (R2), and an invalid row shows nowhere (R3).

### Precedent matches — confirm all with ok

### P1. One page of activity makes one extra read per entry — 🐞 BUG-1712
**Background:** Each entry is returned with the profile of whoever did it. `list_events` reads that profile entry by entry. The event row has a `performer` relationship, and one read by a list of ids would do.
**What happens today:** two reads (component, events) plus one per entry with a performer, the same person included each time: 100 entries by one person, 102 reads.
**Example:** The BUG-1198 activity panel opens on a component with 100 entries; the server makes 102 database reads where 3 would do. The page looks the same either way.
**Rules affected:** `list_events` R8
**Answer:** bug — per BUG-1141 precedent: performers of a page are read together, at most three reads for the whole call; the result is unchanged (precedent — confirm)
**Resolution:** confirmed — decided by Claude under the reviewer's delegation (2026-11-04), per the BUG-1141 precedent: the performers of a page are read together, at most three reads for the whole call, the result unchanged. Rules: `list_events` R8.

### Notes

### Q1. Moved to the work order manager — After BUG-1192, a work order that already points at another workspace's component can no longer be started or completed
> **Not a question for this spec** — decided by Claude under the reviewer's delegation (2026-11-04). It is about how `work_order_manager` reacts to the refusal, not about this module. That `log_event` refuses another workspace's component is settled by HR-16 / BUG-1192 (`log_event` R6, unchanged). The owner question is parked as **OQ-10** in `docs/testing/owner-questions.md`, which blocks only `work_order_manager`; see FU-1. The text below is kept as the record.

**Background:** A work order may name a project component. When it uses stock and when it is completed, it writes `work_order_item_used` / `work_order_completed` to that component's activity log through `log_event`. BUG-1016 (logged, owner 2026-10-30) stops new work orders from naming another workspace's component, but orders saved before that fix may already do so; `scripts/find_cross_workspace_rows.py` lists them (`work_orders.project_component_id -> project_components`). BUG-1192 (house rule HR-16) makes `log_event` refuse such a component with 404. For machines the same question did not arise: an order with another workspace's machine already stops at start today (machine activity manager spec, "BUG-1091 and the order workflow"). Nothing in the work order flow checks the component before `log_event` (read, not run).
**What happens today:** Such an order starts, uses stock and completes normally, and each step writes an invalid row on the other workspace's component that nobody can see.
**After BUG-1192 as worded:** starting it with stock lines, adding a stock line to it once started, and completing it all answer 404 `Project component with ID <id> not found`, and the whole step rolls back. A started order cannot have its component changed (structural fields are locked), so it stays stuck in progress until someone repairs the data.
**Example:** Work order WO-0412 of workspace A was saved last month naming component 88, which belongs to workspace B. After the fix a supervisor in A presses Complete and gets "Project component with ID 88 not found", for a component A's pages do not show; the order stays in progress.
**Rules affected:** `log_event` R6 (unchanged either way); the work order manager's `_consume_item` and `finalize_completion` (no spec yet, FU-1)
**Suggested answer:** `log_event still refuses; the work order manager writes no component entry when the order's component is not in the order's workspace, and the step goes on` — as the attachment delete in machine Q3: the invalid link is not made worse, and an order is never stuck on data the user cannot see or fix. The links themselves are repaired with the audit script's list, by hand.
**Alternatives:** (a) refuse: the step fails with the 404 until the link is cleared by a data fix. (b) refuse with a clearer message that names the work order, not the component (e.g. "Work order WO-0412 has an invalid project component; contact support").
**Answer:** moved — see OQ-10 (blocks `work_order_manager` only)

## Overview
`ProjectComponentActivityManager` is the only writer of `project_component_activity_events`, the history of a project component (attachments added or removed; work order stock use and completion), and its reader. Writers: `AttachmentManager._log_attachment_entity_events` (confirm and delete of an attachment) and `WorkOrderManager` (`_consume_item`, `finalize_completion`). `list_events` has **no caller** today: BUG-1198 adds `GET /project-components/{id}/activity/`. It is meant to protect workspace isolation and keep the log complete. It never commits, never updates or deletes a row, and takes no lock.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none. `created_at` is a Python column default (`utcnow`), not freezable by patching: assert it is set, not its value.
**Integration-only behavior:** the HTTP status of the 404; the BUG-1198 endpoint's `skip` / `limit` checks.

**Facts for the test designer**
- Import: `from app.managers.project_component_activity_manager import ProjectComponentActivityManager, project_component_activity_manager`. No-argument constructor, no per-call state. All parameters positional-or-keyword.
- Table, columns, metadata storage (`metadata` attribute `metadata_json`; JSON `null` vs SQL `NULL`), indexes: DAO spec **Model facts**. `project_component_id` and `workspace_id` FKs `ON DELETE CASCADE`; `performed_by` FK to `profiles.id` `ON DELETE SET NULL`. Nothing in the database ties the component to the row's workspace.
- `ProjectComponent` has no soft delete; deleting one is a hard delete in `ProjectComponentService` (BUG-1196). `Profile` has no workspace column and no soft delete.
- `HTTPException` is `fastapi.HTTPException`: assert `.status_code` and `.detail`.

**Notes for the test designer**
- Parents built directly (add + flush), as the DAO spec's Notes: `Factory`, `Project`, `ProjectComponent(workspace_id, project_id, name)`; events built directly for `list_events`, with explicit distinct `created_at`. `autoflush=False`: flush before calling.
- **BUG-1192:** strict xfail: W2's component, the call from W, assert the `HTTPException` and that the row count is unchanged. Today the row is stored. An unknown id today raises `IntegrityError`, so wrap that case in `with db.begin_nested():` inside `pytest.raises(...)`; also strict xfail.
- **The invalid row (`list_events` R3):** build it directly, W's `workspace_id` on W2's component.
- **Counting reads (BUG-1712, strict xfail):** a `before_cursor_execute` listener on `db.connection()`; assert the count only.
- Database errors abort the transaction: `with db.begin_nested():` inside `pytest.raises(...)`.

## Not specified
- `ProjectComponentActivityManager.__init__` — stores the two DAOs, no logic
- `project_component_activity_manager` — module-level singleton, no logic

---

## `ProjectComponentActivityManager.log_event(session, project_component_id, workspace_id, event_type, description, performed_by=None, metadata=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** public (used by: `AttachmentManager._log_attachment_entity_events`, `WorkOrderManager._consume_item`, `WorkOrderManager.finalize_completion`)

**Purpose:** Append one entry to a project component's history.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `project_component_id` | int | [BUG-1192] must be a component of the workspace |
| `workspace_id` | int | the row's workspace |
| `event_type` | str | at most 50 characters; no list of values |
| `description` | str | any text, `""` included |
| `performed_by` | int \| `None` | a profile id; `None` = no performer |
| `metadata` | `dict` \| `None` | stored whole; must be JSON-serialisable |

**Returns:** the `ProjectComponentActivityEvent`, flushed (`id` set), not committed.

**Rules:**
- **R1.** One row is added on every call, with `workspace_id`, `project_component_id`, `event_type`, `description`, `metadata_json`, `performed_by` as given. Two identical calls give two rows. No existing row changes.
- **R2.** `metadata=None` (or left out) stores JSON `null`, not SQL `NULL`; it reads back as `None`. `{}` is stored as `{}`. `performed_by` left out stores `NULL`.
- **R3.** Metadata is stored as given: nested lists and objects, `None` inside them and floats come back equal.
- **R4.** `event_type` is not checked against any list: `""` and 50 characters are stored. `description` may be `""`.
- **R5.** `created_at` is set on the row, naive.
- **R6.** [BUG-1192] (HR-16) A component that is not in the workspace (another workspace's, an unknown id, `0`, or an unknown `workspace_id`) → 404 `Project component with ID <project_component_id> not found`, nothing written, the same answer for each. *(Today: another workspace's component is stored under the caller's workspace (verified, DAO spec); the others raise `IntegrityError`, see Errors.)*
- **R7.** A component of a soft-deleted project is accepted: a log of activity is history.
- **R8.** Unknown `performed_by`, or `0` → `IntegrityError` (foreign key on `performed_by`), no row. A performer is not checked against the workspace.
- **R9.** A metadata value JSON cannot hold (`Decimal`, `datetime`) fails at the flush, no row. Every caller today passes plain values.
- **R10.** Flushed, not committed: rolling back a savepoint removes the row.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| [BUG-1192] component not in the workspace | `HTTPException` 404 | `Project component with ID <project_component_id> not found` |
| Today: unknown `project_component_id` or `0`; unknown `workspace_id` | `IntegrityError`, pgcode `23503` | — |
| unknown `performed_by` | `IntegrityError`, pgcode `23503` | — |
| `event_type` or `description` `None` | `IntegrityError`, pgcode `23502` | — |
| `event_type` over 50 characters | `DataError`, pgcode `22001` | — |
| metadata not JSON-serialisable | `StatementError`, `.orig` a `TypeError` | — |

**Side effects:** one `project_component_activity_events` row, flushed. No commit.

---

## `ProjectComponentActivityManager.list_events(session, project_component_id, workspace_id, skip=0, limit=100)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (no caller today; `GET /project-components/{id}/activity/` will call it, BUG-1198)

**Purpose:** A project component's history, one page at a time, each entry with who did it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `session` | `Session` | open session |
| `project_component_id` | int | must be a component of the workspace |
| `workspace_id` | int | caller's workspace |
| `skip`, `limit` | int, defaults `0`, `100` | not validated here |

**Returns:** a `list` of 2-tuples `(ProjectComponentActivityEvent, Profile | None)`, possibly empty.

**Rules:**
- **R1.** For a component of the workspace, the result is its events with that workspace, newest first, paged, as DAO `get_by_component` R1, R5–R7; `skip` and `limit` reach it unchanged.
- **R2.** A component of another workspace, an unknown id, `0` or a negative id → 404 `Project component with ID <id> not found`, the answers differing only in the id sent. No event is read.
- **R3.** (HR-16) A row of workspace A on a component of workspace B shows nowhere: A gets R2, and B's list leaves it out (DAO `get_by_component` R2).
- **R4.** A component of a soft-deleted project returns every event (the log is history; DAO standing decision 2).
- **R5.** A component with no events → `[]`.
- **R6.** The first element is the row as stored, `metadata_json` whole.
- **R7.** The second element is the performer's `Profile`, or `None` when `performed_by` is `None`. Two entries by one person hold the same instance.
- **R8.** [BUG-1712] All performers of a page are read together: at most three reads for the whole call, whatever the number of entries or performers; R7 unchanged. *(Today: two reads plus one per entry with a performer, a repeated person included: 100 entries by one person take 102 reads.)*
- **R9.** With the defaults at most 100 entries; `limit=0` and `skip` past the end give `[]`; a negative `limit` or `skip` raises as DAO `get_by_component` R8.
- **R10.** The call writes nothing.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| component not in the workspace | `HTTPException` 404 | `Project component with ID <project_component_id> not found` |
| negative `limit` / `skip` | `DataError` | as DAO `get_by_component` |

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 32–39 | row built from the arguments; no component check (BUG-1192) | `log_event` R1–R7 |
| 40–41 | add, flush; database refusals | `log_event` R8, R9, R10, Errors |
| 52–54 | raw lookup inside the workspace | `list_events` R2, R3, R4 |
| 55–59 | not found → 404 | `list_events` R2 |
| 60–66 | DAO page, skip / limit passed | `list_events` R1, R5, R9 |
| 67–70 | per entry: `performed_by` truthy → `profile_dao.get`; else `None`; empty / many | `list_events` R6, R7, R8 |

## Follow-ups for other reviews
> Nothing below is a rule of this manager.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Work order manager** (`app/managers/work_order_manager.py`, no spec yet) | OQ-10 (the former Q1): `_consume_item` and `finalize_completion` call `log_event` for `wo.project_component_id` with no check of its own. | Q1 → OQ-10 |
| FU-2 | **Attachment manager** (`app/managers/attachment_manager.py`, no spec yet) | BUG-1192: as machine activity manager Q3 (decided for BUG-1091), deleting an attachment whose link names another workspace's component proceeds and writes no activity row; sign and confirm refuse. Same bug, no new ID. | machine Q3 precedent |
