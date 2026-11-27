# Verification — `app/utils/work_order_generation.py`

> **Verdict:** PASS
> Tests: 26 passed · 12 xfailed (reproduced ✅) · coverage 88% branch (100% of specified code; the only miss is the dead branch L28–31)
> Mutation: 13 mutants · 9 killed · 4 survived → score 100% (9/9, after excluding 0 equivalent, 2 dead, 2 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. All 38 cases in revision 2 of the cases file map one-to-one to tests. Every xfail is strict, names its bug, and under `--runxfail` fails on exactly the "fails today on" assertion from its case. The runs reproduce the notes: 26 passed, 12 xfailed and 88% branch coverage, with identical results across three runs. Every mutant on specified, non-bug behavior was killed. The 4 survivors are either in the dead L27–31 branch or change the 1000-row cap, which BUG-342 says should be removed. Nothing needs fixing.

## Findings
None.

Informational (not a finding): BUG-340..343 are not yet in `docs/testing/bugs.md`. In batch mode they are staged in `tests/unit/utils/work_order_generation.bugs-staging.md` and will be merged later by the merge agent. The IDs and titles there match the xfail reasons used in the test file.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 9 | L31 | `return [m.id for m in machines]` → `return None` | dead | Inside the second `if factory_section_id:` branch (L27–31). The spec's "Not specified" section lists it as dead code to remove (Q4). It can't run: `section_id = template.default_factory_section_id or factory_section_id` is truthy whenever `factory_section_id` is, so the L22 branch returns first. | — |
| 11 | L24 | `limit=1000` → `limit=1001` (section lookup) | bug-path | Spec R5b [BUG-342] says there should be no cap. The mutant only changes results for sections with more than 1000 machines. Only WOG-R-28 covers that case, and it is an xfail for BUG-342, so the mutation run excludes it. The pass-side boundary WOG-R-27 (1000 → 1000) still holds under the mutant, as it should. A lowered cap (for example 999) would be caught by WOG-R-27. | — (resolves when BUG-342 is fixed) |
| 12 | L29 | `limit=1000` → `limit=1001` (dead section branch) | dead | In the same dead branch as #9 (Q4). | — |
| 13 | L34 | `limit=1000` → `limit=1001` (factory lookup) | bug-path | Same argument as #11 for the factory path (R5b/R7 [BUG-342]). Only WOG-R-37 (xfail) goes above 1000 machines, and the pass-side WOG-R-36 is unaffected. | — (resolves when BUG-342 is fixed) |

Killed mutants: negated conditions at L20, L22, L27 and L32; `or` → `and` at L19; `return None` at L21, L26, L36 and L37.

## Traceability
cases 38 · tests 38 · unmatched: none · marker mismatches: none. I checked this with an AST script: the case-ID set from the cases file equals the set of IDs in the test names, and each ID maps to exactly one test.
- None of the 26 `pass` cases has an xfail marker.
- The 12 `xfail` cases each use `xfail(strict=True)`, with a reason that names the case's bug:
  - R-07, R-08, R-09 → BUG-340
  - R-10 to R-14 → BUG-341
  - R-26 and R-35 → BUG-343
  - R-28 and R-37 → BUG-342
- All four BUG IDs are in the module's bugs-staging file. They are waiting to be merged into `bugs.md` (batch mode).

**Fidelity:** I read every test against the Given/When/Then of its case and found no problems.
- **Setup:** every Given is reproduced.
  - WOG-R-18 has a W2 machine assigned to W1's S1.
  - WOG-R-07, WOG-R-09, WOG-R-10 and WOG-R-11 put live machines in the template's section or the requested factory/section, so a wrong fall-through would be caught once the bug is fixed.
  - WOG-R-09 asserts that id 2147483000 does not exist before the call.
  - The ordering helper asserts that ids ascend in insertion order.
- **Assertions:**
  - "Set equals" is sorted equality plus a length check, as the conventions require.
  - "Returns [X]" uses exact `==`.
  - I checked the expected order in the ordering cases, `[B, C, A, E, F, D]`, by hand against lower(name), then id.
  - "No pending changes" checks `db.new` and `db.dirty` in R-01, R-15, R-29 and R-38.
- **Mocks and error handling:** nothing is mocked, and there is no `try/except` and no `pytest.raises`.
- **Under `--runxfail`:**
  - R-07 to R-14 fail on `assert [id] == []`.
  - R-26 and R-35 fail on exact list order.
  - R-28 and R-37 fail on `assert 1000 == 1001`.
  - None fails on a setup or import error.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_generation.py -q -p no:cacheprovider --cov=app.utils.work_order_generation --cov-branch --cov-report=term-missing
  app\utils\work_order_generation.py      18      2      8      1    88%   28-31
  26 passed, 12 xfailed in 7.46s

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_generation.py -q -p no:cacheprovider --runxfail -rf
  12 failed, 26 passed in 5.03s   (the 12 failures are exactly the 12 xfail cases, each on its stated assertion)

.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_generation.py -q -p no:cacheprovider   (x2, flakiness check)
  26 passed, 12 xfailed in 4.73s
  26 passed, 12 xfailed in 5.91s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/work_order_generation.py tests/unit/utils/test_work_order_generation.py --timeout 180 --json C:/Users/User/AppData/Local/Temp/wog_mut.json
  Mutants: 13 · killed 9 · timeout 0 · survived 4 · score 69% (raw)
  SURVIVED #9 L31:8 return None · #11 L24:85 1000->1001 · #12 L29:93 1000->1001 · #13 L34:77 1000->1001
```
