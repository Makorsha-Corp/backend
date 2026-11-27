# Spec — `app/dao/project_member.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** Q1 accepted as pre-filled, decided by Claude under the reviewer's delegation (2026-11-02). It is not the owner's own answer. BUG-1274 stands from the house rule. BUG-1280's rule belongs to the workspace manager, so no rule here carries that tag: these reads stay raw.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. Things of a soft-deleted parent are hidden. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v3.py`, `v5.py`, `v6.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; order by `assigned_at`; a tie, which swapped only under a forced sequential scan; 101 members; unknown ids; a stranger; another workspace; the unique constraint across workspaces; the naive default `assigned_at`; a member removed through `remove_member_from_workspace`; a soft-deleted project through `list_members`, `add_member`, `remove_member`. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of the bugs below.

## Review
> All answered; applied 2026-11-02.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | Someone who left the workspace stays on the project | bug — taken off its projects (BUG-1280) | Claude, delegated |

Decided by a house rule: members with one stamp come back in no fixed order (BUG-1274, HR-6).

### House-rule violations — applied automatically

- **HR-6** `get_by_project` R4 — ordered by `assigned_at` alone. Verified under a forced sequential scan: two members with one stamp swapped once the lower `id` was updated. Ties happen when several people are added quickly (BUG-1200's count: 18 to 27 of 30 stamps repeated on this machine). Intended: `assigned_at` ascending, then `id` ascending.
**Answer:** bug — per HR-6 (house rule)
**Resolution:** BUG-1274 (pattern `tied-timestamp-no-tiebreak`). Rules: `get_by_project` R4.

Checked and **not** a new line here: **HR-6** on `get_by_project_and_user` — no `ORDER BY`, but `uq_project_member_project_user` leaves at most one row. **HR-5, HR-7, HR-8** — no paging, no `LIKE`. **HR-4** — the table has no soft-delete column; the parent's state is `get_by_project` R5. **HR-9, HR-10** — the DAO only reads. **HR-15** — no money. **HR-16** — `add_member` takes the workspace from a checked project and checks the person's membership.

### Precedent matches — confirmed

### Q1. Someone who left the workspace stays on the project — 🐞 BUG-1280
**Background:** A project set to `invited_only` is seen only by its members, its creator and privileged roles. Removing someone from the workspace sets their membership to `inactive` and keeps the row; `project_members` is not touched. The owner ruled the same shape for approvers in BUG-1201: a person who left is taken off what they were assigned to.
**What happens today:** `get_by_project` and `get_by_project_and_user` return the row of someone who left. (Verified: status `inactive`, still listed.) They cannot reach the project while they are out, because the workspace refuses them. If they are invited back, their old project access returns with no one deciding it.
**Example:** Rahim is on the private project "Tender 2026". He leaves in March and the members list still shows him. He comes back in June as a contractor and can open "Tender 2026" at once.
**Rules affected:** `get_by_project` R6, `get_by_project_and_user` R4
**Suggested answer:** the answer below. Not an OWNER item: no money, stock or order flow. These two reads stay raw either way.
**Answer:** bug — per BUG-1201 precedent: removing a member from the workspace deletes their `project_members` rows, with one `member_removed` project event per project; the fix is in `WorkspaceManager.remove_member_from_workspace`, and these reads stay raw
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): BUG-1280 (pattern `stale-assignment-after-member-removal`, as BUG-1201). Fix routed to `WorkspaceManager.remove_member_from_workspace`. Rules: `get_by_project` R6 ✅, `get_by_project_and_user` R4 ✅, unchanged; the tagged rule is FU-2.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Project manager** (`app/managers/project_manager.py`, not yet specified) | **BUG-1278, logged:** `require_project_access` looks the project up raw, so a soft-deleted project passes it. Verified: `list_members` lists its members, `add_member` adds one, `remove_member` removes one. `get_project` also returns the deleted project; that HR-4 item is for the manager's spec. The manager's spec must carry the rule and the tag. | standing decision |
| FU-2 | **Workspace manager** (`app/managers/workspace_manager.py`, `remove_member_from_workspace`) | **BUG-1280, logged:** the manager's spec must carry the rule and the tag: every `project_members` row of that person in that workspace is deleted, with one `member_removed` event per project. A person invited back has no project access until added again. The fix adds a read of one user's rows, new to this DAO: it gets a rule when written. | Q1 |

