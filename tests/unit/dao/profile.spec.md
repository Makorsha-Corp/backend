# Spec — `app/dao/profile.py`

> **Status:** APPROVED — Q1 answered by the owner (2026-11-04) (OQ-1): BUG-1860, BUG-1861, BUG-1862. Nothing else is open.
> **Source commit:** e48a092

> **Review round 2026-11-03.** **Delegated:** nothing needed a delegated answer. BUG-038 and BUG-500 are existing bugs (security spec) that reach `authenticate`; BUG-1406 stands from HR-1. **Owner round 2026-11-04:** Q1 answered by the owner (2026-11-04), suggested answer → BUG-1860, BUG-1861, BUG-1862.

> **Base behaviour** is in `tests/unit/dao/base.spec.md` and is not restated.
>
> **Verified by running** (throwaway scripts `facts.py`, `v_auth.py`, harness `h.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsdao\`, each in one transaction rolled back against `marker_test`; nothing committed): the table's columns and constraints; `create` with a mixed-case email, spaces in the name, a timezone with spaces, an empty password, 72- and 73-byte passwords, a dict, a taken email, an email equal to another profile's `user_id`; two profiles `Ann.Lee@example.com` and `ann.lee@example.com` side by side; `get_by_email` with other case and a leading space; `authenticate` with right, wrong, other-case, unknown, 73-byte and empty passwords and with an empty or malformed stored hash; `get_by_workspace` on `Profile`. **Not run:** anything over HTTP; timing (BUG-038); the intended behaviour of the bug rules.

## Review
> All questions answered.

### Quick list
| # | What the code does today, in plain words | Answer | Decided by |
|---|---|---|---|
| Q1 | An email is matched with its exact capital letters: `Ann@x.com` and `ann@x.com` can be two accounts, and logging in with other capitals fails | bug — BUG-1860, BUG-1861, BUG-1862 | **Owner** (2026-11-04) |

Decided by a house rule: a person's name is stored untrimmed and may be blank (BUG-1406, HR-1). Existing bugs that reach this DAO: BUG-038 (login timing), BUG-500 (over-long password raises).

### House-rule violations — applied automatically

- **HR-1** `create` R2 — the name is stored as typed: `"  Ann "` keeps its spaces, `""` and `"   "` are accepted (verified). `ProfileCreate.name` is a bare `str`; `RegisterRequest.name` has `min_length=1`, which `"   "` passes. Intended: `ProfileCreate` (and `RegisterRequest`, the API's entry point) strip the name and require at least one character after stripping (Pydantic `ValidationError`, 422 at the API); stored trimmed; inner spaces and case kept.
**Answer:** bug — per HR-1 (house rule)
**Resolution:** BUG-1406 (pattern `blank-name-accepted`; the fix is in `app/schemas/profile.py` and `app/schemas/auth.py`). `ProfileMeUpdate.name` (`PATCH /auth/me/`) has the same gap and belongs to the same fix; it is tested with the auth service. Rules: `create` R2.

Checked and **not** a new line here: **HR-2** — email uniqueness is enforced in the database (`profiles_email_key`), so the only open part is case, which is Q1. **HR-4** — profiles have no soft delete. **HR-5, HR-6, HR-7, HR-8** — no list. **HR-9** — no audit columns. **HR-10** — no state transition. **HR-16** — profiles are not workspace rows.

### Existing bugs that reach this DAO (not new)
- **BUG-038** (`timing-account-enumeration`, logged from the security spec against `authenticate`): an unknown email returns at once, a known one runs bcrypt. Rule `authenticate` R2a carries the tag; timing is not unit-testable, so the case checks only that a password check runs for an unknown email (see the note for the test designer).
- **BUG-500** (`error-message-account-enumeration`, `verify_password`): a password over 72 UTF-8 bytes raises `ValueError` for a known email and returns `None` for an unknown one. Rule `authenticate` R4 carries the tag; the fix is in `app/core/security.py`.

### New questions

### Q1. Email matching is case-sensitive — 🐞 BUG-1860, BUG-1861, BUG-1862 (answered by the owner (2026-11-04))
**Background:** Login, registration's "already registered" check and the password-reset lookup all find a profile with `get_by_email`, an exact comparison. The database's unique index on `email` is exact too. Pydantic's `EmailStr` lowers only the domain: `Ann.Lee@Example.COM` becomes `Ann.Lee@example.com`. Invitations, by contrast, are stored in lower case and accepted case-insensitively, and the waitlist lower-cases emails before storing.
**What happens today:** `Ann.Lee@example.com` and `ann.lee@example.com` can both register, as two accounts with two passwords (verified). Logging in as `ANN.LEE@example.com` fails with "Invalid email or password" (verified). Nobody knows today whether production already holds such pairs; this query tells: `SELECT lower(email), count(*) FROM profiles GROUP BY 1 HAVING count(*) > 1`.
**Example:** Ann registers as `Ann.Lee@factory.com`. A month later her phone capitalises nothing and she types `ann.lee@factory.com`: login fails. She clicks "register", which succeeds, and she now has a second, empty account with none of her workspaces. Worse, anyone who can receive mail at that address can do the same deliberately.
**Rules affected:** `get_by_email` R1, `create` R4, `authenticate` R1
**Suggested answer:** `bug — an email identifies one account whatever its capitals`: `get_by_email` matches `lower(trim(email))`; registration stores the email lower-cased; a unique index on `lower(email)` replaces the exact one; a script lists existing case-variant pairs for the owner to merge or close by hand (no automatic merge: two passwords and two sets of workspaces). **Alternatives:** (a) `intended` — keep exact matching (today); (b) only login and the "already registered" check become case-insensitive, existing pairs stay as they are, with no new index (smaller change, but a pair then cannot log in predictably).
**Answer:** bug — an email identifies one account whatever its capitals (the suggested answer; answered by the owner (2026-11-04), OQ-1).
**Resolution:** 🐞 BUG-1860 (`get_by_email` compares `lower(trim(email))` on both sides; `authenticate` follows it), 🐞 BUG-1861 (registration stores the email lower-cased), 🐞 BUG-1862 (a unique index on `lower(email)` replaces the exact `profiles_email_key`). Pattern `case-sensitive-email-match` (per BUG-1402). The script that lists existing case-variant pairs for a manual merge is part of the fix but not of this spec. Rules: `get_by_email` R1, `create` R4, R4a, R4b, `authenticate` R1.

## Follow-ups for other reviews
> Nothing below is a rule of this DAO and no bug is logged for it here.

| # | Where it must be looked at | What | Came from |
|---|---|---|---|
| FU-1 | **Auth service** (`app/services/auth_service.py`, not yet specified) | (a) After Q1 (BUG-1860, BUG-1861), `request_password_reset` and `register_user` must use the same matching, and `register_user` stores the email lower-cased; `WorkspaceManager.create_invitation`'s already-a-member check inherits BUG-1860. (b) `ProfileMeUpdate.name` HR-1 (part of BUG-1406). (c) `ProfileCreate` has no password minimum; `RegisterRequest` requires 8 — `create` hashes whatever it gets, `""` included. | Q1, HR-1 line |

## Overview
`DAOProfile` reads and creates `profiles`, the user accounts. It is global (no workspace column). `get_by_email` is the account lookup of registration, login, password reset and invitations; `create` makes an account with a bcrypt hash of the password; `authenticate` is the login check. Callers: `AuthService` (register ×3, login, reset), `WorkspaceManager.create_invitation`; the inherited `get` is used in about fifty places to read a person by id. It never commits.

**Callables:** 3 specified · 1 not specified (+ inherited, base spec)
**Externals to mock:** none. bcrypt runs for real (about a quarter of a second per hash or check); no clock is read.
**Integration-only behavior:** none

**Model facts (table `profiles`):** `name` VARCHAR NOT NULL (no length limit); `email` VARCHAR NOT NULL, **unique `profiles_email_key` (exact, case-sensitive; BUG-1862: to be replaced by a unique index on `lower(email)`)**; `user_id` VARCHAR NOT NULL, **unique `profiles_user_id_key`**; `hashed_password` VARCHAR NOT NULL; `timezone` VARCHAR(64) nullable; `is_platform_admin` BOOLEAN NOT NULL, default `false` (Python and database); `saved_stamp` JSONB nullable. No `workspace_id`, no soft delete, no timestamps. About 150 foreign keys in other tables point at `profiles.id`.

**Notes for the test designer:** `from app.dao.profile import profile_dao`. Build other profiles with `make_profile` (`tests/unit/factories.py`); it does not hash, so use `create` (or `get_password_hash`) where a real password is needed. Emails must be unique across concurrently running tests: add a unique suffix to the local part. **BUG-038:** patch `app.core.security.verify_password` with `wraps=` the real one (the DAO imports it inside the function, from `app.core.security`) and assert it is called once for an unknown email; today it is not called → **strict** xfail. **BUG-500:** strict xfail (today `ValueError`). **BUG-1406:** build `ProfileCreate(name="  Ann ")` / `ProfileCreate(name="   ")`; today the first is stored with its spaces and the second is accepted → **strict** xfail. **BUG-1860, BUG-1861, BUG-1862** (owner, Q1): build the mixed-case stored profile with `make_profile` (it stores the email as given, like rows saved before the fix); all three are **strict** xfail today. Keep the working parts (`get_by_email` R1, `create` R4) as plain passing cases.

## Not specified
- `profile_dao` — module-level singleton, no logic.
- Inherited `BaseDAO` methods — covered by the base spec. Specific here: `get_by_workspace` and `get_by_id_and_workspace` raise `AttributeError` (`Profile` has no `workspace_id`); `update` with a `ProfileUpdate` carrying `password` changes nothing for it (the model has no `password` attribute, so the key is skipped; base `update` R4) — no caller uses `ProfileUpdate` today.

---

## `DAOProfile.get_by_email(db, *, email)`
**Shape:** get
**Persistence:** reads
**Visibility:** public (used by: `authenticate`; `AuthService.register_user` (already-registered check), `request_password_reset`; `WorkspaceManager.create_invitation` (already-a-member check))

**Purpose:** The account registered under an email.

**Returns:** the `Profile`, or `None`.

**Rules:**
- **R1.** The profile stored with exactly the given text is found: `Ann.Lee@example.com` finds the profile stored as `Ann.Lee@example.com`.
- **R1a.** [BUG-1860] (Q1, owner) The email is compared as `lower(trim(...))` on both sides: for a profile stored as `Ann.Lee@example.com` (as older rows are), `ann.lee@example.com`, `ANN.LEE@EXAMPLE.COM` and ` Ann.Lee@example.com ` (outer spaces) all find it; for a profile stored as `ann.lee@example.com`, `Ann.Lee@example.com` finds it. Inner text still has to match: `ann.lee2@example.com` gives `None`. *(Today: exact match only; other capitals or an outer space give `None`. Verified.)*
- **R2.** An unknown email or `""` gives `None`, with no error. The email is unique in the database, so at most one profile matches.

**Errors:** none of its own.

**Side effects:** none

---

## `DAOProfile.create(db, *, obj_in)`
**Shape:** create
**Persistence:** writes
**Visibility:** public (used by: `AuthService._register_user_only`, `_register_with_invitation`, `_register_with_new_workspace`, always with a `ProfileCreate`). Replaces `BaseDAO.create`.

**Purpose:** Make a new account with a hashed password.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `obj_in` | `ProfileCreate` | `name: str` (BUG-1406), `email: EmailStr` (domain lowered by Pydantic), `password: str`, `timezone`: trimmed, blank → `None`, must be a valid IANA zone (schema validator) |

**Returns:** the new `Profile`, flushed (has its `id`), not committed.

**Rules:**
- **R1.** One profile is inserted with `name`, `email` and `timezone` from the schema, `user_id` equal to the email, `hashed_password` a bcrypt hash of the password (it starts `$2`, and `verify_password(password, hashed_password)` is true), `is_platform_admin = False`, `saved_stamp = None`. The same password hashed twice gives two different hashes (random salt).
- **R2.** [BUG-1406] (HR-1) The name is stored trimmed (`"  Ann "` → `"Ann"`), and a blank or whitespace-only name never reaches the DAO: `ProfileCreate(name="   ")` raises Pydantic `ValidationError`. *(Today: stored as typed; `""` and `"   "` accepted.)*
- **R3.** The password is not checked for strength: `""` is hashed and stored. A password of exactly 72 UTF-8 bytes is accepted; 73 bytes raise `ValueError("Password exceeds bcrypt's 72-byte limit")` before anything is added.
- **R4.** A taken email (exact text) raises `IntegrityError` (`UniqueViolation`, pgcode `23505`) at the flush. An email equal to another profile's `user_id` raises `IntegrityError` on `profiles_user_id_key`.
- **R4a.** [BUG-1861] (Q1, owner) The email is stored lower-cased: `ProfileCreate(email="Ann.Lee@Example.COM")` is stored as `ann.lee@example.com`, and `user_id` equals the stored email (R1). *(Today: only the domain is lowered (by `EmailStr`): stored `Ann.Lee@example.com`. Verified. The fix may sit in `ProfileCreate` / `RegisterRequest` or in `create`; the test goes through `create` with a `ProfileCreate`.)*
- **R4b.** [BUG-1862] (Q1, owner) A second account for the same address with other capitals is refused by the database: with a profile stored as `Ann.Lee@example.com` (built with `make_profile`, as an older row), creating `ann.lee@example.com` raises `IntegrityError` (pgcode `23505`) at the flush, from a unique index on `lower(email)` that replaces the exact `profiles_email_key`. *(Today: accepted as a second account. Verified. Requires a migration; it fails while case-variant pairs exist, which the fix's listing script finds for a manual merge.)*
- **R5.** Only a schema works: a plain dict raises `AttributeError` (`'dict' object has no attribute 'name'`) before anything is added.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| password over 72 UTF-8 bytes | `ValueError` | `Password exceeds bcrypt's 72-byte limit` |
| taken email or `user_id` | `sqlalchemy.exc.IntegrityError`, pgcode `23505` | — |
| `obj_in` is a dict | `AttributeError` | `'dict' object has no attribute 'name'` |

**Side effects:** one row inserted, flushed, not committed.

---

## `DAOProfile.authenticate(db, *, email, password)`
**Shape:** validator
**Persistence:** reads
**Visibility:** public (used by: `AuthService.login_user` ← `POST /auth/login/`, which turns `None` into "Invalid email or password")

**Purpose:** The account for an email and password, if the password is right.

**Returns:** the `Profile`, or `None`.

**Rules:**
- **R1.** Given the email of a profile (found as `get_by_email` R1) and its right password, that profile is returned.
- **R1a.** [BUG-1860] (Q1, owner) The email is found as `get_by_email` R1a: for a profile stored as `Ann.Lee@example.com`, logging in as `ANN.LEE@example.com` with the right password returns it. *(Today: `None`, "Invalid email or password" at the API. Verified.)*
- **R2.** An unknown email gives `None`.
- **R2a.** [BUG-038] For an unknown email a password check is still run (against a dummy hash), so the answer takes as long as for a known one. *(Today: returns at once, without checking any password.)*
- **R3.** A wrong password gives `None`. A stored hash that is empty, or is not a bcrypt hash at all (`"not-a-hash"`), gives `None`, never an error. An empty password against a real hash gives `None`.
- **R4.** [BUG-500] A password over 72 UTF-8 bytes gives `None`, for a known email as for an unknown one. *(Today: for a known email `ValueError("Password exceeds bcrypt's 72-byte limit")` is raised; for an unknown email `None`.)*
- **R5.** Nothing is written.

**Errors:** today only `ValueError` of R4 (BUG-500).

**Side effects:** none

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 25 | exact `email ==` (BUG-1860); `.first()` row / `None` | `get_by_email` R1, R1a, R2 |
| 38–44 | fields from the schema; `user_id = email` (BUG-1861); hash (72-byte limit) | `create` R1, R2, R3, R4a, R5 |
| 45–47 | flush: unique email (BUG-1862) / `user_id`; no commit | `create` R4, R4b |
| 63–65 | no profile → `None` (BUG-038) | `authenticate` R2, R2a |
| 66–67 | `verify_password` false → `None`; empty / bad hash; over 72 bytes raises (BUG-500) | `authenticate` R3, R4 |
| 68 | match → profile | `authenticate` R1, R1a, R5 |
| `core/security.py` 55–65 | empty hash → false; > 72 bytes raise; bcrypt error → false | `authenticate` R3, R4 |
| `core/security.py` 84–89 | > 72 bytes raise; salt + hash | `create` R1, R3 |
| 71 | module singleton | Not specified |
