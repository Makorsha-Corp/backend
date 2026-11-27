# Verification — `app/core/deps.py`

> **Verdict:** PASS
> Tests: 79 passed · 6 xfailed (reproduced ✅) · coverage 100% branch (55 stmts, 16 branches)
> Mutation: 45 mutants · 43 killed · 2 survived → score 100% (after excluding 1 equivalent, 0 dead, 1 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
These tests can be trusted. I re-audited against cases revision 3, which changes no case (it only
states the "one representative re-read per error row" convention outright). All 66 case IDs map
one-to-one onto tests. The tests assert the exact status, detail and header values, re-read the
database where the cases require it, and mock only the spy `SessionLocal` and the app-client
`get_db` / `get_current_user` overrides that the Conventions prescribe. With `--runxfail`, all six
BUG-440 xfails fail on the stated assertion (`403 == 404`). Both surviving mutants are explained:
one is equivalent and one is on the bug-path. Nothing needs to change.

## Findings
None.

(Informational only, not a finding: the test module docstring still says "cases.md (revision 2)".
Revision 3 changed no case, and the notes record that the test file stayed the same.)

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 16 | 66 | `raise credentials_exception` → `pass` (sub missing) | equivalent | When `sub` is absent, `user_id_str` is `None`. Execution falls through to `int(None)`, which raises `TypeError`. Line 70 catches it and line 71 re-raises the same `credentials_exception` object (401, "Could not validate credentials", `WWW-Authenticate: Bearer`). Nothing touches the DB in between. The only difference is `__context__`, which callers and HTTP clients cannot observe. | — |
| 41 | 155 | 403 detail `"You do not have access to this workspace"` → `""` | bug-path | Spec R8/R9 tag this branch [BUG-440]. The intended result is 404 `"Workspace with ID {id} not found"`, so this 403 detail goes away when the bug is fixed. Only the xfail cases (CW-11/13/14/19) target it. Their pass counterparts (CW-12/15/20/23) deliberately assert DENIED (403 or 404) so they keep passing after the fix. | — |

## Traceability
Cases: 66 · test functions: 65 (85 collected) · unmatched IDs: none · tests without a case ID: none.
PA-04 and PA-05 share one function as two `pytest.param` ids, and each ID appears exactly once.
Marker mismatches: none. Every `pass` case has no xfail marker. CW-11, CW-13, CW-14 (×3) and CW-19
carry `xfail(strict=True, reason="BUG-440: …")`. The check was an AST scan of the test file
against the cases table's `| DEPS-…` rows.

BUG-440 is still missing from `docs/testing/bugs.md`. It is recorded in
`tests/unit/core/deps.bugs-staging.md` and will reach the register at the batch merge. I accept the
staging file as satisfying the "BUG ID exists" check (best-practice default, delegated by
reviewer). In batch mode `bugs.md` is frozen, and staging files are the designated source.

Fidelity: I compared every Then item with its test. Checked items:
- The exact E401 dict (`headers ==`).
- The exact 400/404/403 details, and the parsed-integer detail in CW-06 and CW-07.
- CU-11 matches its case's own values (`exp = PAST`).
- Re-reads use `expire_all()` plus a fresh query where the cases ask for them: CU-07/22/27,
  AU-01/03, CW-01/02/09/12/15/16/23, PA-01/02/03. This also satisfies the rev-3 convention.
- No `try/except` around actions. DB-07 has a `try/finally`, but it only closes the generator.
- No `pytest.raises(Exception)`, and no mocked session or DAO.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/core/test_deps.py -q -p no:cacheprovider --cov=app.core.deps --cov-branch --cov-report=term-missing
  app\core\deps.py   55   0   16   0   100%
  79 passed, 6 xfailed, 3 warnings in 7.01s

.venv/Scripts/python.exe -m pytest tests/unit/core/test_deps.py -q -p no:cacheprovider --runxfail -rf
  6 failed, 79 passed — all 6 (CW-11, CW-13, CW-14 suspended/invited/Active, CW-19) fail on
  "AssertionError: assert 403 == 404" (HTTPException(403, 'You do not have access to this workspace'))

.venv/Scripts/python.exe -m pytest tests/unit/core/test_deps.py -q -p no:cacheprovider   (×2, flakiness)
  79 passed, 6 xfailed in 4.19s
  79 passed, 6 xfailed in 3.85s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/deps.py tests/unit/core/test_deps.py --timeout 180 --json %TEMP%/deps_mut_verify.json
  Mutants: 45 · killed 43 · timeout 0 · survived 2 · score 96% (raw)
  SURVIVED #16 L66:8 raise: raise -> pass
  SURVIVED #41 L155:19 const: 'You do not have acce' -> ''
```
Results match the notes' Result line (79 passed · 6 xfailed · 100% branch).
