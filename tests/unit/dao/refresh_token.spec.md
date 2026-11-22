# Spec — `app/dao/refresh_token.py`

> **Status:** APPROVED (2026-11-03; nothing open)
> **Source commit:** e48a092

> **Review round 2026-11-03.** **Delegated:** P1, Q1–Q3 decided by Claude under the reviewer's delegation (2026-11-03). None is the owner's own answer, and none changes who can sign in or what a session may do: P1 stops a crash, Q1 keeps today's revocation, Q2 confirms today's lookup, Q3 removes code nothing calls. The HR-10 race on token rotation is a house-rule matter for the auth service (FU-1), not a rule here.

> **Base behaviour:** this DAO does **not** inherit `BaseDAO`; it has only the methods below.
>
> **Verified by running** (throwaway scripts `facts.py`, `v_auth.py`, `v_auth2.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns, constraints and indexes; `create` with and without the optional values, a taken hash, a 65-character hash, a 37-character family, user agents of 512 and 513 characters, a 65-character IP, unknown user and workspace, `expires_at=None`, a past expiry; `get_by_hash` with other case and `""`; `revoke` with `utcnow` patched: first call, second call with another successor, call with none, an unknown successor, a row whose session copy is stale; `revoke_family` and `revoke_all_for_user` counts with active, expired, already revoked rows, another user and another family; that both bulk updates leave the session's loaded copies unchanged until refreshed; `touch_last_used`; the cascade when a profile is deleted; `SET NULL` when a successor is deleted. **Not run:** anything over HTTP; two concurrent transactions; the intended behaviour of BUG-1407.

## Review
> All answered; nothing pending.

### Quick list — all answered
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| P1 | A browser name over 512 characters, or an address over 64, makes login fail with a 500 | bug — cut them (BUG-1407) | Claude, delegated |
| Q1 | "Revoke all" also stamps and counts tokens that had already expired | intended | Claude, delegated |
| Q2 | The module says every query is scoped to a user; the token lookup and the family revoke are not | intended — the comment is wrong, not the code | Claude, delegated |
| Q3 | `get_by_id` has no caller | remove | Claude, delegated |

Checked and **not** a line here: **HR-10** — `AuthService.refresh_access_token` reads the row with `get_by_hash` (no lock), checks it is not revoked, issues a successor, then calls `revoke`. Two refreshes with one token at the same moment both pass the check and both issue a live successor in the family (a duplicate side effect, so HR-10 applies). The fix is a locked read in the service, or a locked variant of `get_by_hash`; the default read here stays unlocked (FU-1). **HR-4, HR-5, HR-6, HR-7, HR-8** — no soft delete, no list. **HR-9** — no audit columns. **HR-16** — `workspace_id` is set by the service from a checked membership.

### Precedent matches — all accepted (decided by Claude under the reviewer's delegation, 2026-11-03)

### P1. An over-long browser name or address makes login fail — 🐞 BUG-1407
**Background:** Every login, registration, workspace switch and refresh writes a token row with the request's `User-Agent` header and client address (from `X-Forwarded-For` when present). They are "best-effort diagnostics" (the endpoint's own comment). The columns are `VARCHAR(512)` and `VARCHAR(64)`. BUG-144 (financial audit log) ruled the same case: a diagnostic value never fails the user's action.
**What happens today:** A 513-character user agent, or a 65-character address, raises `DataError` at the flush, so the login fails with a 500. (Verified at the DAO.) The forwarded-for header is client-controlled.
**Example:** A tester's browser extension adds a long product token to the `User-Agent`. Login answers 500 every time.
**Rules affected:** `create` R4
**Answer:** bug — per BUG-144 precedent: `user_agent` is cut to its first 512 characters and `ip_address` to its first 64 before writing; the row is written
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): 🐞 BUG-1407 (pattern `unchecked-column-length`). Rules: `create` R4.

### New questions

### Q1. "Revoke all" counts tokens that had already expired — ✅ intended
**Background:** `revoke_all_for_user` (logout on all devices, and an owner's password reset of a member) and `revoke_family` (token reuse detected) stamp `revoked_at` on every row of the user / family that has none. Expired rows are not left out. The logout message says "Revoked N active session(s)."
**What happens today:** A user with one live session and four expired ones logs out everywhere: five rows are stamped and the message says 5. (Counts verified.)
**Example:** Rahim logs out of all devices and reads "Revoked 5 active session(s)" while only his laptop was signed in.
**Rules affected:** `revoke_family` R1, `revoke_all_for_user` R1
**Suggested answer:** `intended` — stamping expired rows is harmless and leaves no row unrevoked; the wording "active" is the auth service's (FU-1 (c)). Alternative: `bug — leave expired rows alone and count only live ones`.
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged; the message wording is noted for the auth service.

### Q2. The module comment says every query is scoped to a user — ✅ intended
**Background:** The module docstring says "every query scopes to a known user_id (or workspace_id) — there is no global lookup". `get_by_hash`, `get_by_id` and `revoke_family` take no user. The lookup by hash is how a refresh token is recognised: the client presents only the raw token, whose SHA-256 is the key; family ids are random UUIDs.
**What happens today:** `get_by_hash` finds a row of any user; `revoke_family` stamps every row of the family, whatever its user (verified: a row of another user that shared the family id was stamped too — which cannot happen with real UUIDs).
**Example:** A client sends its refresh token; the server finds the row by hash and learns the user from it. A per-user scope would need the user before the token.
**Rules affected:** `get_by_hash` R2, `revoke_family` R2
**Suggested answer:** `intended` — the comment is wrong, the code is right; correcting the comment is a doc change. Alternative: scope `revoke_family` by user as well (a defence in depth that changes nothing with UUIDs).
**Answer:** intended
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): rules unchanged.

### Q3. `get_by_id` has no caller — 🗑️ remove
**Background:** A search of `app/`, `tests/` and `scripts/` finds no caller of `refresh_token_dao.get_by_id`. Its neighbours `list_active_for_user` and `cleanup_expired` were already removed as dead code.
**What happens today:** Nothing can reach it; it works when called directly (verified).
**Example:** No request or job runs it.
**Rules affected:** none left
**Suggested answer:** `remove`. Alternative: `intended — keep`.
**Answer:** remove
**Resolution:** decided by Claude under the reviewer's delegation (2026-11-03): dead code; listed in `docs/testing/dead-code-removal-checklist.md`.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Auth service** (`app/services/auth_service.py`, not yet specified) and `POST /auth/logout/` | (a) **HR-10, security:** `refresh_access_token` must read the presented row with a row lock, so a second refresh with the same token sees it revoked (and, having a successor, triggers reuse detection). Today `revoke` on a row already revoked by the other request keeps the first `revoked_at` but **replaces** `replaced_by_id`, so the first successor is left live and unlinked. (b) `revoke_family` / `revoke_all_for_user` do not refresh rows already loaded in the session: code that reads `row.revoked_at` afterwards in the same transaction sees the old value, and a later `revoke(row=…)` on such a stale copy overwrites the stamp (verified). (c) The logout message counts expired rows as "active" (Q1). (d) `/auth/logout/` with `all_devices` finds the user from a revoked or expired refresh token as well. | HR-10 line, Q1 |

## Overview
`RefreshTokenDAO` reads and writes `refresh_tokens`, the server side of the login session: one row per issued refresh token, keyed by the SHA-256 of the raw token, grouped by `family_id` (all rotations of one login), linked to its successor by `replaced_by_id`. Revoked means `revoked_at` is set. Callers: `AuthService` (issue a pair on login, register, switch workspace and refresh; rotate; detect reuse; logout; owner's password reset) and `POST /auth/logout/`. It never commits; every method flushes.

**Callables:** 6 specified · 2 not specified
**Externals to mock:** `utcnow` — patch `app.dao.refresh_token.utcnow` for `revoke`, `revoke_family`, `revoke_all_for_user`, `touch_last_used`. `issued_at`'s default is bound into the model and is not reached by that patch.
**Integration-only behavior:** none (a row lock cannot be observed with one connection).

**Model facts (table `refresh_tokens`):** `user_id` NOT NULL, FK `profiles` ON DELETE CASCADE; `workspace_id` nullable, FK `workspaces` ON DELETE CASCADE; `token_hash` VARCHAR(64) NOT NULL, **unique index `ix_refresh_tokens_token_hash`**; `family_id` VARCHAR(36) NOT NULL; `issued_at` NOT NULL, Python default `utcnow()`; `expires_at` NOT NULL, no default; `revoked_at`, `last_used_at` nullable; `replaced_by_id` nullable, FK `refresh_tokens.id` ON DELETE SET NULL; `user_agent` VARCHAR(512), `ip_address` VARCHAR(64) nullable. All timestamps `timestamp without time zone`, naive UTC. Indexes also on `user_id`, `workspace_id`, `family_id`, `expires_at`, `(user_id, family_id)`, `(user_id, revoked_at, expires_at)`.

**Notes for the test designer:** `from app.dao.refresh_token import refresh_token_dao`. Profiles and workspaces from `tests/unit/factories.py`. Every parameter after `db` is keyword-only. Use 64-character hex strings for hashes, unique per test. After a bulk revoke, `db.refresh(row)` (or `expire_all()`) before reading `revoked_at`; the stale-copy rule (`revoke_family` R4) reads the attribute without refreshing. Wrap database errors in `with db.begin_nested():` inside `pytest.raises`. **BUG-1407:** today's `DataError` is deterministic → **strict** xfail.

## Not specified
- `refresh_token_dao` — module-level singleton, no logic.
- `RefreshTokenDAO.get_by_id` — dead code, to be removed (Claude, delegated; Q3).

---

## `RefreshTokenDAO.get_by_hash(db, *, token_hash)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `AuthService.refresh_access_token` (twice: the presented token, then the successor just created), `logout_session`; `POST /auth/logout/` with `all_devices`)

