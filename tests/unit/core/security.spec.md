# Spec — `app/core/security.py`

> **Status:** APPROVED
> **Source commit:** `e48a092`

## Review
> Reviewer: answer each question on its **Answer:** line with one of
> `intended` · `bug` · `bug — <what it should do instead>` · `remove` (unreachable
> code only) · or a question back.
> Then run the describer in `apply-review` mode.

### New questions

### Q1. An over-long password at login tells an attacker whether the email is registered — 🐞 BUG-500
**Background:** bcrypt can only use the first 72 bytes of a password. Registration
and password-change schemas already reject passwords longer than 72 UTF-8 bytes,
but the login schema (`LoginRequest.password`) has no length limit. The login
endpoint turns any `ValueError` from the login flow into a 401 whose detail is the
error's text. For an unknown email the login flow never checks the password.
**What happens today:** checking a password longer than 72 bytes raises
`ValueError("Password exceeds bcrypt's 72-byte limit")` instead of returning
`False`.
**Example:** an attacker posts `{"email": "ceo@acme.com", "password": "<73 x 'a'>"}`
to `/auth/login/`. If the account exists the reply is 401 "Password exceeds
bcrypt's 72-byte limit"; if it does not exist the reply is 401 "Invalid email or
password". Comparing the two messages reveals which emails have accounts.
**Rules affected:** `verify_password` R2
**Suggested answer:** bug — `verify_password` returns `False` (never raises) for a plain password longer than 72 UTF-8 bytes, so login answers "Invalid email or password" either way
**Answer:** bug — `verify_password` returns `False` (never raises) for a plain password longer than 72 UTF-8 bytes, so login answers "Invalid email or password" either way (reviewer accepted suggestion)
**Resolution:** `verify_password` never raises on password length; a plain password over 72 UTF-8 bytes returns `False` against any hash — including a hash of its own first 72 bytes (no silent truncation) (best-practice default, delegated by reviewer). The timing side of login enumeration is tracked separately as BUG-038. Rules: `verify_password` R2.

### Q2. Password-hash docstring says long passwords are truncated, but they are rejected — ✅ intended
**Background:** `get_password_hash` is used when a user registers and when an admin
resets a password. Every public schema already rejects passwords over 72 bytes
before this function is reached.
**What happens today:** the function's note says passwords longer than 72 bytes
"will be truncated", but the code raises `ValueError("Password exceeds bcrypt's
72-byte limit")` and hashes nothing.
**Example:** a script calling `get_password_hash("a" * 73)` expecting a hash of the
first 72 characters instead gets a `ValueError`.
**Rules affected:** `get_password_hash` R2
**Suggested answer:** intended (rejecting is the safe behavior; the docstring is stale and should be corrected)
**Answer:** intended (rejecting is the safe behavior; the docstring is stale and should be corrected) (reviewer accepted suggestion)
**Resolution:** rejection is the intended behavior; `get_password_hash` R2 unchanged. The stale docstring note ("will be truncated") should be corrected when the module is next edited — documentation only, no BUG ID, no test impact.

### Q3. An expiry of zero is ignored and the token gets the default 15 minutes — 🐞 BUG-501
**Background:** `create_access_token` takes an optional custom lifetime. No caller
in the app passes one today; every access token uses the configured default
(`ACCESS_TOKEN_EXPIRE_MINUTES`, 15). The code checks the lifetime by truthiness,
and a zero-length `timedelta` counts as "not given".
**What happens today:** `expires_delta=timedelta(0)` produces a token valid for the
default 15 minutes instead of one that is already expired. A negative lifetime is
honoured (token already expired).
**Example:** a test or future feature calls
`create_access_token({"sub": "5"}, expires_delta=timedelta(0))` to mint an
immediately-expired token; the token is accepted by `decode_token` for the next 15
minutes.
**Rules affected:** `create_access_token` R3
**Suggested answer:** bug — any explicitly passed `expires_delta` (including zero) is honoured; only `None` falls back to the default
**Answer:** bug — any explicitly passed `expires_delta` (including zero) is honoured; only `None` falls back to the default (reviewer accepted suggestion)
**Resolution:** `expires_delta=None` → default lifetime; any `timedelta` passed (zero, positive or negative) → `exp = utcnow() + expires_delta`. Rules: `create_access_token` R2, R3 (split: R3 working part, R3a bug).

