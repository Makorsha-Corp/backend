# Test cases — `app/core/deps.py`

> **Spec:** `tests/unit/core/deps.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 3 — re-run against the unchanged APPROVED spec (commit e48a092, Gap log G1–G3 already applied). `deps.verify.md` (PASS) has no Findings and no `case-missing` survivors (#16 equivalent, #41 bug-path, both "Fix by —"), so nothing to address. No case added, changed or retired; only the "unchanged database" convention for read-only error cases was made explicit (see Conventions).
> Revision 2 — spec Gap log G1–G3 closed my three gaps (status is free-text VARCHAR(50), membership lookup uses `current_user.id`, only `autoflush` observable); CW-14/15 now insert the listed statuses unconditionally with role `"member"`, CW-18/19/20 cite the spec's `id` fact, DB-07 cites the spec's Returns. No case IDs added or retired.
> **Counts:** 66 cases · 62 expected-to-pass · 4 expected-to-fail (bugs) · 0 deferred

## Reviewer summary
- **Per callable:** `get_db` 7 cases · `get_current_user` 28 · `get_current_active_user` 3 · `get_current_workspace` 23 (4 bug, all BUG-440) · `get_platform_admin` 5
- **Notable design choices:**
  - `HTTPBearer` behavior (`get_current_user` R1, R2) and the header-name case-insensitivity of `X-Workspace-ID` are tested through a minimal `FastAPI()` app + `TestClient` with `get_db` overridden; everything else calls the functions directly.
  - "Before any database access" (CU R1) is checked by making the `get_db` override count its invocations; it must stay 0.
  - BUG-440 is split: the xfail cases assert the intended 404 + "not found" detail; paired pass cases assert only that access is denied (`HTTPException` with status 403 or 404, workspace not returned), so the security property stays protected today.
  - All "not found" ids are computed (`W1.id + 1_000_000`) so concurrent agents' rows cannot collide with them.
  - `get_db` is tested with a spy session factory patched over `app.core.deps.SessionLocal`; one case uses the real `SessionLocal` without querying, to check `autoflush` is off.
  - "Database unchanged" after errors is re-read in one representative case per error row, not in every case, since nothing here writes (best-practice default, delegated by reviewer).
- **Needs a decision:** None.

## Conventions for this module
- **IDs:** `DEPS` = deps module; `DB` = `get_db`, `CU` = `get_current_user`, `AU` = `get_current_active_user`, `CW` = `get_current_workspace`, `PA` = `get_platform_admin`.
- **Rows:** every `workspace_members` row gets `role` explicitly (`"member"` unless stated); `status` as stated.
  - W1, W2 = two workspaces (default subscription fields unless stated).
  - U1 = a profile, email `"u1@example.com"`, `is_platform_admin` false, with a `workspace_members` row in W1, role `"member"`, status `"active"`. U1 has no membership in W2.
  - U3 = a profile, `is_platform_admin` false, with no memberships at all.
  - A = a profile, `is_platform_admin` true, with no memberships at all.
  - MISSING = `W1.id + 1_000_000` (no workspace has this id); NOUSER = `U1.id + 1_000_000` (no profile has this id).
- **Tokens:** `tok(claims, key=settings.SECRET_KEY, alg=settings.ALGORITHM)` = `jwt.encode(claims, key, algorithm=alg)`. `FUT` = real now + 15 min (epoch seconds), `PAST` = real now − 60 s. Unless stated, claims are `{"sub": str(U1.id), "email": "u1@example.com", "exp": FUT}`. Time is never mocked in this module (PyJWT uses the real clock).
- **Creds(t)** = `HTTPAuthorizationCredentials(scheme="Bearer", credentials=t)`.
- **E401** = `HTTPException` with `status_code == 401`, `detail == "Could not validate credentials"`, `headers == {"WWW-Authenticate": "Bearer"}` (exact dict).
- **req(h)** = `starlette.requests.Request({"type": "http", "headers": [(b"x-workspace-id", h.encode())]})`; **req_none** = same scope with `"headers": []`.
- **DENIED** = raises `HTTPException` whose `status_code` is 403 or 404 (the function does not return a workspace). Used only in the pass counterparts of BUG-440 cases.
- **App client (TestClient cases only):** a fresh `FastAPI()` app with route `GET /me` → `Depends(get_current_user)`, returning `{"id": user.id}`, and route `GET /ws` → `Depends(get_current_workspace)`, returning `{"id": workspace.id}`. `app.dependency_overrides[get_db]` = a generator function that increments a counter and yields the test session. The real application is never started.
- **Spy session (get_db cases):** `app.core.deps.SessionLocal` monkeypatched to a factory that creates a new spy object per call and records the call count; each spy counts `close()`, `commit()` and `rollback()` calls.
- **Unchanged:** "re-read unchanged" means the named rows are re-queried after the call and every column listed in the case equals its pre-call value.
- **Unchanged database on errors:** every callable here is read-only or pure (spec Persistence: `reads`/`pure`, Side effects: none), so "nothing changed" is asserted with an explicit re-read in one representative error case per error row (CU-07 for the 401 row, CW-02 for the 400 rows, CW-12/15/23 for the access-denied row, PA-02/PA-03 for the 403 row) rather than in every parametrized error case (best-practice default, delegated by reviewer).
- **Race simulations:** none.
- **Externals mocked:** none.

## `get_db`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPS-DB-01 | R1 | happy | spy factory patched | `g = get_db(); s = next(g)`; then `g.close()` | `s` is the spy returned by the factory's only call; factory call count == 1 | pass |
| DEPS-DB-02 | R1 | boundary | spy factory patched | `g1 = get_db(); g2 = get_db(); s1 = next(g1); s2 = next(g2)`; then `g1.close()` | `s1 is not s2`; factory call count == 2; `s1.close` count == 1, `s2.close` count == 0 (closing one does not close the other); finally `g2.close()` → `s2.close` count == 1 | pass |
| DEPS-DB-03 | R2, R4 | side-effect | spy factory patched | `g = get_db(); s = next(g); g.close()` | `s.close` count == 1; `s.commit` count == 0; `s.rollback` count == 0 | pass |
| DEPS-DB-04 | R2, R4 | side-effect | spy factory patched | `g = get_db(); s = next(g)`; then `next(g)` again | second `next` raises `StopIteration`; `s.close` count == 1; `s.commit` == 0; `s.rollback` == 0 | pass |
| DEPS-DB-05 | R3, R4 | error | spy factory patched; `exc = ValueError("boom")` | `g = get_db(); s = next(g); g.throw(exc)` | raises `ValueError`, the raised object `is exc` (unchanged, message "boom"); `s.close` count == 1; `s.commit` == 0; `s.rollback` == 0 | pass |
| DEPS-DB-06 | R3 | error | spy factory patched; `exc = HTTPException(status_code=404, detail="x")` | `g = get_db(); s = next(g); g.throw(exc)` | raises the same object (`is exc`), `status_code == 404`, `detail == "x"`; `s.close` count == 1 | pass |
| DEPS-DB-07 | Returns | happy | real `SessionLocal` (not patched) | `g = get_db(); s = next(g)`; inspect without running any query; then `g.close()` | `s` is a SQLAlchemy `Session`; `s.autoflush is False` (`autocommit` is not asserted — not an attribute in SQLAlchemy 2.x, per spec Returns) | pass |

## `get_current_user`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPS-CU-01 | R1 | error | U1; app client | `GET /me` with no `Authorization` header | response 401; JSON `detail == "Not authenticated"`; response header `WWW-Authenticate == "Bearer"`; `get_db` override counter == 0 | pass |
| DEPS-CU-02 | R1 | error | U1; app client | `GET /me` with `Authorization: Basic abc` | 401; detail `"Not authenticated"`; `WWW-Authenticate: Bearer`; `get_db` counter == 0 | pass |
| DEPS-CU-03 | R1 | boundary | U1; app client | `GET /me` with `Authorization: Bearer ` (empty token) | 401; detail `"Not authenticated"`; `WWW-Authenticate: Bearer`; `get_db` counter == 0 | pass |
| DEPS-CU-04 | R1 | boundary | U1; app client | `GET /me` with `Authorization: Bearer <tok()>` | 200; body `{"id": U1.id}` | pass |
| DEPS-CU-05 | R2 | happy | U1; app client | `GET /me` with `Authorization: bearer <tok()>` (lowercase scheme) | 200; body `{"id": U1.id}` | pass |
| DEPS-CU-06 | R2, R4 | boundary | U1; app client | `GET /me` with `Authorization: bearer abc` | 401; detail `"Could not validate credentials"` (the token reached decoding, not `"Not authenticated"`); `WWW-Authenticate: Bearer` | pass |
| DEPS-CU-07 | R3, R4 | error | U1 | `get_current_user(Creds(t), db)` parametrized over t = `"not-a-jwt"`, `tok()[:-10]` (truncated), `"!!!.@@@.###"` | raises E401 (exact status, detail, headers); U1 re-read unchanged (email) | pass |
| DEPS-CU-08 | R3, R5 | error | U1 | `Creds(tok(key="wrong-secret"))` | raises E401 | pass |
| DEPS-CU-09 | R6 | error | U1 | `Creds(tok(alg="HS512"))` (right secret) | raises E401 | pass |
| DEPS-CU-10 | R6 | error | U1 | `Creds(jwt.encode(claims, None, algorithm="none"))` (unsigned, default claims) | raises E401 | pass |
| DEPS-CU-11 | R7 | boundary | U1 | claims with `exp = PAST` | raises E401 | pass |
| DEPS-CU-12 | R7 | boundary | U1 | claims with `exp = real now + 60 s` | returns the profile: `.id == U1.id`, `.email == "u1@example.com"` | pass |
| DEPS-CU-13 | R7 | boundary | U1 | default claims plus `nbf = real now + 3600` | raises E401 | pass |
| DEPS-CU-14 | R7 | boundary | U1 | default claims plus `nbf = PAST` | returns profile with `.id == U1.id` | pass |
| DEPS-CU-15 | R7 | error | U1 | claims with `exp = "tomorrow"` (string) | raises E401 | pass |
| DEPS-CU-16 | R7 | error | U1 | default claims plus `iat = "yesterday"` | raises E401 | pass |
| DEPS-CU-17 | R7 | error | U1 | default claims plus `nbf = "soon"` | raises E401 | pass |
| DEPS-CU-18 | R8 | boundary | U1 | claims `{"sub": str(U1.id), "email": "u1@example.com"}` (no `exp`) | returns profile with `.id == U1.id` | pass |
| DEPS-CU-19 | R9 | error | U1 | claims `{"email": "u1@example.com", "exp": FUT}` (no `sub`) | raises E401 | pass |
| DEPS-CU-20 | R10 | error | U1 | claims with `sub = U1.id` (JSON number, not string) | raises E401 | pass |
| DEPS-CU-21 | R11 | error | U1 | claims with `sub` parametrized over `"abc"`, `""`, `"5.0"` | raises E401 | pass |
| DEPS-CU-22 | R12, R14 | happy | U1 | `Creds(tok())` (sub `str(U1.id)`) | returns profile: `.id == U1.id`, `.email == "u1@example.com"`, `.is_platform_admin` false; U1 re-read unchanged (email, is_platform_admin) | pass |
| DEPS-CU-23 | R12 | boundary | U1 | claims with `sub` parametrized over `f" {U1.id} "`, `f"+{U1.id}"`, `f"0_{U1.id}"` | returns profile with `.id == U1.id` | pass |
| DEPS-CU-24 | R12, R13 | boundary | U1 | claims with `sub` parametrized over `"-1"`, `"0"` | raises E401 | pass |
| DEPS-CU-25 | R13 | error | U1 | claims with `sub = str(NOUSER)` | raises E401 | pass |
| DEPS-CU-26 | R13 | error | profile U2 created and flushed, token for U2 made, then U2's row deleted and flushed | `Creds(tok({"sub": str(U2.id), "exp": FUT}))` | raises E401 | pass |
| DEPS-CU-27 | R14 | happy | U1 | claims `{"sub": str(U1.id), "email": "other@example.com", "workspace_id": MISSING, "exp": FUT}` | returns profile with `.id == U1.id` and `.email == "u1@example.com"`; U1 re-read: email still `"u1@example.com"` | pass |
| DEPS-CU-28 | R15 | happy | A | token with `sub = str(A.id)` | returns profile with `.id == A.id`, `.is_platform_admin` true | pass |

## `get_current_active_user`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPS-AU-01 | R1 | happy | U1 | `get_current_active_user(U1)` | returns an object that `is U1`; U1 re-read unchanged (email, is_platform_admin false) | pass |
| DEPS-AU-02 | R1 | happy | A | `get_current_active_user(A)` | returns object that `is A`; `.is_platform_admin` true | pass |
| DEPS-AU-03 | R1 | boundary | a transient `Profile` P (email `"p@example.com"`) never added to the session | `get_current_active_user(P)` | returns object that `is P`; no profile with email `"p@example.com"` exists in the database | pass |

## `get_current_workspace`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPS-CW-01 | R7 | happy | W1, U1 (active member of W1) | `get_current_workspace(req(str(W1.id)), db, U1)` | returns workspace with `.id == W1.id`; W1 re-read unchanged (name, subscription_status); U1's W1 membership re-read: status still `"active"`, no new membership rows for U1 | pass |
| DEPS-CW-02 | R1 | error | W1, U1 | `get_current_workspace(req_none, db, U1)` | raises `HTTPException` 400, detail `"X-Workspace-ID header is required"`; W1 and memberships re-read unchanged | pass |
| DEPS-CW-03 | R2 | boundary | W1, U1 | `req("")` | raises `HTTPException` 400, detail `"X-Workspace-ID header is required"` | pass |
| DEPS-CW-04 | R3 | error | W1, U1 | header parametrized over `"abc"`, `"5.0"`, `"0x5"`, `"   "` | raises `HTTPException` 400, detail `"X-Workspace-ID must be a valid integer"` | pass |
| DEPS-CW-05 | R4 | boundary | W1, U1 | header parametrized over `f" {W1.id} "`, `f"+{W1.id}"`, `f"0_{W1.id}"` | returns workspace with `.id == W1.id` | pass |
| DEPS-CW-06 | R4, R5 | boundary | W1, U1 | header parametrized over `"-1"`, `"0"`, `"99999999999999999999"` | raises `HTTPException` 404 with detail `"Workspace with ID -1 not found"`, `"Workspace with ID 0 not found"`, `"Workspace with ID 99999999999999999999 not found"` respectively; no other exception type | pass |
| DEPS-CW-07 | R5 | error | W1, U1 (active member of W1) | header `f" 0{MISSING} "` | raises `HTTPException` 404, detail `f"Workspace with ID {MISSING} not found"` (parsed integer, no leading zero or spaces) | pass |
| DEPS-CW-08 | R5 | error | A (platform admin) | `get_current_workspace(req(str(MISSING)), db, A)` | raises `HTTPException` 404, detail `f"Workspace with ID {MISSING} not found"` (admin does not bypass existence) | pass |
| DEPS-CW-09 | R6 | happy | W2, A (no memberships) | `req(str(W2.id))`, user A | returns workspace with `.id == W2.id`; no membership row for A created (re-read) | pass |
| DEPS-CW-10 | R1–R5 precedence | error | A | `req("abc")`, user A | raises `HTTPException` 400, detail `"X-Workspace-ID must be a valid integer"` (header checks run before existence/admin) | pass |
| DEPS-CW-11 | R8 [BUG-440] | bug | W1, W2, U1 (member of W1 only) | `req(str(W2.id))`, user U1; also, in the same test, `req(str(MISSING))`, user U1 | first call raises `HTTPException` with `status_code == 404` and detail `f"Workspace with ID {W2.id} not found"`; its status equals the status of the MISSING call (404) and its detail has the same format | xfail BUG-440 — fails today on: status is 403 (detail "You do not have access to this workspace") |
| DEPS-CW-12 | R8 | error | W1, W2, U1 (member of W1 only) | `req(str(W2.id))`, user U1 | DENIED; no membership row for U1 in W2 exists afterwards (re-read) | pass |
| DEPS-CW-13 | R8 [BUG-440] | bug | W1, U3 (no memberships) | `req(str(W1.id))`, user U3 | raises `HTTPException` 404, detail `f"Workspace with ID {W1.id} not found"` | xfail BUG-440 — fails today on: status is 403 |
| DEPS-CW-14 | R9 [BUG-440] | bug | W1; profile U2 (non-admin) with a W1 membership, role `"member"`, whose status is parametrized over `"suspended"`, `"invited"`, `"Active"` (free-text column, stored as-is per spec R9) | `req(str(W1.id))`, user U2 | raises `HTTPException` 404, detail `f"Workspace with ID {W1.id} not found"` | xfail BUG-440 — fails today on: status is 403 |
| DEPS-CW-15 | R9 | error | same as CW-14 (same parametrization) | `req(str(W1.id))`, user U2 | DENIED; U2's membership re-read: status unchanged | pass |
| DEPS-CW-16 | R10, R7 | side-effect | workspace W3 with subscription fields parametrized over (a) `subscription_status="cancelled"`, `trial_ends_at` = now − 60 days, `subscription_ends_at` = now − 1 day; (b) `subscription_status="trial"`, `trial_ends_at` = now − 60 days; U1 with an active membership in W3 | `req(str(W3.id))`, user U1 | returns workspace with `.id == W3.id`; W3 re-read: subscription fields unchanged | pass |
| DEPS-CW-17 | R10, R6 | side-effect | W3 as in CW-16 variant (a); A | `req(str(W3.id))`, user A | returns workspace with `.id == W3.id` | pass |
| DEPS-CW-18 | R11, R7 | boundary | W1, U1 (active in W1); `obj = SimpleNamespace(id=U1.id)` (no `is_platform_admin` attribute; `id` = profile primary key, the attribute the lookup uses per spec R11) | `req(str(W1.id))`, user `obj` | returns workspace with `.id == W1.id` | pass |
| DEPS-CW-19 | R11, R8 [BUG-440] | bug | W2, U1 (not in W2); `obj = SimpleNamespace(id=U1.id)` | `req(str(W2.id))`, user `obj` | raises `HTTPException` 404, detail `f"Workspace with ID {W2.id} not found"` | xfail BUG-440 — fails today on: status is 403 |
| DEPS-CW-20 | R11 | error | as CW-19 | `req(str(W2.id))`, user `obj` | DENIED (not treated as an admin: no workspace returned) | pass |
| DEPS-CW-21 | Inputs (header name case-insensitive) | happy | W1, U1; app client with `get_current_user` overridden to return U1 | `GET /ws` with header `X-WORKSPACE-ID: <W1.id>`; and again with `x-workspace-id: <W1.id>` | both 200 with body `{"id": W1.id}` | pass |
| DEPS-CW-22 | R6 | boundary | W1, A; A also has no membership in W1 | `req(str(W1.id))`, user A | returns `.id == W1.id` (admin path; the non-admin side is CW-12/CW-13) | pass |
| DEPS-CW-23 | R8 | error | W1, U3 (no memberships) | `req(str(W1.id))`, user U3 | DENIED; no membership row for U3 exists afterwards | pass |

## `get_platform_admin`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| DEPS-PA-01 | R1, R4 | happy | A (no memberships) | `get_platform_admin(A)` | returns object that `is A`; A re-read: `is_platform_admin` still true | pass |
| DEPS-PA-02 | R2 | error | U1 | `get_platform_admin(U1)` | raises `HTTPException` 403, detail `"Platform admin access required"`; U1 re-read unchanged (`is_platform_admin` false) | pass |
| DEPS-PA-03 | R4 | error | W1; profile O (non-admin) with W1 membership role `"owner"`, status `"active"` | `get_platform_admin(O)` | raises `HTTPException` 403, detail `"Platform admin access required"`; O's membership re-read unchanged | pass |
| DEPS-PA-04 | R3 | boundary | `obj = SimpleNamespace(id=1)` (no `is_platform_admin`) | `get_platform_admin(obj)` | raises `HTTPException` 403, detail `"Platform admin access required"` | pass |
| DEPS-PA-05 | R3 | boundary | `obj = SimpleNamespace(id=1, is_platform_admin=None)` | `get_platform_admin(obj)` | raises `HTTPException` 403, detail `"Platform admin access required"` | pass |

## Deferred to other specs
None.

## Spec gaps
None. (Revision 1 gaps 1–3 closed by spec Gap log G1–G3.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_db` | R1 | DB-01, DB-02 |
| `get_db` | R2 | DB-03, DB-04 |
| `get_db` | R3 | DB-05, DB-06 |
| `get_db` | R4 | DB-03, DB-04, DB-05 |
| `get_db` | Returns (autoflush off) | DB-07 |
| `get_current_user` | R1 | CU-01, CU-02, CU-03, CU-04 |
| `get_current_user` | R2 | CU-05, CU-06 |
| `get_current_user` | R3 | CU-07 … CU-11, CU-13, CU-15 … CU-17, CU-19 … CU-21, CU-24 … CU-26 (all assert E401 exactly) |
| `get_current_user` | R4 | CU-06, CU-07 |
| `get_current_user` | R5 | CU-08 |
| `get_current_user` | R6 | CU-09, CU-10 |
| `get_current_user` | R7 | CU-11, CU-12, CU-13, CU-14, CU-15, CU-16, CU-17 |
| `get_current_user` | R8 | CU-18 |
| `get_current_user` | R9 | CU-19 |
| `get_current_user` | R10 | CU-20 |
| `get_current_user` | R11 | CU-21 |
| `get_current_user` | R12 | CU-22, CU-23, CU-24 |
| `get_current_user` | R13 | CU-24, CU-25, CU-26 |
| `get_current_user` | R14 | CU-22, CU-27 |
| `get_current_user` | R15 | CU-28 |
| `get_current_user` | Error: missing/non-Bearer/empty → 401 Not authenticated | CU-01, CU-02, CU-03 |
| `get_current_user` | Error: undecodable/key/alg/exp/sub/unknown → 401 Could not validate | CU-07 … CU-11, CU-13, CU-15 … CU-17, CU-19 … CU-21, CU-24 … CU-26 |
| `get_current_active_user` | R1 | AU-01, AU-02, AU-03 |
| `get_current_workspace` | R1 | CW-02 |
| `get_current_workspace` | R2 | CW-03 |
| `get_current_workspace` | R3 | CW-04, CW-10 |
| `get_current_workspace` | R4 | CW-05, CW-06 |
| `get_current_workspace` | R5 | CW-06, CW-07, CW-08, CW-11 |
| `get_current_workspace` | R6 | CW-09, CW-17, CW-22 |
| `get_current_workspace` | R7 | CW-01, CW-16, CW-18 |
| `get_current_workspace` | R8 [BUG-440] | CW-11 (xfail), CW-13 (xfail), CW-19 (xfail), CW-12, CW-23, CW-20 |
| `get_current_workspace` | R9 [BUG-440] | CW-14 (xfail), CW-15 |
| `get_current_workspace` | R10 | CW-16, CW-17 |
| `get_current_workspace` | R11 | CW-18, CW-19 (xfail), CW-20 |
| `get_current_workspace` | Inputs: header name case-insensitive | CW-21 |
| `get_current_workspace` | Error: header missing/empty → 400 | CW-02, CW-03 |
| `get_current_workspace` | Error: header not integer → 400 | CW-04, CW-10 |
| `get_current_workspace` | Error: no workspace → 404 | CW-06, CW-07, CW-08 |
| `get_current_workspace` | Error: no active membership → 404 [BUG-440] | CW-11, CW-13, CW-14, CW-19 (xfail); CW-12, CW-15, CW-20, CW-23 (pass, DENIED) |
| `get_current_workspace` | Error precedence (400 → 404) | CW-10, CW-07 |
| `get_platform_admin` | R1 | PA-01 |
| `get_platform_admin` | R2 | PA-02 |
| `get_platform_admin` | R3 | PA-04, PA-05 |
| `get_platform_admin` | R4 | PA-01, PA-03 |
| `get_platform_admin` | Error: not platform admin → 403 | PA-02, PA-03, PA-04, PA-05 |
| — | BUG-440 | CW-11, CW-13, CW-14, CW-19 |
