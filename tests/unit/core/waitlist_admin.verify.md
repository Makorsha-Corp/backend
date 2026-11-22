# Verification — `app/core/waitlist_admin.py`

> **Verdict:** PASS
> Tests: 13 passed · 6 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 14 mutants · 11 killed · 3 survived → score 100% (after excluding 0 equivalent, 0 dead, 3 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. All 19 cases (revision 2) map one-to-one to tests. Each test checks everything its case's Then column lists: exact status and detail, that the returned object is the same user, a fresh database re-read, and no pending session changes. The only patch is the `settings.WAITLIST_ADMIN_EMAILS` value, and no externals are mocked. All 6 xfails fail today on the documented assertion. The coverage, `--runxfail` and stability runs match the notes exactly. The 3 surviving mutants sit on the BUG-540/BUG-541 lines, which only the xfail tests reach, and they will go away when those bugs are fixed. Nothing needs to change.

## Findings
None.

Observation (not a finding, batch mode): BUG-540 and BUG-541 are defined in `tests/unit/core/waitlist_admin.bugs-staging.md` and are not in `docs/testing/bugs.md` yet. The batch rules forbid editing the shared register, so the merge agent folds them in later. The xfail reasons (`BUG-540: …`, `BUG-541: …`) match the staging entries (best-practice default, delegated by reviewer: staged IDs count as existing for traceability).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 4 | L32 | `return current_user` → `return None` | bug-path | Reached only when a non-admin's email matches the allowlist. Today's behaviour there is BUG-540 (the intended result is 403). Only the xfail cases WLA-G-11/12/13 target it, and the mutation run excludes xfail tests. | — (resolves when BUG-540 is fixed) |
| 7 | L20 | empty-allowlist `raise HTTPException(...)` → `pass` | bug-path | Execution falls through to L26: `""`/email not in the empty set, so it raises 403 with detail D-NA. That is exactly the behaviour the BUG-541 fix requires. The passing twins G-04/06/08 deliberately assert only the 403, and that still holds. The detail check lives in the xfail cases G-05/07/09. | — (resolves when BUG-541 is fixed) |
| 12 | L22 | detail `'Waitlist admin access requires…'` → `''` | bug-path | This is the configuration-revealing message of BUG-541. The spec says it should not exist, and only the xfail cases G-05/07/09 assert the detail on this path. | — (resolves when BUG-541 is fixed) |

## Traceability
Cases: 19 · tests: 19 (10 functions, 3 of them parametrized × 3 with `pytest.param(id="WLA-G-NN")`) · unmatched: none · every test carries exactly one case ID (non-parametrized ones in the name and docstring).
Marker mismatches: none. The 13 `pass` cases have no xfail marker. G-05/07/09 have `xfail(strict=True, reason=BUG_541)`, which names BUG-541. G-11/12/13 inherit the function-level `xfail(strict=True, reason=BUG_540)`, which names BUG-540.
Fidelity (all 19 cases read against their Given/When/Then):
- There are no missing or weakened assertions. Every case asserts `status_code == 403` exactly, and `detail == D_NA` exactly wherever the case states it. G-04/06/08 leave the detail out on purpose, as their cases say.
- The setup matches the Given in every case: saved rows for "Saved P", in-memory `Profile` for G-06/07/17–19, and `SimpleNamespace` for G-08–10. The allowlist is set explicitly in each test.
- "Row unchanged" is checked with `expire_all()`, a fresh `SELECT email, is_platform_admin`, and `not db.new` / `not db.dirty`, as the conventions require.
- No `try/except` blocks and no `pytest.raises(Exception)`. Every refusal uses `pytest.raises(HTTPException)`.
- No extra mocks. The only change is `monkeypatch.setattr(settings, "WAITLIST_ADMIN_EMAILS", …, raising=False)`.
- xfail honesty is confirmed with `--runxfail`: G-05/07/09 fail on `detail == D_NA`, and G-11/12/13 fail with `DID NOT RAISE HTTPException`. Both match the "fails today on" column, and there are no setup or import errors.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/core/test_waitlist_admin.py -q -p no:cacheprovider --cov=app.core.waitlist_admin --cov-branch --cov-report=term-missing
  app\core\waitlist_admin.py      14      0      6      0   100%
  13 passed, 6 xfailed in 6.27s

.venv/Scripts/python.exe -m pytest tests/unit/core/test_waitlist_admin.py -q -p no:cacheprovider --runxfail -rf
  6 failed, 13 passed in 3.98s
  G-05/07/09: AssertionError: assert 'Waitlist adm..._ADMIN_EMAILS' == 'Not authoriz...tlist signups'
  G-11/12/13: Failed: DID NOT RAISE HTTPException

Stability re-runs (x2): 13 passed, 6 xfailed in 4.64s / 13 passed, 6 xfailed in 5.53s   (no flakiness; matches notes)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/waitlist_admin.py tests/unit/core/test_waitlist_admin.py --timeout 180 --json %TEMP%/waitlist_admin_mut.json
  Mutants: 14 · killed 11 · timeout 0 · survived 3 · score 79% (raw)
  SURVIVED #4 L32:4 return: return None
  SURVIVED #7 L20:8 raise: raise -> pass
  SURVIVED #12 L22:19 const: 'Waitlist admin acces' -> ''
```
