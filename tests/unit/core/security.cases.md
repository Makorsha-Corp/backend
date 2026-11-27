# Test cases — `app/core/security.py`

> **Spec:** `tests/unit/core/security.spec.md` (source commit `e48a092`)
> **Status:** READY
> **Revision:** 2 — re-run on the same APPROVED spec (commit `e48a092`); no rule changes since revision 1; `security.verify.md` has no case-designer (`case-missing`) findings (its 3 surviving mutants are BUG-500 bug-path, fix by —). No cases added, changed or retired.
> **Counts:** 68 cases · 61 expected-to-pass · 7 expected-to-fail (bugs) · 3 deferred

## Reviewer summary
- **Per callable:** `create_access_token` 16 cases (1 bug) · `verify_password` 18 (5 bug) · `get_password_hash` 8 · `create_refresh_token` 3 · `hash_refresh_token` 5 · `decode_token` 18 (1 bug)
- **Notable design choices:**
  - Pure module: no database rows, no session. Only `utcnow` is patched; bcrypt, PyJWT, hashlib, secrets run for real.
  - `decode_token` checks expiry against the real clock, so its cases build tokens relative to the real "now" (`NOW`), never the fixed 2026-01-01 time used for `create_access_token` (that date is already in the past).
  - Zero-leeway expiry is tested with a token that expired 5 s ago (not 1 s) to avoid clock-tick flakiness (best-practice default, delegated by reviewer).
  - The `alg: none` token is built by hand (base64url header + payload + empty signature) so the case does not depend on PyJWT's willingness to encode unsigned tokens (best-practice default, delegated by reviewer).
  - One read-only bcrypt hash `H1` may be computed once per test module and shared, to keep the suite fast (spec asks to keep real hashes few).
  - BUG-500 regression guard: over-long passwords against an empty/`None` hash return `False` today and after the fix — covered by passing case SEC-VP-07.
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `SEC` = `app/core/security.py`. Methods: `CAT` = `create_access_token`, `VP` = `verify_password`, `GPH` = `get_password_hash`, `CRT` = `create_refresh_token`, `HRT` = `hash_refresh_token`, `DT` = `decode_token`.
- **Settings in every test** (via `monkeypatch.setattr(settings, ...)` on `app.core.config.settings`): `SECRET_KEY = K1`, `ALGORITHM = "HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES = 15`, unless the case says otherwise.
  - `K1 = "unit-test-secret-key-0123456789abcdef"` (37 bytes)
  - `K2 = "another-unit-test-secret-key-0123456789"` (39 bytes)
- **Time:**
  - `T0 = datetime(2026, 1, 1, 12, 0, 0)` (naive). "utcnow = T0" means `app.core.security.utcnow` is patched to return T0.
  - `ts(h, m, s)` = `int(datetime(2026, 1, 1, h, m, s, tzinfo=timezone.utc).timestamp())`.
  - `NOW` = `int(time.time())` taken at test start (real clock). `REAL_UTCNOW` = `datetime.now(timezone.utc).replace(tzinfo=None)` at test start.
- **Reading a token without the module:** `peek(t)` = `jwt.decode(t, K1, algorithms=[settings.ALGORITHM], options={"verify_exp": False})`; `header(t)` = `jwt.get_unverified_header(t)`.
- **Hand-signed token:** `sign(claims, key=K1, alg="HS256")` = `jwt.encode(claims, key, algorithm=alg)`.
- **Hashes:** `H1 = get_password_hash("Secret-Pass-1")` (read-only, may be shared per module). `A72 = "a" * 72`, `A73 = "a" * 73`, `TK24 = "৳" * 24` (72 UTF-8 bytes), `TK25 = "৳" * 25` (75 UTF-8 bytes, 25 characters).
- **Externals mocked:** `app.core.security.utcnow` only (where a case says so). Nothing else.
- **Race simulations:** none.
- **Database:** not used by this module; no rows are inserted and there is no database state to re-read.
- "No raise" in Then means the call completes without any exception.

