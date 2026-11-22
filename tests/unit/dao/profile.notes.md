# Execution notes — `app/dao/profile.py`

> Cases: `tests/unit/dao/profile.cases.md` (revision 2, READY) · Tests: `tests/unit/dao/test_profile.py` · Source commit: e48a092
> Result: 33 passed · 13 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_profile.py -q -p no:cacheprovider --cov=app.dao.profile --cov-branch --cov-report=term-missing`

## How the tests are built
- Normal mode (no local model); every test sits below a `# [claude] <ID>` comment, in card order, one test per case (42).
- Conventions → code: fixture `e` makes TAG once per test and holds MIXED, LOWER, UPPER, EA, EZ; constants `PW`, `TZ`; `dao = profile_dao`.
  `profile(db, email, hashed_password=None, **columns)` wraps `make_profile` (Given "profile(e)", "profile(e, h)", "but …" columns), each flushed on its own, so ids rise in Given order.
  `reread` (expire_all + `db.get`), `new_row` (expire_all + select by id), `count`, `count_ci`, and `StatementRecorder` (a `before_cursor_execute` listener on `db.connection()`; `written()` = INSERT/UPDATE/DELETE).
- "rolled back" (PRF-CR-03): `sp = db.begin_nested()`, `patch.object(db, "commit", wraps=db.commit)` around the call, inside checks, `sp.rollback()`, after check.
- `IntegrityError on flush` cards: `pytest.raises(IntegrityError)` around `with db.begin_nested():` (file-level `noqa: SIM117`).
- Nothing mocked except PRF-AU-04: `patch("app.core.security.verify_password", wraps=verify_password)` (the DAO imports it inside `authenticate`). bcrypt runs for real (~0.25 s per hash), so the file takes about 9 s.
- PRF-AU-09: the card's Then 1 is the call itself (today it raises `ValueError`), so the call and its assertion sit under one `# Then 1` comment.

## Verification done at execution
- `--runxfail`: all 13 strict xfails fail on their named Then line: GE-03/04/05/06/13 and AU-02 on Then 1 (`None is not None`); CR-04 on Then 2 (`'  Ann ' == 'Ann'`); CR-05/06 on Then 1 (DID NOT RAISE ValidationError); CR-15 on Then 2 (`'Ann.Lee.<tag>@example.com' == 'ann.lee.<tag>@example.com'`); CR-17 on Then 1 (DID NOT RAISE IntegrityError); AU-04 on Then 2 (`0 == 1`); AU-09 on Then 1 (`ValueError: Password exceeds bcrypt's 72-byte limit`).
- Reference fix plugin (scratch, not in the repo: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\oqe\profile\ref_fix_profile.py`, loaded with `-p ref_fix_profile --runxfail`) patches in-process: BUG-1860 `lower(trim())` on both sides; BUG-1861 lower-cased email in `create`; BUG-1862 drops `profiles_email_key` and adds a unique index on `lower(email)` inside the test's own transaction; BUG-1406 a `ProfileCreate` subclass that strips the name and refuses blank; BUG-038 a dummy-hash check for unknown emails; BUG-500 `verify_password` returns False over 72 bytes. Result: 42 passed, and coverage of the test file itself is 349/349 lines, so every line past each failure point ran.
- 3 plain runs: 29 passed, 13 xfailed each time. `ruff check` and `ruff format --check` clean; LF.

## Discrepancies
None.

## Revision history
- **Revision 2 (2026-11-04).** Cases revision 2 is additive (from `profile.verify.md` findings 1 and 2). Added PRF-GE-14 and GE-15 (`%` is literal, so a LIKE/ILIKE fix fails) and PRF-GE-16 and GE-17 (an inner space on either side is not ignored, so a strip-every-space fix fails). All four pass today. No existing test changed, and none were retired. Re-run results:
  - 3 plain runs: 33 passed, 13 xfailed each time.
  - Branch coverage: 100%.
  - `--runxfail`: the same 13 failure lines as before.
  - Reference plugin (unchanged; its `lower(trim())` fix keeps GE-14…17 green): 46 passed, and test-file coverage is 373/373 lines.
  - Ruff clean, LF.

## Coverage gaps
None — 100% branch coverage (22 statements, 4 branches).

## Factories added
None.

## Notes for maintainers
- When BUG-1860 is fixed: GE-03…06, GE-13, AU-02 XPASS → remove their markers. BUG-1861: CR-15. BUG-1862: CR-17 (needs the migration; the BUG-1862 listing script must run first). BUG-1406: CR-04…06 (fix is in the schemas). BUG-038: AU-04. BUG-500: AU-09.
- CR-13 deliberately checks only pgcode `23505`, not the constraint name, so it stays green after BUG-1862 renames the email index.
- Emails carry a per-test TAG so concurrent runs on the shared `marker_test` database never collide.
- The BUG-038 spy patches `app.core.security.verify_password`; if the fix moves the import to module level in `app/dao/profile.py`, the patch target must become `app.dao.profile.verify_password` (then the card's Given line needs a revision).
