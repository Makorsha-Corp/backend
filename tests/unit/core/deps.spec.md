# Spec — `app/core/deps.py`

> **Status:** APPROVED
> **Source commit:** e48a092

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

_No house-rule violations (neither `Profile` nor `Workspace` has a soft-delete
column; nothing here lists, searches, names or audits). No precedent matches._

### New questions

### Q1. "Active user" check does not check anything — ✅ intended
**Background:** Almost every endpoint (≈340 uses) depends on
`get_current_active_user`. Its docstring says it rejects inactive users, but
user profiles have no active/disabled/banned flag at all; the only "suspended"
concept is per-workspace membership (`workspace_members.status`), which
`get_current_workspace` already enforces.
**What happens today:** `get_current_active_user` returns whatever user the token
resolves to, with no further check. There is no way to lock a user out of the
whole product other than deleting their profile row.
**Example:** An employee leaves; an admin wants to disable their account
everywhere. There is no switch for that — until their access token expires
(15 min) and as long as their refresh token works, every endpoint that does not
need a workspace (profile, workspace list, notifications, …) keeps answering them.
**Rules affected:** `get_current_active_user` R1 ✅
**Suggested answer:** intended
**Answer:** intended (reviewer accepted suggestion)
**Resolution:** no active/disabled flag on profiles; `get_current_active_user` stays a pass-through. Rules: `get_current_active_user` R1.

### Q2. Non-members can tell which workspace ids exist — 🐞 BUG-440
**Background:** Every workspace-scoped request sends the workspace id in the
`X-Workspace-ID` header. Workspace ids are sequential integers.
**What happens today:** A non-existent id gets 404 "Workspace with ID N not
found", while an existing workspace the caller is not a member of gets 403 "You
do not have access to this workspace".
**Example:** A signed-in user of workspace 3 sends `X-Workspace-ID: 4`, `5`, `6`…
and gets 403 for 4 and 5 and 404 for 6 — learning that exactly 5 workspaces
exist (i.e. how many customers the product has), without being a member of any.
**Rules affected:** `get_current_workspace` R5, R8
**Suggested answer:** bug — a caller who is not an active member (and not a platform admin) gets the same 404 "Workspace with ID N not found" as for a workspace that does not exist
**Answer:** bug — a caller who is not an active member (and not a platform admin) gets the same 404 "Workspace with ID N not found" as for a workspace that does not exist (reviewer accepted suggestion)
**Resolution:** a workspace the caller may not act in (no membership, or membership not exactly `"active"`, and not a platform admin) is indistinguishable from a non-existent one: 404 `"Workspace with ID {id} not found"`. Rules: `get_current_workspace` R8, R9 (R5 unchanged).

### Q3. Workspace access ignores the subscription state — ✅ intended
**Background:** Workspaces carry `subscription_status` (default `trial`),
`trial_ends_at` and `subscription_ends_at`. No code anywhere in the backend reads
these to restrict access; `get_current_workspace` is the single gate every
workspace-scoped endpoint goes through.
**What happens today:** Any active member can use a workspace regardless of its
subscription status or whether its trial/subscription end date has passed.
**Example:** A workspace's trial ended 60 days ago and it never paid
(`subscription_status = "trial"`, `trial_ends_at` in the past, or status
`"cancelled"`). Its members keep creating orders and invoices exactly as before.
**Rules affected:** `get_current_workspace` R10 ✅
**Suggested answer:** intended
**Answer:** intended (reviewer accepted suggestion)
**Resolution:** subscription state is not enforced by this dependency. Rules: `get_current_workspace` R10.

## Overview
FastAPI dependency functions shared by every endpoint: open/close the request's
database session, turn the `Authorization: Bearer <JWT>` header into the
signed-in `Profile`, resolve the `X-Workspace-ID` header into a `Workspace` the
user may act in, and gate platform-admin (Makorsha staff) endpoints. Invariants:
no endpoint runs for an unauthenticated caller; a workspace-scoped endpoint only
runs for an active member of that workspace, or for a platform admin.

The access token also carries a `workspace_id` claim (set at login/switch), but
nothing in this file reads it: the header alone decides the workspace.

**Callables:** 5 specified · 0 not specified
**Externals to mock:** none (JWT signing is local via PyJWT and `settings.SECRET_KEY`/`settings.ALGORITHM`; do not mock it)
**Integration-only behavior:** none beyond the FastAPI wiring itself (`Depends` chaining, `HTTPBearer` header parsing) — see notes below for how to cover it in unit tests.

