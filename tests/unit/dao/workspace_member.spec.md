# Spec — `app/dao/workspace_member.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** No owner answer was needed. BUG-1400 stands from a house rule; its order (`id` ascending) was decided by Claude under the reviewer's delegation (2026-11-03). One owner item found while reading the callers is not a rule of this DAO and is parked in `docs/testing/owner-questions.md` (OQ-2); it does not block this spec.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Raw lookups stay raw (HR-4 scope). HR-16: a row linking to another workspace's row is invalid data.
>
> **Verified by running** (throwaway scripts `facts.py`, `v_ws.py`, `v_plan.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns, defaults, constraints and indexes; the SQL of every method (no `ORDER BY`, no `FOR UPDATE`); statuses `active`, `suspended`, `invited`, `inactive`, `Active`, `""` through every method; another workspace, unknown ids, `0`; the unique pair; a schema create; the order of `get_workspace_members`, `get_by_workspace` and `get_by_user` under a forced sequential scan (rows came back in physical order, an updated row last); `skip` refused by `get_by_workspace`; positional arguments refused. **Not run:** anything over HTTP; the intended behaviour of BUG-1400.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| — | No question: every behaviour is either decided by a house rule or plainly intended | — | — |

Decided by a house rule: the three member lists have no sort order (BUG-1400, HR-6).

### House-rule violations — applied automatically

- **HR-6** `get_by_user` R3, `get_workspace_members` R4 (and through it `get_by_workspace` R2) — no `ORDER BY`. Verified: four members of one workspace came back `1, 2, 3, 0` (offset from the first `id`) after the first row was updated, and `2, 3, 0, 1` after the second was; three memberships of one user came back `1, 2, 0`. These lists feed the members page (`GET /workspaces/{id}/members/`), the workspace switcher (`GET /workspaces/`), mention and approval recipients and the worker-name lookup. Intended: `id` ascending (BUG-906 precedent: a membership row has no name of its own; `id` is the order people joined). A display order by the member's name, or the switcher by workspace name, belongs to `WorkspaceService` (FU-1). Decided by Claude under the reviewer's delegation (2026-11-03).
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1400 (pattern `unordered-pagination`). Rules: `get_by_user` R3, `get_workspace_members` R4, `get_by_workspace` R2.

Checked and **not** a new line here: **HR-4** — `workspace_members` has no soft-delete column; a removed member keeps the row with `status = 'inactive'`, and `workspaces` and `profiles` have no soft delete either. **HR-5** — every filter is in the query. **HR-7** — nothing here pages (`get_by_workspace` has no `skip` / `limit`). **HR-8** — no `LIKE`. **HR-9** — the table has no `updated_by`. **HR-10** — the DAO only reads; `count_active_members` feeds a plan-limit check in `WorkspaceManager` that is read-then-insert, logged with that manager (FU-2). **HR-16** — every lookup takes the workspace and the user together; nothing links two workspaces.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Workspace service** (`app/services/workspace_service.py`) | (a) `list_members` filters `status == 'active'` in Python after loading every member; fine at today's sizes, but the display order (member name, case-insensitive, then `id`) is the service's. (b) `list_user_workspaces` reads each workspace one by one; display order by workspace name is the service's. | HR-6 line |
| FU-2 | **Workspace manager** (`app/managers/workspace_manager.py`) — **OWNER, plan limits** | (a) `max_members = -1` means "unlimited" (`app/models/subscription_plan.py:24`, the seeded Enterprise plan), but the checks are `count >= max_members`, so on an Enterprise workspace **every** invitation and every add is refused with "Workspace has reached maximum member limit (-1)" (verified through `create_invitation` and `add_member_to_workspace`). (b) The limit is read-then-insert with no lock (HR-10 does not cover plan limits; owner's call). Parked as OQ-2. | `count_active_members` |
| FU-3 | **Deps** (`app/core/deps.py`, spec approved) | `has_access` is the membership gate of `get_current_workspace`; BUG-440 already covers what a non-member is told there (404, not 403). Nothing new. | `has_access` |

## Overview
`WorkspaceMemberDAO` reads `workspace_members`: one row per person per workspace, carrying the role, the position and a free-text `status` (`active` is the only value the code treats as a member; removal sets `inactive`). It is the access gate of the whole API: `get_current_workspace` asks `has_access` on every workspace request, and about thirty other call sites look up "is this user an active member, and with what role" through `get_by_workspace_and_user`. `WorkspaceManager` adds members through the inherited `create` and counts active members against the plan limit. It never commits.

**Callables:** 6 specified · 1 not specified (+ inherited, base spec)
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `workspace_members`):** `workspace_id` FK `workspaces` ON DELETE CASCADE, `user_id` FK `profiles` ON DELETE CASCADE, `invited_by_user_id` FK `profiles` ON DELETE SET NULL. `role` VARCHAR(50) NOT NULL, free text. `status` VARCHAR(50) NOT NULL, Python default `'active'`, no database default, no check. `invited_at`, `created_at`, `updated_at` NOT NULL with Python default `utcnow()` (`updated_at` also `onupdate`); `joined_at`, `left_at`, `position` (VARCHAR(255)) nullable. **Unique constraint `uq_workspace_user (workspace_id, user_id)`.** Plain indexes on `id`, `workspace_id`, `user_id`. No soft-delete column.

**Notes for the test designer:** `from app.dao.workspace_member import workspace_member_dao`. Workspaces and profiles from `tests/unit/factories.py`; build `WorkspaceMember(workspace_id, user_id, role, status)` directly and flush. Every parameter after `db` is keyword-only. **BUG-1400:** force a sequential scan (`SET LOCAL enable_indexscan = off`, `enable_bitmapscan = off`, `enable_indexonlyscan = off`), insert four rows, update the lowest `id`, flush, `db.expire_all()`; the result rests on physical order, so the case is a **non-strict** xfail with the assertion not weakened. Compare **sets** of ids everywhere else.

## Not specified
- `workspace_member_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods (`create`, `update`, `get`, `get_multi`, `remove`, `get_by_id_and_workspace`) — covered by the base spec. Specific to this model: `create` with `WorkspaceMemberCreate` works (the schema carries `workspace_id`), status defaults to `'active'`; a second row for one workspace + user raises `IntegrityError` (`UniqueViolation`, pgcode `23505`, constraint `uq_workspace_user`); a `role` over 50 characters raises `DataError` (pgcode `22001`); `update` with `WorkspaceMemberUpdate(role=…, position=None)` keeps `position` (base `update` R3).

---

## `WorkspaceMemberDAO.get_by_workspace_and_user(db, *, workspace_id, user_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `has_access`; `WorkspaceService._require_active_membership`, `update_member_role`; `WorkspaceManager.add_member_to_workspace`, `remove_member_from_workspace`, `create_invitation`; `AuthService.switch_workspace`, `reset_password_by_admin`; role checks in the order managers and endpoints — about 35 call sites)

**Purpose:** The membership row of one user in one workspace, whatever its status.

**Returns:** the `WorkspaceMember`, or `None`.

**Rules:**
- **R1.** Given a row with that `workspace_id` and that `user_id`, it is returned, whatever its `status` (`active`, `suspended`, `inactive`, any other text).
- **R2.** The same user in another workspace, or another user in this workspace, is not matched: `None`. Unknown ids and `0` give `None`, with no error.
- **R3.** At most one row can match: the pair is unique in the database (`uq_workspace_user`).

**Errors:** none of its own. Positional `workspace_id` / `user_id` raise `TypeError`.

**Side effects:** none

---

## `WorkspaceMemberDAO.get_by_user(db, *, user_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceService.list_user_workspaces` ← `GET /workspaces/`, which keeps only `active` rows)

**Purpose:** Every membership of one person, across workspaces.

**Returns:** a `list` of `WorkspaceMember` (possibly empty).

**Rules:**
- **R1.** Returns every row with that `user_id`, in every workspace, whatever its `status`.
- **R2.** An unknown user or `0` returns `[]`. No paging, no cap.
- **R3.** [BUG-1400] (HR-6) Ordered by `id` ascending. *(Today: no `ORDER BY`; verified: rows come back in physical order, an updated row last.)*

**Errors:** none of its own.

**Side effects:** none

---

## `WorkspaceMemberDAO.get_workspace_members(db, *, workspace_id, status='active')`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `get_by_workspace`; `notification_service._active_workspace_member_ids` and `approval_notification_service._active_member_ids`, as a set of recipients; `work_order_workers.load_active_member_lookups`, the worker-name lookup — all with `status="active"`)

**Purpose:** The members of one workspace, by default only the active ones.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | int | equality |
| `status` | `str \| None`, default `'active'` | `None` = no status filter; any string, `""` included, is an exact, case-sensitive match |

**Returns:** a `list` of `WorkspaceMember` (possibly empty).

**Rules:**
- **R1.** With the default, only rows with `status` exactly `'active'` are returned: `'Active'`, `'suspended'`, `'invited'`, `'inactive'` are left out.
- **R2.** With `status=None` every row of the workspace is returned, whatever its status. With any other string (`""` included) only rows with exactly that status are returned: `status=""` returns the rows whose status is the empty string, not every row.
- **R3.** Rows of another workspace never appear. An unknown workspace or `0` returns `[]`. No paging, no cap.
- **R4.** [BUG-1400] (HR-6) Ordered by `id` ascending. *(Today: no `ORDER BY`.)*

**Errors:** none of its own.

**Side effects:** none

---

## `WorkspaceMemberDAO.get_by_workspace(db, *, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceService.list_members` ← `GET /workspaces/{id}/members/`, which filters `active` in Python unless `include_inactive`)

**Purpose:** Every member of one workspace, whatever the status. Replaces `BaseDAO.get_by_workspace`.

**Rules:**
- **R1.** Returns what `get_workspace_members(status=None)` returns: every row of the workspace, whatever its status (`get_workspace_members` R2, R3). No paging and no cap.
- **R2.** [BUG-1400] Ordered by `id` ascending, as `get_workspace_members` R4. This method replaces the base one, so BUG-100's fix in `app/dao/base.py` does not reach it.
- **R3.** It takes no `skip` / `limit`: passing either raises `TypeError` (unlike the base method it replaces).

**Errors:** `TypeError` for `skip` / `limit` or positional arguments.

**Side effects:** none

---

## `WorkspaceMemberDAO.count_active_members(db, *, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `WorkspaceManager.add_member_to_workspace`, `create_invitation`, against the plan's `max_members`)

**Purpose:** How many people hold an active seat in the workspace.

**Returns:** `int`.

**Rules:**
- **R1.** Counts the rows of the workspace whose `status` is exactly `'active'` (same set as `get_workspace_members` R1); the owner's row counts like any other.
- **R2.** Rows of another workspace are not counted. An unknown workspace, `0`, or a workspace with no active member gives `0`.

**Errors:** none of its own.

**Side effects:** none

---

## `WorkspaceMemberDAO.has_access(db, *, user_id, workspace_id)`
**Shape:** compute
**Persistence:** reads
**Visibility:** public (used by: `get_current_workspace` in `app/core/deps.py`, for every non-platform-admin request with an `X-Workspace-ID`)

**Purpose:** Whether the user is an active member of the workspace.

**Returns:** `bool`.

**Rules:**
- **R1.** `True` exactly when `get_by_workspace_and_user` finds a row and its `status` is exactly `'active'`.
- **R2.** `False` when there is no row (unknown user, unknown workspace, `0`, a member of another workspace only), and when the row's status is anything else (`'Active'`, `'suspended'`, `'invited'`, `'inactive'`, `""`).

**Errors:** none of its own.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13–24 | workspace AND user; `.first()` row / `None`; unique pair | `get_by_workspace_and_user` R1, R2, R3 |
| 26–32 | `user_id` only; no `ORDER BY` (BUG-1400) | `get_by_user` R1, R2, R3 |
| 35, 40–41 | `status` default `'active'`; `is not None` → filter / `None` → none; `""` filters | `get_workspace_members` R1, R2 |
| 38, 43 | workspace filter; no `ORDER BY` (BUG-1400) | `get_workspace_members` R3, R4 |
| 45–47 | delegates with `status=None`; no `skip` / `limit` | `get_by_workspace` R1, R2, R3 |
| 49–58 | workspace AND `status == 'active'`; count | `count_active_members` R1, R2 |
| 64–67 | row found / not; status `== 'active'` / other | `has_access` R1, R2 |
| 70 | module singleton | Not specified |