**Purpose:** The row of a presented refresh token.

**Returns:** the `RefreshToken`, or `None`.

**Rules:**
- **R1.** Given a row with exactly that hash, it is returned, whatever its state: revoked, expired, with or without a successor.
- **R2.** ✅ (Q2) Not scoped to a user or workspace. The match is exact: the same hash in upper case, `""`, or an unknown hash give `None`. The hash is unique, so at most one row matches.

**Errors:** none of its own.

**Side effects:** none

---

## `RefreshTokenDAO.create(db, *, user_id, token_hash, family_id, expires_at, workspace_id=None, user_agent=None, ip_address=None)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `AuthService._issue_token_pair`, on login, every registration path, workspace switch and refresh)

**Purpose:** Store a newly issued refresh token.

**Returns:** the new `RefreshToken`, flushed (has its `id`), not committed.

**Rules:**
- **R1.** One row is inserted with the given values; `issued_at` is set to the current UTC time (naive); `revoked_at`, `replaced_by_id`, `last_used_at` are `NULL`. `workspace_id`, `user_agent`, `ip_address` not given are `NULL`.
- **R2.** Nothing is checked in Python: an `expires_at` in the past is stored; a workspace the user is not a member of is stored.
- **R3.** A taken `token_hash` raises `IntegrityError` (`UniqueViolation`, pgcode `23505`) at the flush. A `token_hash` over 64 or a `family_id` over 36 characters raises `DataError` (pgcode `22001`). An unknown `user_id` or `workspace_id` raises `IntegrityError` (pgcode `23503`). `expires_at=None` raises `IntegrityError` (pgcode `23502`).
- **R4.** [BUG-1407] (P1) A `user_agent` over 512 characters is stored cut to its first 512, and an `ip_address` over 64 to its first 64; the row is written and nothing is raised. Exactly 512 / 64 are stored whole. *(Today: `DataError`, pgcode `22001`, at the flush.)*
- **R5.** Every parameter is keyword-only: positional arguments raise `TypeError`.