## `create_access_token`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SEC-CAT-01 | R1 | happy | utcnow = T0 | `create_access_token({"sub": "5", "email": "a@x.com", "workspace_id": 7})` | returns a `str` with exactly 3 non-empty dot-separated segments; `header(t)["alg"] == "HS256"`; `peek(t)` has `sub == "5"`, `email == "a@x.com"`, `workspace_id == 7`, and an `exp` key; keys are exactly `{sub, email, workspace_id, exp}`; `jwt.decode(t, K2, algorithms=["HS256"], options={"verify_exp": False})` raises `jwt.InvalidSignatureError` | pass |
| SEC-CAT-02 | R1 | happy | utcnow = T0; `ALGORITHM = "HS512"` | `create_access_token({"sub": "5"})` | `header(t)["alg"] == "HS512"`; `jwt.decode(t, K1, algorithms=["HS512"], options={"verify_exp": False})["sub"] == "5"` | pass |
| SEC-CAT-03 | R2 | happy | utcnow = T0 | `create_access_token({"sub": "5"})` (no `expires_delta`) | `peek(t)["exp"] == ts(12, 15, 0)`; `isinstance(exp, int)` | pass |
| SEC-CAT-04 | R2 | happy | utcnow = T0 | `create_access_token({"sub": "5"}, expires_delta=None)` | `peek(t)["exp"] == ts(12, 15, 0)` | pass |
| SEC-CAT-05 | R2 | side-effect | utcnow = T0; `ACCESS_TOKEN_EXPIRE_MINUTES = 30` | `create_access_token({"sub": "5"})` | `peek(t)["exp"] == ts(12, 30, 0)` (setting read at call time) | pass |
| SEC-CAT-06 | R2 | boundary | utcnow = `datetime(2026, 1, 1, 12, 0, 0, 750000)` | `create_access_token({"sub": "5"})` | `peek(t)["exp"] == ts(12, 15, 0)` (fraction dropped, whole seconds); `isinstance(exp, int)` | pass |
| SEC-CAT-07 | R3 | happy | utcnow = T0 | `create_access_token({"sub": "5"}, expires_delta=timedelta(hours=2))` | `peek(t)["exp"] == ts(14, 0, 0)`; `peek(t)["sub"] == "5"` | pass |
| SEC-CAT-08 | R3 | boundary | utcnow = T0 | `create_access_token({"sub": "5"}, expires_delta=timedelta(seconds=1))` | `peek(t)["exp"] == ts(12, 0, 1)` (smallest positive lifetime honoured, not the default) | pass |
| SEC-CAT-09 | R3 | boundary | utcnow = T0 | `create_access_token({"sub": "5"}, expires_delta=timedelta(seconds=-60))` | `peek(t)["exp"] == ts(11, 59, 0)` | pass |
| SEC-CAT-10 | R3 | happy | utcnow NOT patched (real) | `create_access_token({"sub": "5"}, expires_delta=timedelta(seconds=-60))` | `peek(t)["exp"] < NOW`; `decode_token(t) is None` (already expired) | pass |
| SEC-CAT-11 | R3a [BUG-501] | bug | utcnow = T0 | `create_access_token({"sub": "5"}, expires_delta=timedelta(0))` | `peek(t)["exp"] == ts(12, 0, 0)` | xfail BUG-501 — fails today on: `exp == ts(12, 15, 0)` (default applied) |
| SEC-CAT-12 | R4 | side-effect | utcnow = T0 | `create_access_token({"sub": "5", "exp": 1})` | `peek(t)["exp"] == ts(12, 15, 0)` (not 1); `peek(t)["sub"] == "5"` | pass |
| SEC-CAT-13 | R5 | side-effect | utcnow = T0; `data = {"sub": "5", "email": "a@x.com"}` | `create_access_token(data)` | after the call `data == {"sub": "5", "email": "a@x.com"}`; `"exp" not in data`; return value is a `str` | pass |
| SEC-CAT-14 | R5 | side-effect | utcnow = T0; `data = {"sub": "5", "exp": 1}` | `create_access_token(data)` | after the call `data == {"sub": "5", "exp": 1}` (caller's `exp` untouched); `peek(t)["exp"] == ts(12, 15, 0)` | pass |
| SEC-CAT-15 | R6 | error | utcnow = T0 | `create_access_token({"sub": "5", "when": datetime(2026, 1, 1)})` | raises `TypeError`; no token returned | pass |
| SEC-CAT-16 | R6 | error | utcnow = T0 | `create_access_token({"sub": "5", "roles": {"admin"}})` | raises `TypeError`; no token returned | pass |

## `verify_password`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SEC-VP-01 | R3 | happy | H1 | `verify_password("Secret-Pass-1", H1)` | returns `True` (is `True`, not just truthy) | pass |
| SEC-VP-02 | R3 | error | H1 | `verify_password("secret-pass-1", H1)` | returns `False` | pass |
| SEC-VP-03 | R3 | error | H1 | `verify_password("Secret-Pass-1 ", H1)` | returns `False` | pass |
| SEC-VP-04 | R3 | boundary | H1 | `verify_password("", H1)` | returns `False`; no raise | pass |
| SEC-VP-05 | R1 | boundary | — | `verify_password("Secret-Pass-1", "")` | returns `False`; no raise | pass |
| SEC-VP-06 | R1 | boundary | — | `verify_password("Secret-Pass-1", None)` | returns `False`; no raise | pass |
| SEC-VP-07 | R1 | boundary | — | `verify_password(A73, "")` and `verify_password(A73, None)` | both return `False`; no raise (holds today and after BUG-500 fix) | pass |
| SEC-VP-08 | R4 | error | — | `verify_password("Secret-Pass-1", "garbage")` | returns `False`; no raise | pass |
| SEC-VP-09 | R4 | error | `S = hashlib.sha256(b"Secret-Pass-1").hexdigest()` | `verify_password("Secret-Pass-1", S)` | returns `False`; no raise | pass |
| SEC-VP-10 | R5 | happy | H1 | `verify_password("Secret-Pass-1", H1.encode())` | returns `True` | pass |
| SEC-VP-11 | R5 | error | H1 | `verify_password("secret-pass-1", H1.encode())` | returns `False` | pass |
| SEC-VP-12 | R2, R3 | boundary | `HA72 = get_password_hash(A72)` | `verify_password(A72, HA72)`; `verify_password("a" * 71, HA72)` | first returns `True` (exactly 72 bytes allowed); second returns `False`; no raise | pass |
| SEC-VP-13 | R2, R3 | boundary | `HTK24 = get_password_hash(TK24)` | `verify_password(TK24, HTK24)` | returns `True` (72 bytes counted in UTF-8 bytes, allowed) | pass |
| SEC-VP-14 | R2 [BUG-500] | bug | H1 | `verify_password(A73, H1)` | returns `False`; no raise | xfail BUG-500 — fails today on: raises `ValueError("Password exceeds bcrypt's 72-byte limit")` |
| SEC-VP-15 | R2 [BUG-500] | bug | H1 | `verify_password(TK25, H1)` (25 characters, 75 bytes) | returns `False`; no raise | xfail BUG-500 — fails today on: raises `ValueError` |
| SEC-VP-16 | R2 [BUG-500] | bug | `HA72 = get_password_hash(A72)` | `verify_password(A73, HA72)` | returns `False` (no silent truncation to the first 72 bytes); no raise | xfail BUG-500 — fails today on: raises `ValueError` |
| SEC-VP-17 | R2 [BUG-500] | bug | — | `verify_password(A73, "garbage")` | returns `False`; no raise | xfail BUG-500 — fails today on: raises `ValueError` |
| SEC-VP-18 | R2 [BUG-500], R5 | bug | H1 | `verify_password(A73, H1.encode())` | returns `False`; no raise | xfail BUG-500 — fails today on: raises `ValueError` |

## `get_password_hash`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SEC-GPH-01 | R1 | happy | — | `h = get_password_hash("Secret-Pass-1")` | `h` is a `str`; `len(h) == 60`; `h.startswith("$2b$12$")`; `verify_password("Secret-Pass-1", h) is True`; `bcrypt.checkpw(b"Secret-Pass-1", h.encode()) is True` | pass |
| SEC-GPH-02 | R2 | boundary | — | `h = get_password_hash(A72)` | returns a 60-char `str` starting `$2b$12$`; `bcrypt.checkpw(A72.encode(), h.encode()) is True` | pass |
| SEC-GPH-03 | R2 | error | — | `get_password_hash(A73)` | raises `ValueError` with message exactly `"Password exceeds bcrypt's 72-byte limit"` | pass |
| SEC-GPH-04 | R2 | boundary | — | `h = get_password_hash(TK24)` | returns a 60-char `str`; `bcrypt.checkpw(TK24.encode("utf-8"), h.encode()) is True` | pass |
| SEC-GPH-05 | R2 | error | — | `get_password_hash(TK25)` (25 characters, 75 bytes) | raises `ValueError` with message exactly `"Password exceeds bcrypt's 72-byte limit"` (limit counts bytes, not characters) | pass |
| SEC-GPH-06 | R3 | side-effect | — | `h1 = get_password_hash("Secret-Pass-1")`; `h2 = get_password_hash("Secret-Pass-1")` | `h1 != h2`; `h1[:29] != h2[:29]` (different salt); `verify_password("Secret-Pass-1", h1) is True`; `verify_password("Secret-Pass-1", h2) is True` | pass |
| SEC-GPH-07 | R4 | side-effect | — | `h = get_password_hash("Plaintext99")` | `"Plaintext99" not in h`; `len(h) == 60` | pass |
| SEC-GPH-08 | R5 | boundary | — | `h = get_password_hash("")` | returns a 60-char `str` starting `$2b$12$`; `bcrypt.checkpw(b"", h.encode()) is True`; `verify_password("a", h) is False` | pass |

## `create_refresh_token`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SEC-CRT-01 | R1 | happy | — | `result = create_refresh_token()` | `result` is a tuple of length 2; `raw = result[0]` is a `str`; `len(raw) == 86`; `re.fullmatch(r"[A-Za-z0-9_-]{86}", raw)`; `"=" not in raw`; `len(base64.urlsafe_b64decode(raw + "==")) == 64` | pass |
| SEC-CRT-02 | R2 | happy | — | `raw, h = create_refresh_token()` | `h == hash_refresh_token(raw)`; `h == hashlib.sha256(raw.encode("utf-8")).hexdigest()`; `re.fullmatch(r"[0-9a-f]{64}", h)` | pass |
| SEC-CRT-03 | R3 | side-effect | — | call `create_refresh_token()` 20 times | the 20 raw tokens are all distinct; the 20 hashes are all distinct | pass |

## `hash_refresh_token`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SEC-HRT-01 | R1 | boundary | — | `hash_refresh_token("")` | returns `"e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"` | pass |
| SEC-HRT-02 | R1 | happy | — | `hash_refresh_token("abc")` | returns `"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"` | pass |
| SEC-HRT-03 | R1, R2 | happy | — | `hash_refresh_token("refresh-token-xyz")` twice | both results equal each other and equal `hashlib.sha256(b"refresh-token-xyz").hexdigest()` | pass |
| SEC-HRT-04 | R2 | boundary | — | `hash_refresh_token("abc")`, `hash_refresh_token("abd")`, `hash_refresh_token("ABC")` | the three results are pairwise different | pass |
| SEC-HRT-05 | R3 | happy | — | `hash_refresh_token("৳ঢাকা")` | no raise; returns `hashlib.sha256("৳ঢাকা".encode("utf-8")).hexdigest()`; matches `[0-9a-f]{64}` | pass |

## `decode_token`

All tokens here are relative to the real clock (`NOW`); utcnow is not patched unless stated.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| SEC-DT-01 | R1 | happy | `t = create_access_token({"sub": "5", "email": "a@x.com", "workspace_id": 7})` (real utcnow) | `decode_token(t)` | returns a `dict` with keys exactly `{sub, email, workspace_id, exp}`; `sub == "5"`, `email == "a@x.com"`, `workspace_id == 7`; `isinstance(exp, int)`; `exp > NOW` | pass |
| SEC-DT-02 | R2 | error | utcnow = `REAL_UTCNOW - timedelta(minutes=16)`; `t = create_access_token({"sub": "5"})` | `decode_token(t)` (utcnow patch irrelevant to decode) | returns `None`; no raise | pass |
| SEC-DT-03 | R2 | boundary | utcnow = `REAL_UTCNOW - timedelta(minutes=14)`; `t = create_access_token({"sub": "5"})` | `decode_token(t)` | returns a dict with `sub == "5"` | pass |
| SEC-DT-04 | R2 | boundary | `t = sign({"sub": "5", "exp": NOW - 5})` | `decode_token(t)` | returns `None` (zero leeway); no raise | pass |
| SEC-DT-05 | R2 | boundary | `t = sign({"sub": "5", "exp": NOW + 60})` | `decode_token(t)` | returns `{"sub": "5", "exp": NOW + 60}` | pass |
| SEC-DT-06 | R3 | error | `t = sign({"sub": "5", "exp": NOW + 3600}, key=K2)` | `decode_token(t)` | returns `None`; no raise | pass |
| SEC-DT-07 | R3 | error | `t = create_access_token({"sub": "5"})` while `SECRET_KEY = K1`; then set `SECRET_KEY = K2` | `decode_token(t)` | returns `None` (key read at call time) | pass |
| SEC-DT-08 | R3 | error | `t = sign({"sub": "5", "exp": NOW + 3600})`; `forged = t.split(".")[0] + "." + b64url_nopad(json.dumps({"sub": "1", "exp": NOW + 3600})) + "." + t.split(".")[2]` | `decode_token(t)`; `decode_token(forged)` | original returns a dict with `sub == "5"` (sanity); `forged` returns `None`; no raise | pass |
| SEC-DT-09 | R3 | error | `t = sign({"sub": "5", "exp": NOW + 3600})`; `t2 = sign({"sub": "5", "exp": NOW + 3600}, key=K2)`; `forged` = first two segments of `t` + `"."` + third segment of `t2` | `decode_token(forged)` | returns `None`; no raise | pass |
| SEC-DT-10 | R3 | error | `t = sign({"sub": "5", "exp": NOW + 3600})` | `decode_token("abc")`, `decode_token("")`, `decode_token("a.b")`, `decode_token(".".join(t.split(".")[:2]))` | each returns `None`; none raises | pass |
| SEC-DT-11 | R3 | error | `t = sign({"sub": "5", "exp": NOW + 3600}, key=K1, alg="HS512")`; `ALGORITHM = "HS256"` | `decode_token(t)` | returns `None`; no raise | pass |
| SEC-DT-12 | R3 | error | `t = b64url_nopad('{"alg":"none","typ":"JWT"}') + "." + b64url_nopad(json.dumps({"sub": "5", "exp": NOW + 3600})) + "."` | `decode_token(t)` | returns `None`; no raise | pass |
| SEC-DT-13 | R3 | error | `t = sign({"sub": "5", "exp": "tomorrow"})` | `decode_token(t)` | returns `None`; no raise | pass |
| SEC-DT-14 | R3 | error | `t = sign({"sub": "5", "exp": NOW + 3600, "iat": NOW + 600})` | `decode_token(t)` | returns `None`; no raise | pass |
| SEC-DT-15 | R3 | error | `t = sign({"sub": "5", "exp": NOW + 3600, "nbf": NOW + 600})` | `decode_token(t)` | returns `None`; no raise | pass |
| SEC-DT-16 | R3 | boundary | `claims = {"sub": "5", "exp": NOW + 3600, "iat": NOW - 60, "nbf": NOW - 60}`; `t = sign(claims)` | `decode_token(t)` | returns a dict equal to `claims` | pass |
| SEC-DT-17 | R4 [BUG-502] | bug | `t = sign({"sub": "1"})` (no `exp`, right key and alg) | `decode_token(t)` | returns `None`; no raise | xfail BUG-502 — fails today on: returns `{"sub": "1"}` |
| SEC-DT-18 | R5 | happy | `claims = {"exp": NOW + 3600, "role": "admin", "tags": ["a", "b"]}` (no `sub`); `t = sign(claims)` | `decode_token(t)` | returns a dict equal to `claims` (no `sub` required, extra claims unchanged) | pass |

`b64url_nopad(s)` = `base64.urlsafe_b64encode(s.encode()).rstrip(b"=").decode()`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `verify_password` R2 [BUG-500] / Q1 | `DAOProfile.authenticate`, `POST /auth/login/` | A password > 72 UTF-8 bytes for a registered email yields the same 401 "Invalid email or password" as for an unknown email (no enumeration via message). Timing side is BUG-038. |
| `get_password_hash` inputs | `RegisterRequest`, password-change / admin-reset schemas | Passwords > 72 UTF-8 bytes (and < 8 chars) are rejected by the schema before hashing. |
| `decode_token` R5 | `get_current_user` dependency | A valid token without `sub` (or with a non-existent user) is rejected by the caller, not by `decode_token`. |

## Spec gaps
None.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_access_token` | R1 | SEC-CAT-01, SEC-CAT-02 |
| `create_access_token` | R2 | SEC-CAT-03, SEC-CAT-04, SEC-CAT-05, SEC-CAT-06 |
| `create_access_token` | R3 | SEC-CAT-07, SEC-CAT-08, SEC-CAT-09, SEC-CAT-10 |
| `create_access_token` | R3a [BUG-501] | SEC-CAT-11 |
| `create_access_token` | R4 | SEC-CAT-12, SEC-CAT-14 |
| `create_access_token` | R5 | SEC-CAT-13, SEC-CAT-14 |
| `create_access_token` | R6 / Errors: non-JSON claim → `TypeError` | SEC-CAT-15, SEC-CAT-16 |
| `verify_password` | R1 | SEC-VP-05, SEC-VP-06, SEC-VP-07 |
| `verify_password` | R2 [BUG-500] | SEC-VP-14, SEC-VP-15, SEC-VP-16, SEC-VP-17, SEC-VP-18 |
| `verify_password` | R2 boundary (exactly 72 bytes) | SEC-VP-12, SEC-VP-13 |
| `verify_password` | R3 | SEC-VP-01, SEC-VP-02, SEC-VP-03, SEC-VP-04, SEC-VP-12, SEC-VP-13 |
| `verify_password` | R4 | SEC-VP-08, SEC-VP-09 |
| `verify_password` | R5 | SEC-VP-10, SEC-VP-11, SEC-VP-18 |
| `get_password_hash` | R1 | SEC-GPH-01 |
| `get_password_hash` | R2 / Errors: > 72 bytes → `ValueError` | SEC-GPH-02, SEC-GPH-03, SEC-GPH-04, SEC-GPH-05 |
| `get_password_hash` | R3 | SEC-GPH-06 |
| `get_password_hash` | R4 | SEC-GPH-07 |
| `get_password_hash` | R5 | SEC-GPH-08 |
| `create_refresh_token` | R1 | SEC-CRT-01 |
| `create_refresh_token` | R2 | SEC-CRT-02 |
| `create_refresh_token` | R3 | SEC-CRT-03 |
| `hash_refresh_token` | R1 | SEC-HRT-01, SEC-HRT-02, SEC-HRT-03 |
| `hash_refresh_token` | R2 | SEC-HRT-03, SEC-HRT-04 |
| `hash_refresh_token` | R3 | SEC-HRT-05 |
| `decode_token` | R1 | SEC-DT-01 |
| `decode_token` | R2 | SEC-DT-02, SEC-DT-03, SEC-DT-04, SEC-DT-05, SEC-CAT-10 |
| `decode_token` | R3 | SEC-DT-06 … SEC-DT-16 |
| `decode_token` | R4 [BUG-502] | SEC-DT-17 |
| `decode_token` | R5 | SEC-DT-18, SEC-DT-16 |