### Q4. A validly signed token with no expiry is accepted forever — 🐞 BUG-502
**Background:** tokens are signed with the server's `SECRET_KEY`. The JWT library
only checks expiry when the token carries an `exp` claim; it does not require one.
Every token this app issues has `exp`, so this only matters if a token without one
is ever signed with the key (e.g. by a script, another service sharing the key, or
a future code path).
**What happens today:** `decode_token` returns the payload of a correctly signed
token that has no `exp` claim; such a token never expires.
**Example:** a maintenance script signs `{"sub": "1"}` with the production key and
the token leaks; it keeps authenticating user 1 indefinitely, even years later.
**Rules affected:** `decode_token` R4
**Suggested answer:** bug — `decode_token` requires the `exp` claim (tokens without it return `None`)
**Answer:** bug — `decode_token` requires the `exp` claim (tokens without it return `None`) (reviewer accepted suggestion)
**Resolution:** a correctly signed token without an `exp` claim is rejected (`None`), like any other invalid token. Rules: `decode_token` R4.

## Overview
Low-level authentication primitives: issuing and verifying signed JWT access
tokens, hashing and checking user passwords with bcrypt, and generating/hashing
opaque refresh tokens. Called by `AuthService` (token pair issuance, refresh
rotation, admin password reset), `DAOProfile` (user creation, login
authentication), the `get_current_user` dependency (access-token decoding), the
`/auth/logout/` endpoint and `MobileUploadSessionManager` (sha256 hashing of opaque
tokens). Invariants: access tokens always carry an expiry and are signed with the
configured key/algorithm; stored passwords and refresh tokens are never the raw
secret; decoding never raises on a bad token.

**Callables:** 6 specified · 0 not specified
**Externals to mock:** `utcnow` (patch `app.core.security.utcnow`, the name imported into this module) to make `exp` deterministic; nothing else — bcrypt, PyJWT, `hashlib` and `secrets` run for real.
**Integration-only behavior:** none

**Notes for the test designer:**
- Pure module, no database. Call the functions directly; no app or session needed.
- Settings are read at call time from `app.core.config.settings`:
  `SECRET_KEY` (default `"your-secret-key-change-this-in-production"`),
  `ALGORITHM` (default `"HS256"`), `ACCESS_TOKEN_EXPIRE_MINUTES` (default `15`).
  Tests can `monkeypatch.setattr(settings, "SECRET_KEY", ...)` etc. To verify a
  token independently, decode it with `jwt.decode(token, settings.SECRET_KEY,
  algorithms=[settings.ALGORITHM], options={"verify_exp": False})`.
- `utcnow()` returns a **naive** UTC datetime; PyJWT encodes it as the POSIX
  timestamp of that UTC instant (seconds, fractional part dropped). So with
  `utcnow` patched to `datetime(2026, 1, 1, 12, 0, 0)` and the default 15 minutes,
  `exp == int(datetime(2026, 1, 1, 12, 15, tzinfo=timezone.utc).timestamp())`.
- `decode_token` checks `exp` against the **real** clock (PyJWT uses
  `datetime.now(timezone.utc)`, not `utcnow`), with zero leeway. For "expired"
  cases, patch `utcnow` to a time in the past (or pass a negative `expires_delta`)
  when creating the token.
- bcrypt hashing uses cost 12 (~0.2–0.3 s each); keep the number of real hashes
  small, or reuse one hash across cases.
- Installed library versions: PyJWT 2.13.0, bcrypt 5.0.0. A short `SECRET_KEY`
  triggers PyJWT's `InsecureKeyLengthWarning` — use a key of ≥ 32 bytes in tests.

## Not specified
(none)

---

## `create_access_token(data, expires_delta=None)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `AuthService._issue_token_pair`)

**Purpose:** Build a signed JWT access token carrying the given claims plus an expiry.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `data` | `dict[str, Any]` | Claims to embed. Values must be JSON-serialisable; nothing else checked. In practice `{"sub": "<user id>", "email": ..., optional "workspace_id": ...}`. |
| `expires_delta` | `timedelta \| None` | Custom lifetime. Default `None`. No caller passes it. |

**Returns:** the encoded JWT as a `str` (three dot-separated base64url segments), signed with `settings.SECRET_KEY` using `settings.ALGORITHM`.

