# Execution notes — `app/services/waitlist_service.py`

> Cases: `tests/unit/services/waitlist_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_waitlist_service.py` · Source commit: e48a092
> Result: 35 of 35 cases implemented · 30 passed · 5 xfail as designed (4 strict, all xfailed; 1 non-strict, L-07, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_waitlist_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `machine_item_service.notes.md` / `department_service.notes.md`.
- **No standing rows:** Conventions name no workspace, profile or other row that exists in every test (the waitlist table is platform-wide, not scoped). Every email carries the per-test `tag` fixture (`uuid.uuid4().hex[:10]`).
- **Given rows:** `mk_signup(db, email, **but)` (the "signup" defaults; flushes); `req(email, **but)` builds the "req" `WaitlistSignupRequest`; `commit_point(db)` = `db.commit()` (a savepoint release). Every DB card runs the commit point after its last Given line; lines marked "(after the commit point)" run after it.
- **Reading helpers:** `row(db, e)`, `count(db, e)`, `reread(db, id)`, `snap_before` / `snap` (every column of `waitlist_signups`), `usable(db)`, `ids(rows)` (order kept).
- **Patches (only those Conventions name):** fixtures `salt_pepper`, `key_set`, `no_key` (`patch.object(settings, …)`); `SECRET_KEY` patched inline in H-03, H-04; the `stub` fixture patches `app.services.waitlist_service.httpx.AsyncClient` with a `Stub` class and returns the card's `posts` list; the failing commit wrap (S-07, U-04); S-06's race simulation (`waitlist_dao.get_by_email` answers `None` on its first call, the real lookup afterwards).
- `committed:` lines: `db.rollback()` once before the first one, as Conventions say.
- `verify_turnstile` cards run the coroutine with `asyncio.run`.
- Spec gaps: the only gap (where the 10 s timeout is passed) rests on no card. No assumed names needed resolving.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N`, value read:
- T-08 (BUG-1580): Then 1, `ValueError: Expecting value` escapes from `json()` — the card's text.
- T-09 (BUG-1580): Then 1, `AttributeError: 'list' object has no attribute 'get'`.
- S-09 (BUG-1579): Then 1, `DID NOT RAISE ValidationError`.
- L-06 (BUG-1410): Then 2, `[A, B]` against `[A]` (`_` matched `x`).
- L-07 (BUG-1411, non-strict): Then 2, `[B, C, A]` against `[C, B, A]` (the updated row A last), in every run.

## Reference run
`wl_refplug.py` (scratch, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc2x\waitlist\`) patched in only what each bug names:
- BUG-1580: `verify_turnstile` turns a `ValueError` from `json()` and a non-dict body into 502 `Could not verify submission`;
- BUG-1410: the DAO's search escapes `\`, `%`, `_` (`ILIKE … ESCAPE '\'`);
- BUG-1411: the DAO orders by `created_at DESC, id DESC`;
- BUG-1579: the test module's `WaitlistSignupRequest` replaced by a subclass that trims `first_name` / `last_name` and refuses blank.

With `--runxfail` all 35 tests passed; without it the 4 strict cards XPASSed (strict, so they failed) and L-07 XPASSed.

## Stability
5 plain runs plus `enable_seqscan=off` and `enable_indexscan=off; enable_bitmapscan=off` (scratch plugin `wl_plans.py`, a `connect` listener; checked to apply by an invalid setting): 30 passed, 5 xfailed in all 7; no test moved. Ruff passes; LF. The file runs in about 2.5 s.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (64 statements, 16 branches) of `app/services/waitlist_service.py`.

## Factories added
None.

## Notes for maintainers
- When BUG-1580, BUG-1579, BUG-1410 are fixed their cards XPASS (strict) → remove the markers. L-07 is non-strict; remove its marker with BUG-1411's fix.
- U-05 leaves the session in "needs rollback"; the test rolls back before its re-read, so `a.id` is read into `a_id` before the call.
- The coverage run prints 15 warnings (SQLAlchemy `LegacyAPIWarning` from `Query.get` in `app/dao/base.py`); harmless here.

## Revision 2 (2026-11-04)
Cases revision 2 (verifier Finding 1 / mutant #2; no spec change). Only one test changed:
- **WSV-S-01** (changed) — Then 2 asserts the literal `"You're on the list — we'll be in touch."` (em dash U+2014, bytes `E2 80 94` verified in the file) instead of the module's `SUCCESS_MESSAGE`. `SUCCESS_MESSAGE` is still imported: other cards' Then lines use it. Passes.

Counts: 35 tests · 30 passed · 5 xfailed · 0 errors · 0 discrepancies. Branch coverage `app.services.waitlist_service` 100%. 3 runs identical. Ruff clean; LF endings.

Joint run of the three files (private `COVERAGE_FILE`): 140 passed · 78 xfailed · 1 xpassed; coverage item 94% / machine 100% / waitlist 100% (TOTAL 98%).
