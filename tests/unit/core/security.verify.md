# Verification — `app/core/security.py`

> **Verdict:** PASS
> Tests: 61 passed · 7 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 32 mutants · 29 killed · 3 survived → score 100% (after excluding 0 equivalent, 0 dead, 3 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Each of the 68 cases in revision 2 is implemented exactly once, and the assertions match the cases. The only mock is `app.core.security.utcnow`, which the spec's "Externals to mock" allows. The runs match the notes' Result line and gave the same outcome three times. With `--runxfail`, each of the 7 xfails fails on the assertion its case names. The 3 surviving mutants are all on the over-72-byte branch of `verify_password` (lines 59–60). That branch is BUG-500, and only strict-xfail tests cover it, so the survivors go away once the bug is fixed. No stage has anything to fix.

## Findings
None.

Note (not a finding): BUG-500, BUG-501 and BUG-502 are not in `docs/testing/bugs.md` yet. They are in `tests/unit/core/security.bugs-staging.md`, which the batch merge step adds to `bugs.md` later. For batch mode, this verifier accepts a BUG ID that is listed in the module's staging register (best-practice default, delegated by reviewer).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 13 | L60 | `raise ValueError(...)` → `pass` | bug-path | Raising for passwords over 72 bytes is the BUG-500 behavior. The intended behavior (R2) is to return `False`. Only xfail cases VP-14..VP-18 reach this branch, and the mutation run leaves xfail tests out. | — |
| 22 | L59 | `> 72` → `> 73` | bug-path | Only a password of exactly 73 bytes can tell the two apart, and what it does today (raise) is the BUG-500 path. The 72-byte boundary cases VP-12 and VP-13 pass, as they should. The 73-byte side is covered by xfail VP-14, VP-16, VP-17 and VP-18, which start guarding it once BUG-500 is fixed. | — |
| 28 | L60 | error message → `''` | bug-path | This is the message of the BUG-500 `ValueError`. The intended behavior never raises, so no passing case can check it. (The same message in `get_password_hash`, L86, is killed by GPH-03/05.) | — |

## Traceability
Cases: 68 (61 pass, 7 xfail). Test items: 68 across 62 test functions. Parametrized items carry `pytest.param(id="SEC-…")`, and every other test's docstring starts with its case ID. An AST script compared the two sets:
- Unmatched cases: none. Tests without a case ID: none. Duplicate IDs: none.
- Marker mismatches: none. CAT-11 has `xfail(strict=True, reason="BUG-501: …")`. VP-14..VP-18 have `xfail(strict=True, reason=_BUG_500)`, which starts with "BUG-500:". DT-17 has `xfail(strict=True, reason="BUG-502: …")`. No pass case has an xfail marker. All three BUG IDs exist in `security.bugs-staging.md` (see the note under Findings).

Fidelity: each test was read against its case's Given / When / Then:
- No missing, weakened or changed assertions. Exact values are checked with `==` and `is True` / `is False` where the case requires them. The GPH-03/05 message is compared exactly. HRT-01/02 use the sha256 test vectors.
- No swallowed failures. The `pytest.raises` types are the specific ones the cases name: `TypeError`, `ValueError` and `jwt.InvalidSignatureError`.
- No extra mocks. The only patch is `patch.object(security, "utcnow")`. `settings` is set with monkeypatch as the Conventions require.
- The module uses no database, so the in-memory check does not apply.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/core/test_security.py -q -p no:cacheprovider --cov=app.core.security --cov-branch --cov-report=term-missing
  app\core\security.py      46      0      8      0   100%
  61 passed, 7 xfailed, 3 warnings in 6.23s

.venv/Scripts/python.exe -m pytest tests/unit/core/test_security.py -q -p no:cacheprovider --runxfail -rf
  7 failed, 61 passed, 3 warnings in 5.82s
  CAT-11: assert 1767269700 == 1767268800 (ts(12,0,0); default 15 min applied)   -> BUG-501 assertion
  VP-14..VP-18: ValueError: Password exceeds bcrypt's 72-byte limit              -> BUG-500 assertion
  DT-17: AssertionError: assert {'sub': '1'} is None                             -> BUG-502 assertion

.venv/Scripts/python.exe -m pytest tests/unit/core/test_security.py -q -p no:cacheprovider   (x2, flakiness)
  61 passed, 7 xfailed, 3 warnings in 5.94s
  61 passed, 7 xfailed, 3 warnings in 5.96s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/security.py tests/unit/core/test_security.py --timeout 180 --json <system temp>/security_mut.json
  Mutants: 32 · killed 29 · timeout 0 · survived 3 · score 91% (raw)
  SURVIVED #13 L60:8 raise: raise -> pass
  SURVIVED #22 L59:29 const: 72 -> 73
  SURVIVED #28 L60:25 const: 'Password exceeds bcr' -> ''
```