**Rules:**
- **R1.** The token's payload contains every key/value of `data` unchanged, plus an `exp` claim; the header's `alg` is `settings.ALGORITHM` and the signature verifies with `settings.SECRET_KEY`.
- **R2.** When `expires_delta` is `None`, `exp` is `utcnow()` + `settings.ACCESS_TOKEN_EXPIRE_MINUTES` minutes (as a whole-second UTC timestamp).
- **R3.** When `expires_delta` is a non-zero `timedelta` (positive or negative), `exp` is `utcnow()` + `expires_delta`. A negative lifetime gives an already-expired token.
- **R3a.** [BUG-501] When `expires_delta` is a zero `timedelta` (`timedelta(0)`), `exp` is exactly `utcnow()` (the lifetime is honoured, not replaced by the default); only `None` falls back to the default of R2. *(Today: a zero `timedelta` is treated like `None` and the token gets the default 15 minutes.)*
- **R4.** If `data` already contains an `exp` key, it is replaced by the computed expiry.
- **R5.** The caller's `data` dict is not modified (no `exp` key is added to it).
- **R6.** A `data` value that is not JSON-serialisable (e.g. a `datetime` other than `exp`, a set) makes the call raise `TypeError`; no token is returned.

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| Non-JSON-serialisable claim value | `TypeError` | from the JSON encoder (not asserted) |

**Side effects:** none.

---

## `verify_password(plain_password, hashed_password)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `DAOProfile.authenticate`, i.e. login)

**Purpose:** Check a plain-text password against a stored bcrypt hash.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `plain_password` | `str` | Password typed by the user. Any length; over 72 UTF-8 bytes never matches (see R2). At login it comes from `LoginRequest.password`, which has no length limit. |
| `hashed_password` | `str` (bytes also accepted) | Stored bcrypt hash (`Profile.hashed_password`). May be empty/`None`. |

**Returns:** `True` if the password matches the hash, else `False`.

**Rules:**
- **R1.** When `hashed_password` is empty (`""`) or `None`, returns `False` without looking at the password — even when the password is longer than 72 bytes.
- **R2.** [BUG-500] When `plain_password` is longer than 72 bytes once UTF-8 encoded (bytes, not characters: 25 × "৳" = 75 bytes counts as too long; exactly 72 bytes is allowed and follows R3), returns `False` and never raises — for any non-empty `hashed_password`, including a valid hash of the password's own first 72 bytes (no silent truncation; best-practice default, delegated by reviewer). *(Today: raises `ValueError("Password exceeds bcrypt's 72-byte limit")`, which the login endpoint shows as a distinct 401 message only for registered emails.)*
- **R3.** When the password is the one that produced the hash (e.g. by `get_password_hash`), returns `True`; any other password (different case, extra trailing space, empty string) returns `False`.
- **R4.** When `hashed_password` is non-empty but not a valid bcrypt hash (e.g. `"garbage"`, a sha256 hex string), returns `False` instead of raising.
- **R5.** `hashed_password` may be given as `str` or as `bytes`; both give the same result.

**Errors:** none intended (R2 — [BUG-500]; today a `plain_password` > 72 UTF-8 bytes with a non-empty `hashed_password` raises `ValueError("Password exceeds bcrypt's 72-byte limit")`).

**Side effects:** none.

---

## `get_password_hash(password)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `DAOProfile.create` at registration, `AuthService` admin password reset)

**Purpose:** Produce a salted bcrypt hash of a password for storage.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `password` | `str` | Must fit in 72 UTF-8 bytes. Callers' schemas (`RegisterRequest`, password-change/reset schemas) already enforce 8–72 characters and ≤ 72 bytes; this function enforces only the byte limit (no minimum). |

**Returns:** the bcrypt hash as a `str`: 60 characters, starting with `$2b$12$`.