**Notes for the test designer:**
- This is framework glue. `get_current_user`, `get_current_active_user`,
  `get_current_workspace` and `get_platform_admin` are plain functions: call them
  directly, passing the real test `db` session and plain arguments —
  `HTTPAuthorizationCredentials(scheme="Bearer", credentials=<token>)` for
  `get_current_user`; a `starlette.requests.Request` built from a minimal ASGI
  scope (`{"type": "http", "headers": [(b"x-workspace-id", b"5")]}`) for
  `get_current_workspace`; a `Profile` instance for `current_user`.
- Behavior owned by `HTTPBearer` (missing/malformed `Authorization` header) is
  only observable through FastAPI: mount the dependency on a route in a minimal
  `FastAPI()` app, override `get_db` with `app.dependency_overrides[get_db] =
  lambda: db` (the test session), and use `TestClient`. Never start the real app.
- Make tokens with `jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)`
  or `app.core.security.create_access_token`. PyJWT checks `exp` against the real
  clock, not the mocked `utcnow`: to get an expired token, encode an `exp` in the
  real past directly; if `utcnow` is mocked, `create_access_token` stamps `exp`
  from the mocked time.
- `WorkspaceMember` rows need `workspace_id`, `user_id` and `role` (free-text `VARCHAR(50)`, e.g. `"owner"`); `status`, `invited_at`, `created_at`, `updated_at` have Python-side defaults. `status` accepts any string up to 50 chars (no CHECK constraint).
- For `get_current_workspace` R11, a plain object (e.g. `types.SimpleNamespace(id=<profile id>)`) is enough: only `id` is read once the admin check falls back to `False`.
- `get_db` uses the module-level `SessionLocal` bound to the dev `DATABASE_URL`;
  test it by monkeypatching `app.core.deps.SessionLocal` with a factory returning
  a spy session (records `close()` calls), and drive the generator with `next()`,
  `.close()` and `.throw(exc)`.

## Not specified
- `security` (module-level `HTTPBearer()` instance) — configuration, no logic of its own; its observable effect is described under `get_current_user` R1–R2.

---

## `get_db()`
**Shape:** helper
**Persistence:** pure (opens and closes a session; no queries)
**Visibility:** public (FastAPI dependency of every endpoint, and of `get_current_user` / `get_current_workspace`)

**Purpose:** Give each request its own database session and always close it afterwards.

**Inputs:** none

**Returns:** a generator that yields exactly one new session from `SessionLocal`
(configured `autocommit=False`, `autoflush=False`). Only `autoflush is False` is
observable on the yielded session: SQLAlchemy 2.x (installed 2.0.51) sessions have
no `autocommit` attribute — `autocommit=False` is the only mode 2.x supports, so
there is nothing to assert for it.