**Errors:** as R3, and today R4.

**Side effects:** one row inserted, flushed, not committed.

---

## `RefreshTokenDAO.revoke(db, *, row, replaced_by_id=None)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `AuthService.refresh_access_token` (with the successor's id), `logout_session` (without))

**Purpose:** Mark one token revoked, optionally naming its successor.

**Returns:** `None`.

**Rules:**
- **R1.** A row with no `revoked_at` gets `revoked_at = utcnow()`. A row that already has one keeps it: calling again later does not move the stamp.
- **R2.** When `replaced_by_id` is given, it is written, also on a row already revoked: a second call with another successor replaces the first successor. When it is `None`, the row's `replaced_by_id` is left as it was.
- **R3.** The decision in R1 reads the row object as the session holds it: if the row was revoked in the database by a bulk update after it was loaded (`revoke_family` R4), the session copy still shows no stamp and `revoke` writes a new one over the database's.
- **R4.** The change is flushed. An unknown `replaced_by_id` raises `IntegrityError` (pgcode `23503`) at the flush. If the successor row is deleted later, `replaced_by_id` becomes `NULL` (ON DELETE SET NULL).

**Errors:** as R4.

**Side effects:** the row's `revoked_at` / `replaced_by_id` updated and flushed.

---

## `RefreshTokenDAO.revoke_family(db, *, family_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `AuthService.refresh_access_token` when a token that was already rotated is presented again)

