# Spec — `app/services/access_control_service.py`

> **Status:** APPROVED (2026-11-04; nothing open). The owner answered who may write these rows (OQ-4, BUG-1875); the remaining items were decided by Claude under the reviewer's delegation (2026-11-04) or routed to the permissions feature.
> **Source commit:** e48a092

> **Revision 2026-11-04 (fill-gaps, `access_control_service.cases.md` gaps 1–3).** Schema modules named; BUG-1875's `user_id` and where its 403 is raised decided. No new bug, no question; stays APPROVED. See the Gap log.

> **Form.** As `tests/unit/services/department_service.spec.md`. `AccessControlService` does **not** inherit `BaseService`: it commits and rolls back itself. Its transaction is stated below as rules TX1–TX5, compared with TC1–TC6 of `tests/unit/services/base_service.spec.md`. Below it: `tests/unit/dao/access_control.spec.md` (APPROVED; `get_by_role`, `get_by_type`, Model facts) and `tests/unit/dao/base.spec.md` (`get_by_workspace`, `get_by_id_and_workspace`, `create`, `update`, `remove`), cited, not restated.
>
> **Answered upstream and applied here:** OQ-4 (owner, 2026-11-04): only the workspace owner may create, change or delete permission rows; any member may read them → BUG-1875, written here as rules. Access control DAO FU-1 answered: (a) BUG-1875; (b) nothing reads the rows — permissions feature; (c) duplicates — D2; (d) role + type — D1 / BUG-2255.
>
> **Verified by running** (`v1_ws.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvc\`, one outer transaction rolled back against `marker_test`, private `COVERAGE_FILE`; nothing persisted): `get_controls(role=OWNER, access_type=FEATURE)` returned both of the role's rows, the `PAGE` one included; another workspace's id → `get_by_id` `None`, `update_control` `None`, `delete_control` `False`; `update_control` with `target=None` left the target; a delete is committed (gone after a test-level rollback). **Read, not run:** commit and refresh failures.

## Review
> All decided; nothing pending.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| O1 | Any member can create, change or delete the workspace's permission rows | bug — owner only, 403 otherwise (BUG-1875) | owner (OQ-4) |
| D1 | Filtering by role and type together ignores the type | bug — both apply (BUG-2255) | Claude, delegated (precedent BUG-1960) |
| D2 | The same type + target + role can be stored twice; `target` can be blank | intended for now — routed to the permissions feature | Claude, delegated |
| D3 | Rows can name only `owner`, `finance`, `ground-team`, `ground-team-manager`; members hold `manager`, `member`, `viewer` too | intended for now — routed to the permissions feature | Claude, delegated |

### O1. Any member can change the permission table — 🐞 BUG-1875 (owner, OQ-4)
**Answer:** owner, 2026-11-04: only the workspace owner may create, change or delete permission rows (403 otherwise); any member may read them.
**Resolution:** 🐞 BUG-1875 (existing; no new ID). Who counts as "the owner" was decided by Claude under the reviewer's delegation (2026-11-04): an **active** membership of the workspace with role exactly `owner`, the same check as `WorkspaceService._require_owner`, which guards sending invitations (on every API path this is the user named by `workspaces.owner_user_id`; workspace service D6). Message and error type follow that sibling. Rules: `create_control` R1, `update_control` R1, `delete_control` R1.

### D1. Filtering by role and type together ignores the type — 🐞 BUG-2255
**Background:** `GET /access-control/` takes optional `role` and `access_type`. The service uses `role` if given, else `access_type`, else neither. Same root cause as BUG-1960 (projects: factory and status).
**What happens today:** `?role=owner&access_type=feature` returns every `owner` row, pages included (verified).
**Example:** The settings screen asks for the owner's feature switches and gets the owner's page rows mixed in.
**Rules affected:** `get_controls` R1
**Answer:** bug — per BUG-1960 precedent: both filters apply (AND), in the query, before paging, ordered by `id` (BUG-1408); either alone as today. Needs a DAO read taking both (or one filtered query).
**Resolution:** 🐞 BUG-2255 (pattern `silently-ignored-input`).

### D2, D3 — intended for now (permissions feature)
- **D2.** No uniqueness on `(workspace_id, type, target, role)` and no check on `target` (`""` accepted). Nothing in the backend reads the rows (OQ-4 facts), so a duplicate or blank row changes nothing today. The feature that gives these rows meaning decides uniqueness and the list of valid targets. Recorded in `docs/future/permissions.md`.
- **D3.** `role` is `RoleEnum` (`owner`, `finance`, `ground-team`, `ground-team-manager`); invitations and role changes use `manager`, `member`, `viewer`, `ground-team` (workspace manager Q10). So no row can name `manager`, `member` or `viewer`. Recorded in `docs/future/permissions.md`.

Checked and **not** violated: **HR-1, HR-2** — no name (D2). **HR-4** — no soft delete. **HR-5** — filters are in the queries (D1 is a dropped filter, not a late one). **HR-6** — BUG-1408 (filtered) and BUG-100 (unfiltered, `id`). **HR-7** — BUG-1409 (endpoint). **HR-8** — no `LIKE`. **HR-9** — no audit columns. **HR-10** — plain rows; a race on duplicates is D2. **HR-11 … HR-15** — none. **HR-16** — every lookup is `get_by_id_and_workspace` with the caller's workspace; another workspace's id is "not found" (verified); `workspace_id` comes from the caller on create and is not in `AccessControlUpdate`.

**Permission checks:** today none (any active member, through `get_current_workspace`). BUG-1875 adds the owner check for the three writes; reads stay open to every member.

## Overview
`AccessControlService` is the transaction boundary for `access_control`, a workspace's table of which role may reach which page, order-status action or feature. The `/access-control/` endpoints call it; it calls the DAO directly (there is no manager). Reads list or fetch rows of the caller's workspace; writes create, change or delete one row and commit. Not-found is returned as `None` / `False`, which the endpoint turns into 404 `Access control not found`. No backend code reads the rows to allow or refuse anything.

**Callables:** 5 specified · 1 not specified
**Externals to mock:** none.
**Integration-only behavior:** the endpoint's 404 on `None` / `False` and its 204 on delete; request validation of `AccessControlCreate` / `AccessControlUpdate` and of the `role` / `access_type` query parameters (enum values); `limit` bounds (BUG-1409); `get_current_workspace` (active membership; BUG-440).

### Transaction (not `BaseService`)
- **TX1.** A successful `create_control`, `update_control` or `delete_control` is committed: it survives a later rollback of the session (as TC1; verified for delete).
- **TX2.** `create_control` and `update_control` return the row re-read after the commit (as TC2). `delete_control` returns `True`, no re-read.
- **TX3.** Any exception inside the method (from the DAO, the flush, the commit or the re-read) rolls the session back once and reaches the caller unchanged (as TC3, TC4); every uncommitted change of the session is discarded. A re-read failure after a commit leaves the change saved (as TC5).
- **TX4.** `update_control` returning `None` and `delete_control` returning `False` (row not found in the workspace) neither commit nor roll back: other pending changes of the session stay pending.
- **TX5.** `get_controls` and `get_by_id` neither commit nor roll back (as TC6).

**Facts for the test designer**
- Import: `from app.services.access_control_service import AccessControlService, access_control_service`. No `__init__`; all parameters positional-or-keyword. The DAO is the module singleton `app.dao.access_control.access_control_dao`, imported by name into the service module (patch `app.services.access_control_service.access_control_dao` to make it fail).
- Enums: `from app.models.enums import RoleEnum, AccessControlTypeEnum` (`RoleEnum` and `AccessControlTypeEnum` are `str` enums; every member is truthy).
- BUG-1875's refusal: `PermissionDeniedError` (`app.core.exceptions`), 403, detail `Only the workspace owner can change access control`.
- Schemas (gap 1): `from app.schemas.access_control import AccessControlCreate, AccessControlUpdate`. Model: `from app.models.access_control import AccessControl`.
- **BUG-1875 signature (gap 2, decided by Claude under the reviewer's delegation, 2026-11-04):** `user_id` is a **required keyword-only** parameter of `create_control`, `update_control` and `delete_control` (`def create_control(self, db, control_in, workspace_id, *, user_id)`). *Why:* an optional caller id would let a forgotten argument skip the owner check, which is the whole fix; keyword-only stops a positional mix-up with `workspace_id`. So every passing write card passes `user_id=<an active owner>`; today that raises `TypeError`, so they are strict xfail until the fix, and the cards for today's behaviour (no check) are the only ones that call without it.
- **Where the 403 is raised (gap 3, decided by Claude under the reviewer's delegation, 2026-11-04):** before the `try`, before any read or write, as the other services' refusals (workspace service TX2): **no rollback** — a row the session had pending (flushed, uncommitted) before the call is still there afterwards, and nothing is written. *Why:* a refusal that writes nothing has nothing to undo, and the sibling owner-only checks (`send_invitation`, `list_invitations`) behave this way.

**Notes for the test designer**
- Session and commits: as `department_service.spec.md` Notes. Build rows directly: `AccessControl(workspace_id, type, target, role)`; owner: `WorkspaceMember(workspace_id, user_id, role="owner", status="active")`.
- **BUG-1875:** the methods have no caller parameter today; calling with `user_id=` raises `TypeError` → strict xfail. Write the intended signature as `create_control(db, control_in, workspace_id, user_id)` (and the same `user_id` last for update and delete).
- **BUG-2255:** one `PAGE` and one `FEATURE` row for `OWNER`, one `FEATURE` for `FINANCE`; `role=OWNER, access_type=FEATURE` → intended only the `FEATURE` / `OWNER` row; today both `OWNER` rows → strict xfail.
- Compare sets of ids except where the order is the case.

## Not specified
- `access_control_service` — module-level singleton.

---

## `AccessControlService.get_controls(db, workspace_id, role=None, access_type=None, skip=0, limit=100)`
**Shape:** list · **Persistence:** reads · **Visibility:** public (used by: `GET /access-control/`, every member)

**Returns:** a `list` of `AccessControl`.

**Rules:**
- **R1.** With `role`: the role's rows (DAO `get_by_role` R1–R5). [BUG-2255] (D1) With `role` and `access_type` both given, only rows matching both, in the query, before paging, `id` order. *(Today: `access_type` is ignored, verified.)*
- **R2.** With only `access_type`: DAO `get_by_type` R1–R5.
- **R3.** With neither (`None`): every row of the workspace, base `get_by_workspace` R1–R3, R5 (`id` order per BUG-100; default 100).
- **R4.** `skip` / `limit` are passed on as given (defaults `0`, `100`); negative values raise `DataError` at the DAO; the endpoint's bounds are BUG-1409.
- **R5.** Read only (TX5). No role is required.

---

## `AccessControlService.get_by_id(db, control_id, workspace_id)`
**Shape:** get · **Persistence:** reads · **Visibility:** public (used by: `GET /access-control/{id}/`)

**Rules:**
- **R1.** The row with that id in that workspace (base `get_by_id_and_workspace`), or `None` for an unknown id, `0`, or another workspace's row (verified). The endpoint answers 404 `Access control not found` for `None`.
- **R2.** Read only (TX5).

---

## `AccessControlService.create_control(db, control_in, workspace_id)`
**Shape:** create · **Persistence:** writes · **Visibility:** public (used by: `POST /access-control/`)

**Returns:** the new `AccessControl`, committed and re-read.

**Rules:**
- **R1.** [BUG-1875] (OQ-4) A new required keyword-only parameter `user_id` (the caller; gap 2). The caller must have an active membership of the workspace with role exactly `owner`; otherwise `PermissionDeniedError("Only the workspace owner can change access control")` (403), nothing written, checked before anything is read or written and outside the `try`: the session is not rolled back, so other pending changes stay (gap 3; TX4-like). *(Today: no such check; any member creates rows.)* *(Requires the new parameter; the endpoint passes `current_user.id`.)*
- **R2.** One row with `type`, `target`, `role` from `control_in` and `workspace_id` = the given workspace (any `workspace_id` cannot be supplied by the client: the schema has none). `target` stored as sent (D2). A row identical to an existing one is created (D2).
- **R3.** Committed (TX1), returned re-read with its `id` (TX2). Errors: TX3.

---

## `AccessControlService.update_control(db, control_id, control_in, workspace_id)`
**Shape:** update · **Persistence:** writes · **Visibility:** public (used by: `PUT /access-control/{id}/`)

**Returns:** the `AccessControl`, committed and re-read, or `None`.

**Rules:**
- **R1.** [BUG-1875] (OQ-4) As `create_control` R1, checked first, so a non-owner gets 403 whatever the id. *(Today: no check.)*
- **R2.** A row not found in the workspace (unknown, `0`, another workspace's, verified) → `None`, nothing written (TX4).
- **R3.** Only fields of `control_in` sent with a value are applied (base `update` R2, R3): `null` leaves the field (verified for `target`); `{}` changes nothing and still commits.
- **R4.** Committed (TX1), re-read (TX2); errors TX3.

---

## `AccessControlService.delete_control(db, control_id, workspace_id)`
**Shape:** delete · **Persistence:** writes · **Visibility:** public (used by: `DELETE /access-control/{id}/`, 204)

**Returns:** `True` when deleted, `False` when not found.

**Rules:**
- **R1.** [BUG-1875] (OQ-4) As `create_control` R1, checked first. *(Today: no check.)*
- **R2.** A row not found in the workspace → `False`, nothing deleted (TX4) (verified for another workspace's row).
- **R3.** Otherwise the row is deleted (hard; base `remove`) and committed (TX1); returns `True`. Nothing references the table, so nothing blocks.
- **R4.** Errors TX3.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 14–15 | `if role:` → by role (type ignored, BUG-2255) | `get_controls` R1, R4 |
| 16–17 | `elif access_type:` → by type | `get_controls` R2, R4 |
| 18–19 | else → workspace | `get_controls` R3, R4 |
| 23 | lookup in workspace | `get_by_id` R1, R2 |
| 27–33 | dump; set workspace; create; commit; refresh (no owner check, BUG-1875) | `create_control` R1–R3; TX1, TX2 |
| 34–36 | any error → rollback, re-raise | TX3 |
| 41–43 | not found → `None` | `update_control` R2; TX4 |
| 44–47 | update; commit; refresh | `update_control` R3, R4 |
| 48–50 | any error → rollback, re-raise | TX3 |
| 55–57 | not found → `False` | `delete_control` R2; TX4 |
| 58–60 | remove; commit; `True` | `delete_control` R3 |
| 61–63 | any error → rollback, re-raise | TX3 |
| 66 | singleton | Not specified |

## Gap log
G1 (`access_control_service.cases.md` gap 1) — Fact — Facts: `app.schemas.access_control` (`AccessControlCreate`, `AccessControlUpdate`), `app.models.access_control`.
G2 (gap 2) — Intent, decided by Claude under the reviewer's delegation (2026-11-04) — `create_control` R1 and Facts: `user_id` is required and keyword-only on the three writes; passing write cards pass it (strict xfail until the fix). Why: an optional id would let a forgotten argument skip the owner check.
G3 (gap 3) — Intent, decided by Claude under the reviewer's delegation (2026-11-04) — `create_control` R1 and Facts: the 403 is raised before the `try`, no rollback; a pending row survives, nothing written. Why: consistent with the other services' up-front refusals (workspace service TX2).
