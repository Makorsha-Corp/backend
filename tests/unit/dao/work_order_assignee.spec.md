# Spec — `app/dao/work_order_assignee.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092
> **Revision 2026-11-04:** FU-1 (a) answered by the owner (2026-11-04), OQ-6: removing a member takes them off open work orders' assignees, with an event; completed orders keep their record. The change belongs in `WorkspaceManager.remove_member_from_workspace` (BUG-1883), not in this DAO; no rule of this DAO changes.

> **Review round 2026-11-03.** No owner answer in this round. **Delegated:** P1 and P2 accepted as suggested, decided by Claude under the reviewer's delegation (2026-11-03). None of them is the owner's own answer. One matter touching work orders is routed to the workspace manager's review as an **OWNER** item (FU-1 (a)); it is not a rule of this DAO and does not hold this spec.

> **Shared with `work_order_completer`.** `WorkOrderAssigneeDAO` and `WorkOrderCompleterDAO` are one shape: the same three methods on the same lines over two tables of the same shape (`work_order_assignees`, `work_order_completers`). Everything here applies to both; `tests/unit/dao/work_order_completer.spec.md` states only what differs. The checks below ran on both. Base behaviour is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data. Logs are history.
>
> **Verified by running** (throwaway script `v_wo.py` with the harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attdao\`, looped over both DAOs, each transaction rolled back against `marker_test`; nothing committed; catalog facts from `cat1.py`): an order with no rows; `replace_for_order` with a repeated user, the same list again (new row ids), a shorter list, `[]`, another order untouched, another workspace's call, a row of workspace B on the order kept and then colliding with a new row (23505), an unknown user and order (23503, savepoint rolled back), `[]` on an unknown order, any profile accepted, a write under another workspace on an order of A, inside a rolled-back savepoint, a loaded `assignee_links` collection left stale until expired; order by `id` under a forced sequential scan after an update; the batch read with a repeated id, an unknown id, `[]` (no query), another workspace; one statement with `ORDER BY`; a soft-deleted order; deleting a profile; a positional call. **Read, not run:** the callers in `app/managers/work_order_manager.py` and `app/services/work_order_service.py`. **Not run:** anything over HTTP; two concurrent transactions.

## Review
> All answered; applied 2026-11-03.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | Saving the same people again deletes their rows and writes new ones | intended — the rows carry no stamp, and the new rows keep the order given | Claude, delegated |
| P2 | The people of a deleted work order are still read here | intended — raw reads; the caller names the order | Claude, delegated |

No house-rule violations.

### House-rule violations — applied automatically
None.

Checked and **not** a new line here: **HR-6** — both reads order by `id` ascending, which is the order the names were given at the last save (R of each). **HR-9** — P1. **HR-10** — the save is a delete-then-insert on rows with no money, stock or approval; the work order manager owns the order's state checks. **HR-4** — no soft-delete column; the order's state is P2. **HR-16** — every method filters or writes the given `workspace_id`; the profile is not checked (R6 of `replace_for_order`), the manager passes only active members of the order's workspace (`resolve_worker_text_to_members` over `load_active_member_lookups`). **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-1, HR-2, HR-3, HR-15** — no text or money.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. Saving the same people again rewrites their rows — ✅ intended
**Background:** `replace_for_order` deletes every row of the order and inserts one per person given. For tag links and section assignments this was ruled a bug (BUG-870, BUG-909, BUG-934), because those rows carry `assigned_by` / `assigned_at` stamps and counters that a re-save falsified (HR-9). These tables have only `id`, `workspace_id`, `work_order_id`, `user_id`.
**What happens today:** Saving `[Rahim, Karim]` twice leaves two rows with new ids; nothing else differs. The reads order by `id`, so the people come back in the order of the last save. (Verified: ids `685–687` became `688–690`.)
**Example:** A work order's "Assigned to" says "Karim, Rahim". It is saved again unchanged: the planned workers still read Karim, Rahim.
**Rules affected:** `replace_for_order` R1, R2
**Answer:** intended — no stamp or counter is falsified, and rewriting is what keeps the order given; HR-9 does not apply
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged. Rules: `replace_for_order` R1 ✅, R2 ✅.

### P2. The people of a deleted work order are still read here — ✅ intended
**Background:** Work orders are soft-deleted. The approver DAOs of the same orders kept their reads raw: the caller names the order, and hiding a deleted order is the work order manager's (work order approver DAO, FU-1 (b)).
**What happens today:** Both reads return the rows of a soft-deleted order. (Verified.)
**Example:** WO-2026-014 is deleted. The batch read for a page that still holds it returns its two planned workers.
**Rules affected:** `get_user_ids_by_orders` R5, `get_user_ids_by_order` R3
**Answer:** intended — per the work order approver DAO precedent: raw reads
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged. Rules: `get_user_ids_by_orders` R5 ✅, `get_user_ids_by_order` R3 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Workspace manager** (`remove_member_from_workspace`) and **work order manager** | (a) **OWNER, order workflow:** a member removed from the workspace stays a planned worker (`work_order_assignees`) of open work orders; nothing touches these rows. BUG-1201 (approvers) and BUG-1280 (project members) removed such people on leaving. Whether planned workers follow is a work order question for the owner; completers are a record of who did the work and should stay (logs are history). **Answered by the owner (2026-11-04), OQ-6:** removing a member deletes their assignee rows on the workspace's open work orders (`DRAFT`, `IN_PROGRESS`), with one event per order; `COMPLETED` and `VOIDED` orders keep their rows, and completers are never touched — 🐞 BUG-1883, for the workspace manager spec. (b) The `assignee_links` / `completer_links` relationships on `WorkOrder` are read nowhere in `app/`; after `replace_for_order` a collection already loaded in the session stays stale until expired (R7). | reading the callers |

## Overview
`WorkOrderAssigneeDAO` keeps `work_order_assignees`, the planned workers of a work order, matched from its free-text "Assigned to" to workspace members. Callers: `WorkOrderManager._sync_assignees_from_text` (`replace_for_order`, on create and update), `WorkOrderManager` start and create metadata (`get_user_ids_by_order`), `WorkOrderService` list responses (`get_user_ids_by_orders`, per workspace). It is meant to protect workspace isolation through the row's `workspace_id`. It flushes, never commits, and takes no lock.

**Callables:** 3 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** none.

**Model facts (table `work_order_assignees`, class `app.models.work_order_assignee.WorkOrderAssignee`):**
| Column | Type / constraint | Default |
|---|---|---|
| `id` | Integer PK | sequence |
| `workspace_id` | Integer NOT NULL, FK `workspaces.id` ON DELETE CASCADE | — |
| `work_order_id` | Integer NOT NULL, FK `work_orders.id` ON DELETE CASCADE | — |
| `user_id` | Integer NOT NULL, FK `profiles.id` ON DELETE CASCADE | — |

- Unique constraint `uq_wo_assignee_wo_user` on `(work_order_id, user_id)` — **without** `workspace_id`. Indexes on `workspace_id`, `work_order_id`, `user_id`. No trigger. Deleting the order, the profile or the workspace deletes the rows.
- `WorkOrder` needs `workspace_id`, a unique `work_order_number` per workspace (`uq_wo_workspace_number`), `title`, `factory_id`, `work_order_type_id`; `WorkOrderType` needs `workspace_id`, `name`.

**Notes for the test designer:**
- Use the singletons `work_order_assignee_dao` / `work_order_completer_dao`; parametrize every case over both. Every parameter after `db` is keyword-only.
- Give each work order its own `work_order_number`.
- For R7, load `wo.assignee_links` (or `completer_links`) before the call.

## Not specified
- `work_order_assignee_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — no caller on this DAO; base spec.

---

## `WorkOrderAssigneeDAO.get_user_ids_by_orders(db, *, work_order_ids, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderService`, once per workspace for the orders of a list page)

**Purpose:** The people of many work orders at once, as a map.

**Returns:** a `dict` from work order id to a `list` of profile ids.

**Rules:**
- **R1.** An empty list returns `{}` with no query.
- **R2.** Otherwise every id given is a key, also ids with no rows and unknown ids (→ `[]`); an id given twice is one key. Keys come in the order first given.
- **R3.** Each list holds the `user_id`s of that order's rows with that `workspace_id`, ordered by row `id` ascending (= the order of the last save).
- **R4.** Rows under another `workspace_id` are not read: asked for workspace B, an order of A maps to `[]`; a row of workspace B on an order of A (invalid data) is read for B only.
- **R5.** ✅ (P2) The order's state is not looked at: a soft-deleted order's people are returned.
- **R6.** One statement, whatever the number of ids.

**Errors:** none. **Side effects:** none

---

## `WorkOrderAssigneeDAO.get_user_ids_by_order(db, *, work_order_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkOrderManager` create and start metadata)

**Rules:**
- **R1.** Returns the `user_id`s of that order's rows with that `workspace_id`, ordered by row `id` ascending; `[]` when none, for an unknown order or `0`.
- **R2.** Rows under another `workspace_id` are not returned (as `get_user_ids_by_orders` R4).
- **R3.** ✅ (P2) The order's state is not looked at.

**Errors:** none. **Side effects:** none

---

## `WorkOrderAssigneeDAO.replace_for_order(db, *, work_order_id, workspace_id, user_ids)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `WorkOrderManager._sync_assignees_from_text`, with the active members matched from the text)

**Purpose:** Make the order's people exactly the ones given, in the order given.

**Returns:** `None`; flushed, not committed.

**Rules:**
- **R1.** ✅ (P1) Every row of that order with that `workspace_id` is deleted, then one row per distinct id in `user_ids` is inserted, in the order of first appearance: `[u3, u1, u3, u2]` reads back `[u3, u1, u2]`. Rows that stay get new ids.
- **R2.** ✅ (P1) Saving the same list again leaves the same people in the same order (with new row ids); a shorter list removes the others; `[]` removes everyone.
- **R3.** Other orders' rows are untouched. A call under another `workspace_id` deletes nothing of this workspace and writes its rows under that other workspace (invalid data; the manager passes the order's own workspace).
- **R4.** A row of the order under another `workspace_id` is not deleted; inserting the same user then raises `IntegrityError` (`UniqueViolation`, 23505, `uq_wo_assignee_wo_user`).
- **R5.** An unknown user or work order raises `IntegrityError` (pgcode `23503`) at the flush; inside a savepoint that is rolled back, the delete is undone too. An unknown order with `[]` raises nothing.
- **R6.** The profiles are not checked against the workspace: any existing profile is accepted.
- **R7.** The delete bypasses the session (`synchronize_session=False`): a `WorkOrder.assignee_links` collection loaded before the call still lists the old rows until it is expired or reloaded; a fresh query and both reads see the new rows.
- **R8.** Flushed, not committed: rolling back a savepoint restores the old rows.

**Errors:** `sqlalchemy.exc.IntegrityError` as in R4, R5.

**Side effects:** rows deleted and inserted, flushed; no event (the manager writes them).

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 10–16, 33–35, 47–49 | keyword-only parameters | Notes |
| 17–18 | `not work_order_ids` → `{}` | `get_user_ids_by_orders` R1 |
| 19 | one key per id given, `[]` each | `get_user_ids_by_orders` R2 |
| 20–28 | `IN` ids AND workspace; `ORDER BY id`; order state not read | `get_user_ids_by_orders` R3, R4, R5, R6 |
| 29–30 | loop over rows, `setdefault` | `get_user_ids_by_orders` R2, R3 |
| 36–45 | order AND workspace; `ORDER BY id` | `get_user_ids_by_order` R1, R2, R3 |
| 50–57 | bulk delete of order AND workspace, `synchronize_session=False` | `replace_for_order` R1, R3, R4, R7 |
| 58–62 | loop; `user_id in seen` → `continue` | `replace_for_order` R1 |
| 63–69 | insert per new id, profile unchecked | `replace_for_order` R1, R2, R5, R6 |
| 70 | flush, no commit | `replace_for_order` R5, R8 |
| 73 | singleton | Not specified |
