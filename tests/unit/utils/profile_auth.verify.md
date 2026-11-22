# Verification — `app/utils/profile_auth.py`

> **Verdict:** PASS
> Tests: 14 passed · 0 xfailed (reproduced ✅, none expected) · coverage 100% branch
> Mutation: 8 mutants · 8 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. All 13 cases (revision 2) are implemented one-to-one
with exact assertions (full-dict `==`, `is True` / `is False` identity checks,
the specific `AttributeError` type), the persisted-profile case re-reads the row
after `expire_all()`, and nothing is mocked. Runs match the notes' Result line
and stay the same across three runs. All 8 mutants (return value, each key name,
the `getattr` attribute name and default) are killed. No changes required.

## Findings
None.

## Surviving mutants
None (8/8 killed).

## Traceability
cases 13 · tests 13 functions / 14 items (PAUTH-D-13 is parametrized as
`PAUTH-D-13a-missing-email` and `PAUTH-D-13b-missing-timezone`, as the cases file specifies)
· unmatched: none (the second `PAUTH-D-05` match is the `_nadia()` helper
docstring, not a test) · marker mismatches: none (0 xfail cases, 0 xfail
markers, no BUG IDs used, so nothing to check in `bugs.md`).

Fidelity notes (no findings):
- PAUTH-D-01 asserts every Then item, including `isinstance(result, dict)`, exact key set, full dict, and `"hash-secret-xyz" not in result.values()`.
- PAUTH-D-05 asserts the `is None` precondition before the call.
- PAUTH-D-08 carries the "(best-practice default, delegated by reviewer)" marker from the cases file.
- PAUTH-D-09 uses `db.expire_all()` instead of `session.expire(P1)`. That check is at least as strong. The re-select by id asserts all five columns plus the return dict, and `p1 not in db.dirty` is asserted.
- PAUTH-D-10 asserts no write-back of the flag, independence of the result, and `second is not result`.
- PAUTH-D-11..13 use `pytest.raises(AttributeError)` (specific type) and check `vars(obj)` unchanged (D-11 also checks exactly 4 attributes).
- No `mock`/`patch`, no `try/except`, no xfail markers (grep confirmed).

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_profile_auth.py -q -p no:cacheprovider --cov=app.utils.profile_auth --cov-branch --cov-report=term-missing
  app\utils\profile_auth.py  4 stmts  0 miss  0 branch  0 brpart  100%
  14 passed in 3.73s   (repeat runs: 14 passed in 3.30s; 14 passed in 3.05s — stable)

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_profile_auth.py -q -p no:cacheprovider --runxfail -rf
  14 passed in 2.96s   (no xfail tests to reproduce)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/profile_auth.py tests/unit/utils/test_profile_auth.py --timeout 180 --json <scratchpad>/profile_auth_mut.json
  [1/8] L8:4   return -> return None            KILLED
  [2/8] L9:8   'id' -> ''                       KILLED
  [3/8] L10:8  'name' -> ''                     KILLED
  [4/8] L11:8  'email' -> ''                    KILLED
  [5/8] L12:8  'timezone' -> ''                 KILLED
  [6/8] L13:8  'is_platform_admin' -> ''        KILLED
  [7/8] L13:48 'is_platform_admin' -> ''        KILLED
  [8/8] L13:69 False -> True                    KILLED
  Mutants: 8 · killed 8 · timeout 0 · survived 0 · score 100%
```
