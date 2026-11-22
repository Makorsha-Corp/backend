# Verification — `app/managers/base_manager.py`

> **Current verdict (round 2, 2026-11-10):** PASS. Findings 1 and 2 are fixed · 6 passed · mutation 100% (1 equivalent).
>
> **Verdict (round 1):** NEEDS WORK
> Tests: 6 passed · 0 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 1 mutant · 0 killed · 1 survived → score 100% (0/0 after excluding 1 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
The suite is small and mostly faithful. Runs, coverage and the three repeat runs match the notes. The one mutant is equivalent.
One test does not match its card: BMG-I-01 got the BMG-I-05 Revision 3 change by mistake. It allows `__orig_class__` on a plain instance and adds a Then 3 the card does not have. A hand variant that adds `__orig_class__` to every instance passes BMG-I-01, although the card's `vars(result) == {"model": Department}` would fail. Other tests catch that variant (I-02, I-03, I-06), so the gap is in fidelity, not in what the suite as a whole notices. The executor restores the card's exact assertion.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Weakened assertion + extra Then | BMG-I-01 · test lines 21–24 | Card Then 2 is `vars(result) == {"model": Department}` (2 Then lines). The test checks `vars(result)["model"] is Department` and `set(vars(result)) - {"__orig_class__"} == {"model"}` (labelled Then 2 / Then 3). That is the I-05 Revision 3 wording copied onto I-01. | Variant `BMV=orig` (plain `__init__` also stores `__orig_class__`): `test_bmg_i_01` **passes**. Under the card's assertion it would fail. | **executor** |
| 2 | Notes accuracy (minor) | notes "Verification runs (revision 3)" | It names the reference plugin `lowsupemm_ref.py`. The file is `lowsupe\bm\bm_ref.py`. | directory listing | **executor** |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L6:20 | `TypeVar("ModelType")` → `TypeVar("")` | equivalent | The TypeVar's name only shows in its `repr`. The spec lists `ModelType` under Not specified (typing only), and nothing at run time reads the name. | — |

## Hand variants (verifier plugin `lowsupv\bm\bmv.py`)
| Variant | Killed by |
|---|---|
| plain instance also stores `__orig_class__` | I-02, I-03, I-06 (**not I-01**, see finding 1) |
| extra attribute stored | I-01, I-02, I-03, I-05, I-06 |
| `None` rejected | I-02 |
| non-class rejected | I-02, I-03 |
| `model=None` default (no TypeError) | I-04 |

## Traceability
cases 6 · tests 6 · unmatched: none · marker mismatches: none (no xfail cards, no markers). Card order kept.

## Commands run
```
COVERAGE_FILE=<lowsupv>\.cov.bm .venv/Scripts/python.exe -m pytest tests/unit/managers/test_base_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.base_manager --cov-branch --cov-report=term-missing
  app\managers\base_manager.py  6 0 0 0 100%   →  6 passed
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_base_manager.py -q -p no:cacheprovider -o addopts="" --runxfail -rf   →  6 passed
(repeat ×2) → 6 passed · 6 passed
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/base_manager.py tests/unit/managers/test_base_manager.py --json <lowsupv>\mut_bm.json
  Mutants: 1 · killed 0 · timeout 0 · survived 1 · score 0%   (the 1 survivor is equivalent)
BMV=<variant> PYTHONPATH=<lowsupv>\bm pytest … -p bmv   (results in the table above)
```

## Round 2 — 2026-11-10

> **Verdict:** PASS
> Tests: 6 passed (3 identical runs; `--runxfail` 6 passed) · coverage 100% branch
> Mutation: no real-gap survivor in round 1 (the one survivor is equivalent), so no re-run was needed. Score 100%.
> Cases revision: 3 (unchanged)

- **Finding 1 fixed.** BMG-I-01 now asserts `result.model is Department` (Then 1) and `vars(result) == {"model": Department}` (Then 2), exactly as the card says, and has no extra Then. Variant `BMV=orig` (a plain instance that also stores `__orig_class__`) now **fails** BMG-I-01, as well as I-02, I-03 and I-06.
- **Finding 2 fixed.** The notes name `lowsupe\bm\bm_ref.py`.
- No other test changed. Traceability: 6 cards · 6 tests · no markers.

```
lowsupv/r2/runs.sh managers base_manager bm  → 6 passed (x3), --runxfail 6 passed, base_manager.py 100%
BMV=orig PYTHONPATH=lowsupv/bm pytest tests/unit/managers/test_base_manager.py -p bmv  → 4 failed (I-01, I-02, I-03, I-06), 2 passed
```