**Rules:**
- **R1.** Advancing the generator yields one newly created session; each call of `get_db()` creates a separate session.
- **R2.** When the consumer finishes normally (generator closed or exhausted after the yield), the session is closed exactly once.
- **R3.** When an exception is thrown into the generator at the yield (the request handler failed), the session is still closed exactly once and the same exception propagates out unchanged.
- **R4.** `get_db` itself never commits or rolls back; uncommitted work is discarded only by `close()` (committing is the service layer's job).

**Errors:** none of its own (see R3).

**Side effects:** creates and closes one session.

---

## `get_current_user(credentials, db)`
**Shape:** get-or-404 (401 variant)
**Persistence:** reads
**Visibility:** public (dependency of `get_current_active_user`, `get_current_workspace`, and endpoints directly)

**Purpose:** Resolve the bearer JWT to the signed-in user's profile.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `credentials` | `HTTPAuthorizationCredentials` | from `HTTPBearer()`; `.credentials` is the raw token string |
| `db` | `Session` | request session |

**Returns:** the `Profile` whose `id` equals the token's `sub` claim (as loaded, not modified).

**Rules:**
- **R1.** *(via `HTTPBearer`, FastAPI-level)* A request with no `Authorization` header, a non-`Bearer` scheme (e.g. `Basic abc`), or `Bearer` with an empty token is rejected with 401, detail `"Not authenticated"`, header `WWW-Authenticate: Bearer`, before any token decoding or database access.
- **R2.** *(via `HTTPBearer`)* The scheme word is case-insensitive: `bearer abc` is accepted and `abc` is treated as the token.
- **R3.** Every rejection below is the same error: `HTTPException` 401, detail `"Could not validate credentials"`, headers `{"WWW-Authenticate": "Bearer"}`.
- **R4.** A token that is not a well-formed JWT (random text, truncated, bad base64) → 401 (R3).
- **R5.** A token signed with a different secret → 401 (R3).
- **R6.** A token whose header algorithm is not exactly `settings.ALGORITHM` (`HS256`) → 401, even if signed with the right secret (e.g. `HS512`, or `alg: none` unsigned).
- **R7.** A token whose `exp` is in the past → 401. A token with a `nbf` in the future or a non-numeric `exp`/`iat`/`nbf` → 401.
- **R8.** A validly signed token with **no** `exp` claim is accepted (expiry is not required).
- **R9.** A validly signed token with no `sub` claim → 401.
- **R10.** A `sub` claim that is not a JSON string (e.g. the number `5`) → 401 (rejected by PyJWT's subject check).
- **R11.** A string `sub` that Python's `int()` cannot parse (`"abc"`, `""`, `"5.0"`) → 401.
- **R12.** A string `sub` that `int()` accepts is used as the user id: `"5"`, `" 5 "`, `"+5"` and `"0_5"` all resolve user 5; `"-1"` or `"0"` are parsed and then match no user (→ R13).
- **R13.** A valid token whose `sub` id has no `Profile` row (e.g. the user was deleted) → 401 (R3).
- **R14.** A valid token whose `sub` matches an existing profile returns that profile. Other claims (`email`, `workspace_id`) are ignored — a token whose `email` differs from the profile's current email still resolves the profile.
- **R15.** A platform-admin profile resolves the same way as any other (no special treatment here).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Missing / non-Bearer / empty `Authorization` (FastAPI-level) | `HTTPException` 401, `WWW-Authenticate: Bearer` | `Not authenticated` |
| Undecodable, wrong key/alg, expired, bad `sub`, unknown user | `HTTPException` 401, `WWW-Authenticate: Bearer` | `Could not validate credentials` |

**Side effects:** none (one read of `profiles` by id).

---

## `get_current_active_user(current_user)`
**Shape:** helper
**Persistence:** pure
**Visibility:** public (dependency of most endpoints and of `get_platform_admin`)

**Purpose:** Documented as "reject inactive users"; today a pass-through.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `current_user` | `Profile` | output of `get_current_user` |

**Returns:** the same `Profile` object it was given (identity, unmodified).

**Rules:**
- **R1.** Returns the given profile unchanged, for every profile — there is no active/inactive check. Authentication failures surface from `get_current_user` (its R1–R13). *(See Q1.)* ✅

**Errors:** none.

**Side effects:** none.

---

## `get_current_workspace(request, db, current_user)`
**Shape:** get-or-404
**Persistence:** reads
**Visibility:** public (dependency of every workspace-scoped endpoint)

**Purpose:** Resolve the `X-Workspace-ID` header to a workspace and ensure the signed-in user may act in it.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `request` | `Request` | only the `x-workspace-id` header is read (header name case-insensitive) |
| `db` | `Session` | request session |
| `current_user` | `Profile` | output of `get_current_user`. Only two attributes are read: `is_platform_admin` (via `getattr`, default `False`) and `id` — the profile primary key (`profiles.id`), matched against `workspace_members.user_id` for the membership lookup. Nothing else on the object is touched. |

**Returns:** the `Workspace` row with the header's id (as loaded, not modified).

**Rules:**
- **R1.** Header absent → 400, detail `"X-Workspace-ID header is required"`.
- **R2.** Header present but empty (`""`) → same 400 as R1.
- **R3.** Header value that Python's `int()` cannot parse (`"abc"`, `"5.0"`, `"0x5"`, `"   "`) → 400, detail `"X-Workspace-ID must be a valid integer"`.
- **R4.** Header values `int()` accepts are used as the id: `"5"`, `" 5 "`, `"+5"`, `"0_5"` all mean workspace 5. Negative, zero and very large values (e.g. `"-1"`, `"0"`, `"99999999999999999999"`) parse and then match no workspace (→ R5) — no 500.
- **R5.** No workspace row with that id → 404, detail `"Workspace with ID {id} not found"` with the parsed integer (e.g. header `" 07 "` → `"Workspace with ID 7 not found"`). This check runs before, and regardless of, membership.
- **R6.** Workspace exists and `current_user.is_platform_admin` is truthy → the workspace is returned, with no membership needed (platform staff may act in any workspace).
- **R7.** Workspace exists, user is not a platform admin, and has a membership row for this workspace with `status == "active"` (exact, case-sensitive) → the workspace is returned.
- **R8.** [BUG-440] Workspace exists, user is not a platform admin, and has no membership row for it → 404, detail `"Workspace with ID {id} not found"` — exactly the same status and detail as R5 for a non-existent id, so the caller cannot tell the two apart. A membership in a *different* workspace does not count. *(Today: 403, detail `"You do not have access to this workspace"`.)* *(See Q2.)*
- **R9.** [BUG-440] Workspace exists, user is not a platform admin, and their membership for it has any status other than exactly `"active"` (`"suspended"`, `"invited"`, `"Active"`) → same 404 as R8/R5. *(Today: same 403 as today's R8.)* `workspace_members.status` is a free-text `VARCHAR(50) NOT NULL` (model default `'active'`) with no enum or CHECK constraint in the model or the migration baseline, so any of these strings can be stored directly.
- **R10.** The workspace's subscription fields (`subscription_status`, `trial_ends_at`, `subscription_ends_at`) are not considered: a workspace in any subscription state is returned under R6/R7. *(See Q3.)* ✅
- **R11.** A `current_user` object without an `is_platform_admin` attribute is treated as a non-admin (R7–R9 apply); its `id` attribute (profile primary key) is what the membership lookup uses.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Header missing or empty | `HTTPException` 400 | `X-Workspace-ID header is required` |
| Header not an integer | `HTTPException` 400 | `X-Workspace-ID must be a valid integer` |
| No workspace with that id | `HTTPException` 404 | `Workspace with ID {id} not found` |
| Not platform admin and no active membership [BUG-440] | `HTTPException` 404 *(today 403 `You do not have access to this workspace`)* | `Workspace with ID {id} not found` |

Error precedence: header checks (400) → existence or access (404, identical for both) *(today: existence 404 → access 403)*.

**Side effects:** none (reads `workspaces` by id and, for non-admins, the user's `workspace_members` row).

---

## `get_platform_admin(current_user)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (dependency of `/platform` endpoints)

**Purpose:** Allow only Makorsha platform staff.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `current_user` | `Profile` | output of `get_current_active_user` |

**Returns:** the same `Profile` object when allowed.

**Rules:**
- **R1.** A profile with `is_platform_admin` true → returned unchanged.
- **R2.** A profile with `is_platform_admin` false → 403, detail `"Platform admin access required"`.
- **R3.** An object without an `is_platform_admin` attribute, or with a falsy value (`None`), → same 403 as R2.
- **R4.** Workspace membership plays no role: a platform admin with no memberships passes; a workspace `owner` who is not a platform admin is rejected.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Not a platform admin | `HTTPException` 403 | `Platform admin access required` |

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 17 (`HTTPBearer()`, auto_error) | header missing / wrong scheme / empty token | `get_current_user` R1, R2 |
| 27–29 | session created and yielded | `get_db` R1 |
| 30–31 | `finally: close()` — normal exit | `get_db` R2, R4 |
| 30–31 | `finally: close()` — exception thrown in | `get_db` R3 |
| security.py 130–134 (`decode_token`) | `jwt.decode` ok vs `PyJWTError` → `None` (malformed, key, alg, exp/nbf, non-string sub) | `get_current_user` R4–R8, R10 |
| 60 | `payload is None` | `get_current_user` R4–R7, R10 |
| 65 | `sub` missing | `get_current_user` R9 |
| 68–71 | `int(sub)` ok vs `ValueError`/`TypeError` | `get_current_user` R11, R12 |
| 73–76 | profile found vs not | `get_current_user` R13, R14, R15 |
| 97 | unconditional return | `get_current_active_user` R1 |
| 122 | header falsy (absent / `""`) | `get_current_workspace` R1, R2 |
| 129–135 | `int(header)` ok vs `ValueError` | `get_current_workspace` R3, R4 |
| 138–143 (`BaseDAO.get`) | workspace found vs `None` | `get_current_workspace` R4, R5 |
| 146 | `is_platform_admin` truthy (getattr default False) | `get_current_workspace` R6, R11 |
| workspace_member.py (`has_access` → `get_by_workspace_and_user`) | membership row missing | `get_current_workspace` R8 |
| workspace_member.py (`has_access`) | `status == 'active'` vs other | `get_current_workspace` R7, R9 |
| 150–158 | subscription fields never checked | `get_current_workspace` R10 |
| 165 | `is_platform_admin` falsy / missing | `get_platform_admin` R1–R4 |

## Gap log
- G1 (deps.cases.md gap 1) — Fact — `workspace_members.status` is free-text `VARCHAR(50) NOT NULL`, default `'active'`, no enum/CHECK (model + squashed baseline); added to `get_current_workspace` R9 and a test-designer note. `"Active"`/`"invited"` rows can be inserted as-is.
- G2 (deps.cases.md gap 2) — Fact — the membership lookup uses `current_user.id` (profile primary key → `workspace_members.user_id`); added to `get_current_workspace` Inputs and R11, plus a test-designer note (`SimpleNamespace(id=...)` suffices).
- G3 (deps.cases.md gap 3) — Test mechanics — `autocommit` is not an attribute of a SQLAlchemy 2.x session (2.0.51 installed); `get_db` Returns now says only `autoflush is False` is observable/asserted.