## Overview
`ProjectMemberDAO` reads `project_members`, the people invited to a project. Callers: `ProjectManager` only (`can_access_project`, `list_members`, `add_member`, `remove_member`). `add_member` builds the row itself and `remove_member` deletes it, so the inherited writes have no caller. The read decides who can open a private project.

**Callables:** 2 specified · 2 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Model facts (table `project_members`):** `workspace_id`, `project_id`, `user_id` are FK CASCADE, NOT NULL; `assigned_by` FK SET NULL, nullable; `assigned_at` NOT NULL, Python default `utcnow` (naive), no database default. `uq_project_member_project_user` on `(project_id, user_id)`, so a second row is refused even under another workspace.

**Notes for the test designer:** `from app.dao.project_member import project_member_dao`. Parents: `Factory`, `Project(workspace_id, factory_id, name, description)`, profiles from `tests/unit/factories.py`. Give `assigned_at` explicitly. **BUG-1274:** two rows with one `assigned_at`, `SET LOCAL enable_indexscan=off; SET LOCAL enable_bitmapscan=off; SET LOCAL enable_indexonlyscan=off`, update the lower `id`, flush, `db.expire_all()`. The result rests on physical order: **non-strict** xfail, assertion not weakened.

## Not specified
- `project_member_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — no caller on this DAO; covered by the base spec.

---

## `ProjectMemberDAO.get_by_project(db, *, project_id, workspace_id)`
**Shape:** list
**Persistence:** reads
**Visibility:** public (used by: `ProjectManager.list_members` ← `GET /projects/{id}/members/`)

**Purpose:** The members of one project, earliest added first.

**Returns:** a `list` of `ProjectMember` (possibly empty).

**Rules:**
- **R1.** Returns the rows with that `project_id` and that `workspace_id`. Another workspace returns `[]`.
- **R2.** An unknown project, `0`, or a project with no members returns `[]`.
- **R3.** Ordered by `assigned_at` ascending.
- **R4.** [BUG-1274] (HR-6) Members with one `assigned_at` are ordered by `id` ascending. *(Today: no tie-break.)*
- **R5.** The state of the project is not looked at: the members of a soft-deleted project are returned. The caller names the project, and hiding it is `ProjectManager`'s (BUG-1278).
- **R6.** ✅ (Q1) The state of the person is not looked at: someone who left the workspace is returned.
- **R7.** No paging and no cap: 101 members give 101 rows.

**Errors:** none of its own.

**Side effects:** none

---

## `ProjectMemberDAO.get_by_project_and_user(db, *, project_id, user_id, workspace_id)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `can_access_project`, `add_member`, `remove_member`)

**Purpose:** One person's membership of one project.

**Returns:** the `ProjectMember`, or `None`.

**Rules:**
- **R1.** Returns the row matching project, user and workspace.
- **R2.** A person who is not a member, an unknown project or an unknown user returns `None`.
- **R3.** Another workspace returns `None`.
- **R4.** ✅ (Q1) As `get_by_project` R5 and R6, neither the project's state nor the person's is looked at.

**Errors:** none.

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 16–19 | project AND workspace | `get_by_project` R1, R2 |
| 20 | `assigned_at` only (BUG-1274) | `get_by_project` R3, R4 |
| 15–21 | no parent or person state; `.all()`: no cap | `get_by_project` R5, R6, R7 |
| 29–33 | project AND user AND workspace; no state | `get_by_project_and_user` R1, R2, R3, R4 |
| 34 | `.first()`: row / `None` | `get_by_project_and_user` R1, R2 |
| 37 | module singleton | Not specified |