**Rules:**
- **R1.** The returned hash verifies: `verify_password(password, result)` is `True`, and `bcrypt.checkpw(password.encode(), result.encode())` is `True`.
- **R2.** When `password` is longer than 72 bytes once UTF-8 encoded (exactly 72 allowed), raises `ValueError("Password exceeds bcrypt's 72-byte limit")`; no hash is produced. (The docstring's "will be truncated" is stale — see Q2.) ✅
- **R3.** Each call uses a fresh random salt: hashing the same password twice gives two different strings, both of which verify.
- **R4.** The hash never contains the plain password.
- **R5.** An empty password `""` is accepted and hashed (no minimum length here).

**Errors:**
| Condition | Raises | Detail message |
|---|---|---|
| `password` > 72 UTF-8 bytes | `ValueError` | `Password exceeds bcrypt's 72-byte limit` |

**Side effects:** none.

---

## `create_refresh_token()`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `AuthService._issue_token_pair`)

**Purpose:** Generate a new opaque refresh token and the hash under which it is stored.

**Inputs:** none.

**Returns:** a tuple `(raw_token, token_hash)`.

**Rules:**
- **R1.** `raw_token` is a URL-safe base64 string (characters `A–Z a–z 0–9 - _` only, no padding) of 86 characters (64 random bytes, `REFRESH_TOKEN_BYTES == 64`).
- **R2.** `token_hash` equals `hash_refresh_token(raw_token)` (the 64-character lowercase sha256 hex digest of the raw token).
- **R3.** Successive calls return different raw tokens (and different hashes).

**Errors:** none.

**Side effects:** none.

---

## `hash_refresh_token(raw)`
**Shape:** compute
**Persistence:** pure
**Visibility:** public (used by: `create_refresh_token`, `AuthService` refresh/logout, `/auth/logout/` endpoint, `MobileUploadSessionManager`)

**Purpose:** Compute the deterministic lookup hash of an opaque token.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `raw` | `str` | Any string, including empty. |

**Returns:** the sha256 hex digest (64 lowercase hex characters) of `raw` encoded as UTF-8.

**Rules:**
- **R1.** Returns `hashlib.sha256(raw.encode("utf-8")).hexdigest()`; e.g. `hash_refresh_token("")` is `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"` and `hash_refresh_token("abc")` is `"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"`.
- **R2.** Deterministic: the same input always gives the same output; different inputs (including a one-character difference or different case) give different outputs.
- **R3.** Non-ASCII input is hashed as its UTF-8 bytes (does not raise).

**Errors:** none.

**Side effects:** none.

---

## `decode_token(token)`
**Shape:** validator
**Persistence:** pure
**Visibility:** public (used by: `get_current_user` dependency)

**Purpose:** Verify an access token's signature and expiry and return its claims.

**Inputs:**
| Name | Type | Meaning / constraints actually enforced |
|---|---|---|
| `token` | `str` | JWT from the `Authorization: Bearer` header. |

**Returns:** the payload `dict` when valid, otherwise `None`. Never raises for a bad token.

**Rules:**
- **R1.** A token produced by `create_access_token` and not yet expired returns its payload: every original claim plus `exp` (an integer timestamp).
- **R2.** A token whose `exp` is in the past (real clock, zero leeway) returns `None`.
- **R3.** Returns `None` when the token is invalid in any way the JWT library detects: signed with a different key; payload or signature tampered with; malformed (e.g. `"abc"`, `""`, two segments only); signed with an algorithm other than `settings.ALGORITHM` (e.g. HS512 with the right key, or `alg: none` unsigned); an `exp` that is not a number; an `iat` in the future or `nbf` in the future.
- **R4.** [BUG-502] A correctly signed token with **no** `exp` claim returns `None` (the `exp` claim is required). *(Today: its payload is returned and the token never expires.)*
- **R5.** No claim other than `exp`/`nbf`/`iat` is checked here: a correctly signed, unexpired token (with `exp`) without `sub`, or with extra claims, returns its payload unchanged (checking `sub` is the caller's job).

**Errors:** none (all JWT errors map to `None`).

**Side effects:** none.

---

## Branch map
| Source line | Decision | Rule |
|---|---|---|
| 31 | `data.copy()` — caller dict untouched | `create_access_token` R5 |
| 33 | `if expires_delta:` truthy (non-zero) | `create_access_token` R3 |
| 35–36 | `else` (`None` or zero `timedelta`) → default minutes | `create_access_token` R2, R3a [BUG-501] |
| 38 | `exp` overwrites any existing key | `create_access_token` R4 |
| 39 | `jwt.encode` succeeds / raises on non-serialisable claim | `create_access_token` R1, R6 |
| 55 | `if not hashed_password` → `False` | `verify_password` R1 |
| 59 | password > 72 bytes → `ValueError` (intended: `False`) | `verify_password` R2 [BUG-500] |
| 62 | `hashed_password` is `str` → encode, else used as bytes | `verify_password` R5 |
| 63–64 | `checkpw` match / no match | `verify_password` R3 |
| 65–66 | `checkpw` raises (malformed hash) → `False` | `verify_password` R4 |
| 85 | password > 72 bytes → `ValueError` | `get_password_hash` R2 |
| 88–89 | fresh salt, hash returned | `get_password_hash` R1, R3, R4, R5 |
| 103–105 | raw token + its hash | `create_refresh_token` R1, R2, R3 |
| 117 | sha256 hex of UTF-8 bytes | `hash_refresh_token` R1, R2, R3 |
| 131–132 | decode succeeds (today also without `exp`) | `decode_token` R1, R4 [BUG-502], R5 |
| 133–134 | `PyJWTError` (expired, bad signature, malformed, wrong alg, bad claims) → `None` | `decode_token` R2, R3 |
