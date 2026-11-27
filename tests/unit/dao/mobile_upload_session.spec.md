# Spec — `app/dao/mobile_upload_session.py`

> **Status:** APPROVED (2026-11-02; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-02.** **Delegated:** Q1 and Q2 accepted as pre-filled and suggested, decided by Claude under the reviewer's delegation (2026-11-02). Neither is the owner's own answer.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Standing decisions applied here (not asked again):** a missing `ORDER BY` is a bug, and no order recipe counts as deterministic unless it ends in `id`. HR-16: a row linking to another workspace's row is invalid data. Raw lookups stay raw (HR-4 scope).
>
> **Verified by running** (throwaway scripts `cat1.py`, `v4.py`, harness `h.py`, `w.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\childdao\`, each transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints, indexes; token lookup with an unknown, empty and upper-case hash; `get_for_creator` with another workspace and another user; a cancelled session through both reads; the unique token; defaults; `mark_expired_if_needed` for every status, one second past, exactly at, and one microsecond before expiry, with naive, UTC and offset values; that it changes nothing in the database; a session written as the app writes it, under `America/New_York`, `UTC`, `Asia/Dhaka`, and read under the same and another zone. `utcnow` was patched. **Not run:** anything over HTTP; two concurrent transactions; Cloudinary.

## Review
> All answered; applied 2026-11-02.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | Session expiry depends on the database's time zone | bug — `expires_at` is a true moment (BUG-1282) | Claude, delegated |
| Q2 | An uploaded file never expires on the desktop side | intended — the 10 minutes limit the phone | Claude, delegated |

Checked and **not** a line here: **HR-6** — `get_by_token_hash` has a unique token, `get_for_creator` a primary key, so `.first()` has one row at most. **HR-5, HR-7, HR-8** — no list, no `LIKE`. **HR-4** — no soft-delete column; the session's entity is not read here. **HR-9** — no audit stamp. **HR-10** — `mark_expired_if_needed` writes nothing to the database; a race only leaves the row as it was. Confirm and promote are the manager's. **HR-15** — no money. **HR-16** — `get_by_token_hash` has no workspace filter by design: the phone has no login and the secret token is the access; `get_for_creator` is scoped.

### Precedent matches — confirmed

### Q1. Session expiry depends on the database's time zone — 🐞 BUG-1282
**Background:** A QR upload session lasts 10 minutes. `expires_at` is `timestamp with time zone`, but the code writes `utcnow()`, which has no zone, and Postgres reads that in the server's `TimeZone`. On reading back, `_naive_utc` removes the zone **without converting to UTC**, in spite of its name. The two mistakes cancel only while the writer and reader share one `TimeZone`. The stored moment is still wrong, and the session response sends that moment to the browser. BUG-992 and BUG-1102 settled, under the reviewer's delegation, that a result must not depend on that setting.
**What happens today:** Verified for a session written with 10 minutes left. Under `UTC`: right. Under `America/New_York`: stored 310 minutes ahead. Under `Asia/Dhaka`: stored 350 minutes in the past. Under Dhaka and read under `UTC`, a fresh session counts as expired at once. An aware value is never converted: `17:59:59+06:00`, one second past expiry at 12:00 UTC, stays `waiting`.
**Example:** The server is set to Asia/Dhaka. A user opens the QR at 14:00 Dhaka time. The poll response gives `expires_at` as 08:10 Dhaka time, nearly six hours in the past, though the phone can still upload until 14:10.
**Rules affected:** `_naive_utc` R2, `mark_expired_if_needed` R5a
**Suggested answer:** the answer below. On a server set to UTC, nothing changes. Not an OWNER item: no money.
**Answer:** bug — per BUG-992 precedent: `expires_at` is a true moment whatever the database's `TimeZone`: written as aware UTC by `create_session`, and converted to UTC, not stripped, before comparing. A UTC server sees no change
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): BUG-1282 (pattern `aware-datetime-against-naive-column`, as BUG-992). Rules: `_naive_utc` R2, `mark_expired_if_needed` R5a; the write side is FU-2. Sessions last 10 minutes, so stored rows need no repair.

### New questions

### Q2. An uploaded file never expires on the desktop side — ✅ intended
**Background:** A session goes `waiting` → `uploaded` when the phone finishes, then `consumed` when the desktop attaches the file. It can also become `cancelled` or `expired`. The desktop polls through `get_for_creator` and calls this method. The phone's path uses the manager's `_ensure_active`, which expires any session past its time unless it is already final.
**What happens today:** This method expires only `waiting` sessions. An `uploaded` session past its time stays `uploaded`, so the desktop keeps seeing it and `promote_to_attachment` still accepts it. The phone's path answers "Upload session has expired." for the same session.
**Example:** A user photographs a receipt on the phone, then goes to lunch. An hour later the desktop page still offers the file and Attach works. If they open the phone link instead, it says the session has expired.
**Rules affected:** `mark_expired_if_needed` R3
**Suggested answer:** `intended — the 10 minutes limit how long the phone may take; a file already uploaded waits for the desktop`. Otherwise users lose uploads they have already made. Alternative: `bug — an uploaded session past its time expires on the desktop too`. Not an OWNER item.
**Answer:** intended — the 10 minutes limit how long the phone may take; a file already uploaded waits for the desktop
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-02): rule unchanged. Rules: `mark_expired_if_needed` R3 ✅.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO. Whoever describes the named module must read this list first.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Mobile upload session manager** (`app/managers/mobile_upload_session_manager.py`, not yet specified) | (a) `get_for_creator` and `_ensure_active` set `expired` in memory and raise; no commit follows, and `get_db` closes the session, so the row stays `waiting` in the database (read; the DAO part is verified). A consequence for any report or clean-up that reads the column. (b) `delivery_type` is NOT NULL in the model and nullable in the database. | reading the callers |
| FU-2 | **Same manager** (`create_session`, `_ensure_active`) | **BUG-1282, logged:** `create_session` writes `expires_at` as aware UTC. `_ensure_active` already calls `_naive_utc`, so it follows R2. The manager's spec must carry the write rule and the tag. | Q1 |

## Overview
`MobileUploadSessionDAO` reads `mobile_upload_sessions`, the short-lived QR sessions that carry a phone upload to the desktop. It finds a session by token hash (the phone, which has no login) or by creator (the desktop), and marks a waiting session as expired in memory. Callers: `MobileUploadSessionManager`, also importing `_naive_utc` for `_ensure_active`.

**Callables:** 4 specified · 2 not specified
**Externals to mock:** `utcnow` in `app.dao.mobile_upload_session`
**Integration-only behavior:** none

**Model facts (table `mobile_upload_sessions`):** `workspace_id`, `created_by` FK CASCADE, `entity_type` String(64), `entity_id`, `token_hash` String(64), `expires_at` `timestamp with time zone` are NOT NULL. `token_hash` unique (`ix_mobile_upload_sessions_token_hash`). `status` NOT NULL default `waiting`; `delivery_type` default `authenticated`. `created_at`, `updated_at` timestamptz with database default `now()`.

**Notes for the test designer:**
- `from app.dao.mobile_upload_session import mobile_upload_session_dao, _naive_utc`. `mark_expired_if_needed` needs no database: build `MobileUploadSession(status=..., expires_at=...)` unsaved.
- Patch `app.dao.mobile_upload_session.utcnow` with a fixed naive value for every expiry case.
- The test database's `TimeZone` is `America/New_York`. A row read back has an aware `expires_at` in that zone, so give aware UTC values, or use `SET LOCAL TIME ZONE 'UTC'`, unless the case is about BUG-1282.
- BUG-1282: `_naive_utc` R2 and `mark_expired_if_needed` R5a need no database and fail today on any offset other than `+00:00`: strict xfail.

## Not specified
- `mobile_upload_session_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — `create` is used with a plain dict; covered by the base spec.

---

## `_naive_utc(value)`
**Shape:** helper
**Persistence:** pure
**Visibility:** internal (used by: `mark_expired_if_needed`, `MobileUploadSessionManager._ensure_active`)

**Purpose:** Make a datetime comparable with `utcnow()`.

**Returns:** a naive `datetime`.

**Rules:**
- **R1.** A naive value comes back unchanged.
- **R2.** [BUG-1282] An aware value is converted to UTC, then its zone is removed: `2026-01-01 00:00+06:00` gives `2025-12-31 18:00`; a `+00:00` value keeps its clock time. *(Today: the zone is removed with no conversion: `2026-01-01 00:00`.)*

**Errors:** none.

**Side effects:** none

---

## `MobileUploadSessionDAO.get_by_token_hash(db, *, token_hash)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `MobileUploadSessionManager.get_by_raw_token`)

**Purpose:** Find a session from the secret token's hash.

**Returns:** the `MobileUploadSession`, or `None`.

**Rules:**
- **R1.** Returns the row with exactly that hash, of any workspace. No workspace filter, by design.
- **R2.** An unknown hash, `""`, or the hash in another case returns `None`.
- **R3.** Status and expiry are not looked at: a cancelled or expired session is returned.

**Errors:** none.

**Side effects:** none

---

## `MobileUploadSessionDAO.get_for_creator(db, *, session_id, workspace_id, created_by)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `MobileUploadSessionManager.get_for_creator`)

**Purpose:** One session, only for the person who made it, in that workspace.

**Returns:** the `MobileUploadSession`, or `None`.

**Rules:**
- **R1.** Returns the row matching id, workspace and creator.
- **R2.** Another workspace, another user of the same workspace, or an unknown id returns `None`.
- **R3.** Status and expiry are not looked at.

**Errors:** none.

**Side effects:** none

---

## `MobileUploadSessionDAO.mark_expired_if_needed(session)`
**Shape:** state-transition
**Persistence:** pure (changes the instance only)
**Visibility:** public (used by: `MobileUploadSessionManager.get_for_creator`)

**Purpose:** Turn a waiting session past its time into an expired one.

**Returns:** the same instance.

**Rules:**
- **R1.** A `waiting` session with `expires_at` before now becomes `expired`.
- **R2.** The boundary: `expires_at` exactly now becomes `expired`; one microsecond later stays `waiting`.
- **R3.** ✅ (Q2) Any other status is left as it is, however far past its time: `uploaded`, `consumed`, `cancelled`, `expired`.
- **R4.** Nothing is written to the database: the instance is dirty in the session, not flushed, and a query for the column still reads `waiting`.
- **R5.** Naive and UTC values compare correctly, by `_naive_utc`.
- **R5a.** [BUG-1282] A value with another offset compares by its true moment: with now = 12:00 UTC, `17:59:59+06:00` (11:59:59 UTC) becomes `expired`, and `08:00-05:00` (13:00 UTC) stays `waiting`. *(Today: compared by clock time, so the first stays `waiting` and the second becomes `expired`.)*

**Errors:** none.

**Side effects:** sets `session.status` in memory only.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13 | `value.tzinfo is not None` | `_naive_utc` R1, R2 |
| 14 | zone removed, not converted (BUG-1282) | `_naive_utc` R2 |
| 22 | hash only, no workspace or status; `.first()`: row / `None` | `get_by_token_hash` R1, R2, R3 |
| 34–39 | id AND workspace AND creator; `.first()`: row / `None` | `get_for_creator` R1, R2, R3 |
| 43 | `status == "waiting"`; `<=` at the boundary | `mark_expired_if_needed` R1, R2, R3, R5, R5a |
| 44 | status set, no flush | `mark_expired_if_needed` R1, R4 |
| 45 | returns the same instance | `mark_expired_if_needed` R1 |
| 48 | module singleton | Not specified |
