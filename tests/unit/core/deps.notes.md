# Execution notes — `app/core/deps.py`

> Cases: `tests/unit/core/deps.cases.md` (revision 3) · Tests: `tests/unit/core/test_deps.py` · Source commit: e48a092
> Result: 79 passed · 6 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/core/test_deps.py -q -p no:cacheprovider --cov=app.core.deps --cov-branch --cov-report=term-missing`

66 case IDs → 85 collected tests (parametrized cases: CU-07 ×3, CU-21 ×3, CU-23 ×3, CU-24 ×2,
CW-04 ×4, CW-05 ×3, CW-06 ×3, CW-14 ×3, CW-15 ×3, CW-16 ×2; PA-04 and PA-05 share one
test as two `pytest.param` ids because setup and assertions are identical).

## How the tests are built
- **Conventions → helpers** (top of the test file, each commented with its convention):
  - W1/W2 → fixtures `w1`, `w2` (`make_workspace`). U1 → `u1` (`make_profile`, email
    `u1@example.com`, non-admin, plus an active `"member"` row in W1). U3 → `u3`, A → `A`
    (admin, no memberships). MISSING / NOUSER → fixtures `W1.id + 1_000_000` / `U1.id + 1_000_000`.
  - `tok(claims, key, alg)` → `jwt.encode` with `settings.SECRET_KEY` / `settings.ALGORITHM`
    by default; `FUT()` / `PAST()` / `_now()` use the real clock (`time.time()`). Time is never mocked.
  - `Creds(t)`, `req(h)`, `req_none()` → exactly as the Conventions define them (a bare
    `starlette.requests.Request` over a minimal ASGI scope).
  - E401 → `assert_e401` (status, detail, exact `headers` dict). DENIED → `assert_denied`
    (`HTTPException` with status 403 or 404), used only in the pass counterparts of BUG-440.
  - Membership rows → local `add_member(db, ws, user, role="member", status="active")`.
  - Re-reads → `reread_profile`, `reread_workspace`, `memberships(db, uid)`; each calls
    `db.expire_all()` then re-queries.
  - Spy session → `SpyFactory` / `SpySession` monkeypatched over `app.core.deps.SessionLocal`
    (fixture `spy`); counts factory calls and `close` / `commit` / `rollback` per session.
  - App client → fixture `client_ctx`: fresh `FastAPI()` with `GET /me` and `GET /ws`;
    `dependency_overrides[get_db]` is a generator that bumps a counter and yields the test
    session. CW-21 additionally overrides `get_current_user` to return U1.
- **Mocks:** none beyond the Conventions' spy `SessionLocal` (spec: no externals).
- **DB-07** uses the real `SessionLocal` (bound to the dev `DATABASE_URL`) but runs no
  query, so it never connects; it only asserts `isinstance(s, Session)` and `autoflush is False`.
- **CW-16 subscription dates** are computed from `app.utils.time.utcnow()` (the app's naive-UTC
  helper) so they match the column type.
- **xfail honesty:** verified with `--runxfail`: all 6 BUG-440 tests (CW-11, CW-13,
  CW-14 ×3, CW-19) fail on `assert 403 == 404` with
  `HTTPException(403, 'You do not have access to this workspace')` — the "fails today on" assertion.
- **Stability:** file run 3 times, identical outcome each time (79 passed, 6 xfailed).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (55 statements, 16 branches).

## Factories added
None (batch mode: `tests/unit/factories.py` is frozen). Worth promoting later:
- `add_member(db, ws, user, role="member", status="active")` → `make_workspace_member` in
  `tests/unit/factories.py` (every workspace-scoped module needs membership rows).
- `tok()` / `Creds()` JWT helpers could become a shared auth helper if other modules
  (e.g. endpoint or security tests) need signed tokens.

## Notes for maintainers
- When BUG-440 is fixed (non-member / non-active member → 404 "Workspace with ID N not found"),
  CW-11, CW-13, CW-14 (×3) and CW-19 will XPASS and fail strictly: remove their
  `xfail` markers. The DENIED counterparts (CW-12, CW-15, CW-20, CW-23) accept 403 or 404
  and keep passing either way.
- CU-08/CU-09 emit PyJWT `InsecureKeyLengthWarning` (short test key / HS512 with the
  HS256-sized secret); harmless and expected.
- `fastapi.testclient` emits a Starlette deprecation warning about `httpx`; unrelated to these tests.
- CU-12 relies on the real clock: `exp = now + 60 s` leaves a 60-second margin, ample for a
  single direct call.

## Revision history
- **Revision 3 (cases rev 3, source e48a092):** no case added, changed or retired; the cases
  file only made the "Unchanged database on errors" convention explicit (one representative
  re-read per error row: CU-07, CW-02, CW-12/15/23, PA-02/PA-03). Checked that the existing
  tests already re-read in exactly those cases (`reread_profile` / `reread_workspace` /
  `memberships`, each after `db.expire_all()`), so the test file is unchanged. Re-ran 3 times:
  79 passed · 6 xfailed each run; branch coverage still 100% (55 stmts, 16 branches).
  `deps.verify.md` (PASS) had no Findings routed to the executor.
