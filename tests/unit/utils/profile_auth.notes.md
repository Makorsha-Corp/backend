# Execution notes — `app/utils/profile_auth.py`

> Cases: `tests/unit/utils/profile_auth.cases.md` (revision 2) · Tests: `tests/unit/utils/test_profile_auth.py` · Source commit: e48a092
> Result: 14 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_profile_auth.py -q -p no:cacheprovider --cov=app.utils.profile_auth --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → helpers** (top of the test file):
  - P1 → `_make_p1(db, is_platform_admin=False)` / fixture `p1`: wraps the existing `make_profile` factory with the case's name/email/timezone/password hash; `user_id` is left to the factory (any unique value). Flushed, so `id` is assigned and the `is_platform_admin` column default is applied.
  - Transient Profile → `Profile(...)` never added to the session; `_nadia()` builds the PAUTH-D-05 / D-10 input with no `is_platform_admin` argument (attribute is `None`; D-05 asserts this precondition).
  - NS(...) → `types.SimpleNamespace` (alias `NS`). EXPECTED_KEYS → module constant.
- **Mocks:** none (spec lists no externals; no race simulations).
- **Re-read:** PAUTH-D-09 does `db.expire_all()` then a fresh `SELECT … WHERE id` and asserts the row columns. Error cases (D-11..D-13) check the input object's `vars()` are unchanged, since the function has no database access.
- **Parametrized:** PAUTH-D-13 as two params (`PAUTH-D-13a-missing-email`, `PAUTH-D-13b-missing-timezone`), per the cases file — hence 14 test items for 13 case IDs.
- **Best-practice default (delegated by reviewer):** PAUTH-D-08 (`0` → `False`) implemented as designed.
- Stability: 3 runs, identical outcome (14 passed) — revision 1 and again for revision 2.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (4 statements, 0 branches; the `getattr` default and `bool()` conversion are expressions, not branches, and are exercised by D-04..D-08).

## Factories added
None (batch mode: `tests/unit/factories.py` not edited). Existing `make_profile` was reused with overrides; no new builder needed and nothing worth promoting (P1 is module-specific data).

## Notes for maintainers
- P1 uses the fixed email `rahim@example.com` (unique column). Each test is rolled back, but a concurrent uncommitted insert of the same email by another test process would make this insert wait on the unique index until that transaction ends; harmless, only a possible short delay.
- If the auth payload gains a field, update EXPECTED_KEYS and the exact-dict assertions in D-01, D-06, D-09 (after the spec/cases change).

## Revision history
- **Cases revision 2 (2026-09-29):** cases file re-issued with no changed, added or retired IDs (spec unchanged, verify PASS with no findings, 8/8 mutants killed). No test changed; only the module docstring's cases-revision reference was bumped to 2. Re-run: 14 passed ×3 (stable), branch coverage 100%. No `test-weakness` findings to fix.
