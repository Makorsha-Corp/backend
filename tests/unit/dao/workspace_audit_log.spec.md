# Spec — `app/dao/workspace_audit_log.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** **Delegated:** P1–P3 (precedent matches) and Q1 decided by Claude under the reviewer's delegation (2026-11-03). None is the owner's own answer.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** logs are history: a log row is never hidden, changed or removed because of the state of what it describes.
>
> **Verified by running** (throwaway scripts `facts.py`, `v_ws.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints (**`created_at` is `timestamp with time zone` in the database although the model declares a plain `DateTime`**); every field written by `log_action`; `None` workspace and user; unknown workspace and user (foreign-key errors); `action` of 101 characters, `ip_address` of 46, `resource_type` of 51 (`DataError`); a 5 000-character user agent stored whole; `metadata` holding a `datetime` (`StatementError`) and a list (stored); positional arguments refused; `create` with `WorkspaceAuditLogCreate`; one moment written under `UTC`, `America/New_York` and `Asia/Dhaka`, then read back as UTC: `14:18`, `19:18`, `08:18`. **Not run:** anything over HTTP; the intended behaviour of the bug rules.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A log row's time is wrong by the database's time-zone offset | bug — the true moment (BUG-1403) | Claude, delegated |
| P2 | No caller ever records the IP address or browser of a workspace action | bug — callers pass them (BUG-1404) | Claude, delegated |
| P3 | An IP address over 45 characters would make the action itself fail | bug — cut to 45 (BUG-1405) | Claude, delegated |
| Q1 | Nothing reads this table | intended — history is kept; a reader is a feature | Claude, delegated |

Checked and **not** a line here: **HR-4** — no soft-delete column, and logs are history. **HR-5, HR-6, HR-7, HR-8** — the DAO has no list (its three readers were removed as dead code before this review). **HR-9** — nothing is updated. **HR-10** — a single insert. **HR-16** — `workspace_id` comes from the caller's checked workspace; `user_id` is a profile, not a workspace row.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. A log row's time depends on the database's time zone — 🐞 BUG-1403
**Background:** The table's `created_at` is `timestamp with time zone` in the database, but the model fills it from `utcnow()`, a UTC time with no zone. Postgres reads a zone-less value in the session's `TimeZone` setting. BUG-1282 (mobile upload `expires_at`) is the same mismatch and was ruled a bug.
**What happens today:** Under a `UTC` session the moment is right; under `America/New_York` it is stored 5 hours late, under `Asia/Dhaka` 6 hours early. (Verified: one moment read back as UTC `14:18`, `19:18`, `08:18`.)
**Example:** The owner adds a member at 14:18 UTC on a server whose database runs in Dhaka time. The log says 08:18 UTC.
**Rules affected:** `log_action` R5
**Answer:** bug — per BUG-1282 precedent: `created_at` is the true moment of the insert, whatever the session's `TimeZone` (written as aware UTC; a UTC server sees no change)
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1403 (pattern `aware-datetime-against-naive-column`). The fix is the default in `app/models/workspace_audit_log.py`. Rules: `log_action` R5.

### P2. No caller records the IP address or browser — 🐞 BUG-1404
**Background:** `log_action` accepts `ip_address` and `user_agent`, and the table has columns for them. Its six callers (`WorkspaceManager`: workspace created, member added, member removed, invitation sent, accepted, cancelled) pass neither; the service and endpoints never hand them down. BUG-140 is the same gap in the financial audit log and was ruled a bug.
**What happens today:** Every workspace audit row has `ip_address` and `user_agent` `NULL`.
**Example:** A member is removed and the owner asks from where. The row says who and when, not from which address or browser.
**Rules affected:** `log_action` R2 (the DAO stores what it is given; the gap is upstream)
**Answer:** bug — per BUG-140 precedent: the request's client IP (as resolved by trusted-proxy handling, never raw `X-Forwarded-For`) and user agent are passed from the endpoints through `WorkspaceService` and `WorkspaceManager` into every `log_action` call, and into the BUG-1193 expense-order delete record
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1404 (pattern `flag-unreachable-from-api`). Tested in the workspace manager / service specs, not here. `resource_type` and `resource_id` are also never passed today; BUG-1193 is about to pass them, so they are not dead.

### P3. An IP address over 45 characters would fail the action — 🐞 BUG-1405
**Background:** `ip_address` is `VARCHAR(45)`. Once P2 is fixed, the value comes from the request, and a forwarded-for header can carry anything. BUG-144 (financial audit log) ruled the same case: the audit write must not fail the user's action.
**What happens today:** A 46-character `ip_address` raises `DataError` at the flush, so the whole action (adding a member, sending an invitation) fails with a 500. Unreachable until P2. (Verified at the DAO.) `user_agent` is `TEXT`, so it has no limit (5 000 characters verified).
**Example:** A proxy forwards a 60-character address string. Today nothing passes it; after P2, adding a member would fail.
**Rules affected:** `log_action` R3
**Answer:** bug — per BUG-144 precedent: `ip_address` is cut to its first 45 characters before writing; the row is written and the action succeeds
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1405 (pattern `unchecked-column-length`). Rules: `log_action` R3.

### New questions

### Q1. Nothing reads the workspace audit log — ✅ intended
**Background:** The DAO used to have three readers (`get_workspace_logs`, `get_user_logs`, `get_logs_by_action`); they had no caller and were removed as dead code. The expense-order delete record (BUG-1193) was designed knowing "no page shows it".
**What happens today:** Rows are written and nothing in the API reads them.
**Example:** The owner cannot see "who removed Rahim" anywhere in the app; the row is only in the database.
**Rules affected:** none
**Suggested answer:** `intended` — logs are history and are kept; a page that shows them is a feature, and who may read it is the owner's call when it is built. Alternative: `bug` per BUG-1198 (`log-without-reader`) — but that precedent was a panel the UI already implied.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): no bug. Rules unchanged.

## Overview
`WorkspaceAuditLogDAO.log_action` appends one row to `workspace_audit_logs`, the record of workspace administration: who did what, to which resource, with free-form `metadata`. Callers: `WorkspaceManager` (six actions, see P2); the expense-order delete record of BUG-1193 will be the seventh. It validates nothing, flushes, never commits.

**Callables:** 1 specified · 1 not specified (+ inherited, base spec)
**Externals to mock:** none (the default `utcnow` is bound into the column default when the model is imported; patching the name in `app.models.workspace_audit_log` does not reach it — verified).
**Integration-only behavior:** none

**Model facts (table `workspace_audit_logs`):** `workspace_id` nullable, FK `workspaces` ON DELETE CASCADE; `user_id` nullable, FK `profiles` ON DELETE SET NULL; `action` VARCHAR(100) NOT NULL; `resource_type` VARCHAR(50), `resource_id` INTEGER, `ip_address` VARCHAR(45), `user_agent` TEXT, `metadata` JSON (attribute `metadata_json`), all nullable; `created_at` **`timestamptz`** NOT NULL, Python default `utcnow()` (naive), no database default. Indexes on `id`, `workspace_id`, `user_id`, `action`, `created_at`. No unique constraint, no soft delete, no table references it.

**Notes for the test designer:** `from app.dao.workspace_audit_log import workspace_audit_log_dao`. Every parameter after `db` is keyword-only. Read `created_at` back as a moment with `SELECT created_at AT TIME ZONE 'UTC'`, under `SET LOCAL TimeZone = 'Asia/Dhaka'` (and `America/New_York`), comparing with a UTC clock read just before and after the call (allow a few seconds); today the value is off by the offset, deterministically → **strict** xfail. Wrap `DataError` / `IntegrityError` / `StatementError` cases in `with db.begin_nested():` inside `pytest.raises`.

## Not specified
- `workspace_audit_log_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — no caller on this DAO; covered by the base spec. `create` with `WorkspaceAuditLogCreate` works: the field `metadata` has the alias `metadata_json`, so the dump by alias lands on the model attribute (verified).

---

## `WorkspaceAuditLogDAO.log_action(db, *, workspace_id, user_id, action, resource_type=None, resource_id=None, metadata=None, ip_address=None, user_agent=None)`
**Shape:** event-log
**Persistence:** writes
**Visibility:** public (used by: `WorkspaceManager.create_workspace_with_owner`, `add_member_to_workspace`, `remove_member_from_workspace`, `create_invitation`, `accept_invitation`, `cancel_invitation`)

**Purpose:** Record one administrative action.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `workspace_id` | `int \| None`, required keyword | `None` allowed; an unknown id fails the foreign key |
| `user_id` | `int \| None`, required keyword | the actor; `None` allowed; an unknown id fails the foreign key |
| `action` | str, required | at most 100 characters; `""` accepted |
| `resource_type` | `str \| None` | at most 50 characters |
| `resource_id` | `int \| None` | not checked against anything |
| `metadata` | `dict \| None` | stored as JSON; anything `json.dumps` accepts (a list too); not copied |
| `ip_address` | `str \| None` | at most 45 characters today (BUG-1405) |
| `user_agent` | `str \| None` | no limit |

**Returns:** the new `WorkspaceAuditLog`, flushed (has its `id`), not committed.

**Rules:**
- **R1.** One row is inserted with exactly the given values; `metadata` lands in the `metadata` column (attribute `metadata_json`). The row is flushed and visible in the same session; rolling back a savepoint around the call removes it.
- **R2.** Optional values not given are stored `NULL`: `resource_type`, `resource_id`, `metadata`, `ip_address`, `user_agent`. `workspace_id=None` and `user_id=None` are stored `NULL` too.
- **R3.** [BUG-1405] (P3) An `ip_address` over 45 characters is stored cut to its first 45; the row is written and nothing is raised. *(Today: `DataError`, pgcode `22001`, at the flush; nothing is written.)* A `user_agent` of any length is stored whole.
- **R4.** An `action` over 100 characters or a `resource_type` over 50 raises `DataError` (pgcode `22001`) at the flush; nothing is written. `metadata` that JSON cannot encode (e.g. a `datetime` value) raises `sqlalchemy.exc.StatementError` (cause `TypeError`) at the flush. An unknown `workspace_id` or `user_id` raises `IntegrityError` (`ForeignKeyViolation`, pgcode `23503`).
- **R5.** [BUG-1403] (P1) `created_at` is the moment of the call: read back as UTC it equals the UTC clock, under any session `TimeZone` (`UTC`, `America/New_York`, `Asia/Dhaka`). *(Today: the naive UTC value is read in the session's zone: right under `UTC`, 5 hours late under `America/New_York`, 6 hours early under `Asia/Dhaka`.)*
- **R6.** Nothing else is read or written: no row is checked for existence beyond the foreign keys, and two identical calls write two rows.
- **R7.** Every parameter is keyword-only: positional arguments raise `TypeError`. `workspace_id`, `user_id` and `action` have no default: leaving one out raises `TypeError`.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `action` > 100, `resource_type` > 50, `ip_address` > 45 (today) | `sqlalchemy.exc.DataError`, pgcode `22001` | — |
| unknown `workspace_id` / `user_id` | `sqlalchemy.exc.IntegrityError`, pgcode `23503` | — |
| `metadata` not JSON-encodable | `sqlalchemy.exc.StatementError` | — |
| positional or missing required keyword | `TypeError` | — |

**Side effects:** one row inserted, flushed, not committed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 12–24 | keyword-only; three required, five optional (`None`) | `log_action` R2, R7 |
| 38–47 | row built from the arguments; `metadata` → `metadata_json` | `log_action` R1, R2 |
| 48–50 | flush: length, foreign-key, JSON errors; no commit | `log_action` R1, R3, R4, R6 |
| `models/workspace_audit_log.py` 31 | `created_at` default naive `utcnow()` into `timestamptz` (BUG-1403) | `log_action` R5 |
| 53 | module singleton | Not specified |
