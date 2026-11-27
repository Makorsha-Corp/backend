# Spec — `app/utils/profile_auth.py`

> **Status:** APPROVED
> **Source commit:** `e48a092`

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

No questions.

## Overview
A pure mapper that turns a user `Profile` into the small `user` dictionary sent
back in the register and login responses (`RegisterResponse.user`,
`LoginResponse.user`, both typed as a plain `dict` in `app/schemas/auth.py`, so
the shape is not validated anywhere else). It protects one invariant: the auth
response exposes only public profile fields — never `hashed_password`,
`user_id`, or `saved_stamp`.

**Callables:** 1 specified · 0 not specified
**Externals to mock:** none
**Integration-only behavior:** none

**Notes for the test designer:** the function has no database access. It can be
tested with a transient `Profile(...)` instance (never added to a session) or a
persisted one from the test DB; a plain object with the needed attributes also
works (the admin flag is read defensively). A transient `Profile` built without
`is_platform_admin` has that attribute as `None` (the column default `False` is
only applied on flush) — see R3.

## Not specified
_(none)_

---

## `profile_to_auth_dict(user)`
**Shape:** mapper
**Persistence:** pure
**Visibility:** public (used by: `POST /auth/register`, `POST /auth/login` in `app/api/v1/endpoints/auth.py`)

**Purpose:** Build the public user payload returned with auth tokens.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `user` | `Profile` (any object with `id`, `name`, `email`, `timezone`) | Not validated; missing `id`/`name`/`email`/`timezone` attributes raise `AttributeError`. `is_platform_admin` may be absent. |

**Returns:** a new `dict` with exactly five keys: `id`, `name`, `email`, `timezone`, `is_platform_admin`.

**Rules:**
- **R1.** The result has exactly the keys `id`, `name`, `email`, `timezone`, `is_platform_admin` — no other profile fields (in particular no `hashed_password`, `user_id`, `saved_stamp`).
- **R2.** `id`, `name`, `email` and `timezone` are copied unchanged from the profile (no trimming, case change or defaulting); a `None` timezone stays `None`.
- **R3.** `is_platform_admin` is always a real boolean: `True` when the profile's flag is truthy; `False` when the flag is `False`, `None`, or the attribute does not exist on the object.
- **R4.** The profile is not modified.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| object lacks `id`, `name`, `email` or `timezone` | `AttributeError` | Python default |

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 13 | `getattr(..., False)` — attribute present vs. absent | R3 |
| 13 | `bool(...)` — truthy vs. falsy (`True` / `False` / `None`) | R3 |
| 8–14 | fixed key set, fields copied as-is | R1, R2, R4 |