**Purpose:** Revoke every not-yet-revoked token of one login.

**Returns:** `int`, the number of rows stamped.

**Rules:**
- **R1.** ✅ (Q1) Every row with that `family_id` and no `revoked_at` gets `revoked_at = utcnow()` (one value for all), expired rows included. Rows already revoked keep their stamp and are not counted.
- **R2.** ✅ (Q2) The family is the only filter: rows of every user in that family are stamped. Rows of other families are untouched.
- **R3.** An unknown family, `""`, or a family with nothing left to revoke gives `0`; a second call gives `0`.
- **R4.** The update runs in the database and is flushed; rows already loaded in the session keep their old `revoked_at` until refreshed (verified).

**Errors:** none of its own.

**Side effects:** rows updated in the database, flushed, not committed.

---

## `RefreshTokenDAO.revoke_all_for_user(db, *, user_id)`
**Shape:** state-transition
**Persistence:** writes
**Visibility:** public (used by: `AuthService.logout_session` with `all_devices`; `AuthService.reset_password_by_admin`)

**Purpose:** Sign one person out of every session.

**Returns:** `int`, the number of rows stamped.

**Rules:**
- **R1.** ✅ (Q1) Every row of that user with no `revoked_at` gets `revoked_at = utcnow()`, whatever its family, workspace or expiry; rows already revoked keep their stamp and are not counted.
- **R2.** Rows of other users are untouched. An unknown user, `0`, or nothing left to revoke gives `0`.
- **R3.** As `revoke_family` R4: the session's loaded copies are not refreshed.

**Errors:** none of its own.

**Side effects:** rows updated in the database, flushed, not committed.

---

## `RefreshTokenDAO.touch_last_used(db, *, row)`
**Shape:** update
**Persistence:** writes
**Visibility:** public (used by: `AuthService.refresh_access_token`, on the old row after rotating it)

**Purpose:** Record when a token was last presented.

**Returns:** `None`.

**Rules:**
- **R1.** `last_used_at` is set to `utcnow()`, replacing any earlier value; nothing else on the row changes (a revoked row stays revoked). Flushed.

**Errors:** none.

**Side effects:** one row updated, flushed.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 21–30 | exact hash; `.first()` row / `None`; no scope | `get_by_hash` R1, R2 |
| 32–33 | `get_by_id` | Not specified (Q3) |
| 35–62 | keyword-only; optional `None`s; flush: unique, length (BUG-1407), FK, NOT NULL | `create` R1–R5 |
| 72–73 | `revoked_at is None` → stamp / keep | `revoke` R1, R3 |
| 74–75 | `replaced_by_id is not None` → write / leave | `revoke` R2 |
| 76 | flush; FK on successor | `revoke` R4 |
| 83–93 | bulk UPDATE family AND not revoked; `rowcount or 0`; no session sync | `revoke_family` R1–R4 |
| 97–107 | bulk UPDATE user AND not revoked; `rowcount or 0` | `revoke_all_for_user` R1–R3 |
| 111–112 | set `last_used_at`; flush | `touch_last_used` R1 |
| 114 | module singleton | Not specified |
