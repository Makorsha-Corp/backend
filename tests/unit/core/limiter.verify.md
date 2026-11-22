# Verification — `app/core/limiter.py`

> **Current verdict:** PASS (2026-11-03, after round 2 and the LIM-01 docstring fix)
>
> **Verdict:** NEEDS WORK — the describer first (fill-gaps), then the case designer. No test is wrong.
> Tests: 11 passed · 0 xfail (reproduced ✅) · coverage 100% branch (3 statements, 0 branches)
> Mutation: 0 mutants · no score (`mutate.py` finds no site in one constructor call; the hand variants carry the check)
> Fidelity: **0 of 11 unfaithful** (11 / 11 right)
> Hand variants: 10 · 7 caught by a pass card · 3 others: 2 in one rule gap, 1 equivalent
> Source commit: e48a092 · Cases revision: 2; spec APPROVED (Gap log G1 applied)

## Summary
- **The tests can be trusted as written.** Every test was read against its card by eye (the Givens here are client calls my script does not rebuild); the script agrees on IDs, markers, Then blocks and When.
- **Why NEEDS WORK:** R5 "no key prefix" and R7 "errors of the storage are not swallowed" have no assertion. A limiter built with `swallow_errors=True` or a key prefix passes all 11. The case designer could not write these lines: the spec's Notes do not name the attributes (cases Spec gap 2), and the Gap log has no answer to it.
- Nothing here touches the database, money or orders.

Written by Claude (all 11 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 11. No `limiter.local-run.json` exists.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | spec-gap | `limiter` R5 "no key prefix", R7 "errors of the storage are not swallowed" (cases Spec gap 2, still open) | The Notes list the private attributes for every other setting, not for these two, so LIM-01 has no line for them. | `lim_r5_prefix` (`key_prefix="mk"`) and `lim_r7_swallow` (`swallow_errors=True`) pass all 11. | **describer** (fill-gaps), then **case designer** |

### Recipe
- **Describer:** add to the Notes, after the list of private attributes: `limiter._key_prefix` (`""`) and `limiter._swallow_errors` (`False`). I checked both names on the installed slowapi 0.1.10 (`vars(limiter)`); the Gap log line is the describer's to write.
- **Case designer, after that:** two new Then lines on LIM-01: `returns: lim._key_prefix == ""` and `returns: lim._swallow_errors is False`. Each holds today and fails its variant above.

## Surviving mutants
None (0 mutants). `limiter = Limiter(key_func=get_remote_address)` has no constant, comparison or return for `mutate.py` to change.

## Hand variants
`variants.py`: whole-module rewrites of the constructor, run with `--runxfail`. Every edit was asserted to apply once, and every run reached all 11 tests.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| lim_r1 | 1 | 1 | LIM-01, LIM-03, LIM-07 … LIM-11 | — |
| lim_r3 | 2 | 2 | LIM-01 | — |
| lim_r4 | 1 | 1 | LIM-01 | — |
| lim_r5 | 2 | 1 | LIM-01 | `lim_r5_prefix` |
| lim_r6 | 1 | 1 | LIM-01, LIM-03, LIM-07 … LIM-11 | — |
| lim_r7 | 3 | 1 | LIM-01, LIM-03, LIM-07 … LIM-11 | `lim_r7_swallow`, `lim_r7_memory_uri` |
| **Total** | **10** | **7** |  | **3** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `lim_r7_memory_uri` | **Equivalent:** `storage_uri=None` already means `memory://`; LIM-01's `isinstance(lim._storage, MemoryStorage)` holds either way. |

## Reproduced claims
- **Result line of the notes holds:** `11 passed` in 4 of 4 runs, the coverage run among them. No flaky test.
- `--runxfail`: 11 passed (no xfail card).
- **Mocks:** none; the autouse fixture calls `limiter.reset()` before and after each test, as the Conventions say. Route functions get unique names per built app (notes, "Unique route function names"): harness hygiene, no setting is changed.

## Traceability
cases 11 · tests 11 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card. `ruff check` passes. `rebuild.py`: 0 reports, 15 Given lines left to my eye (client calls and `req(...)`), all as the cards say.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/core/limiter.py tests/unit/core/test_limiter.py --timeout 300 --json <scratch>/res/mut_limiter.json
  Mutants: 0
.venv/Scripts/python.exe -m pytest tests/unit/core/test_limiter.py -q -p no:cacheprovider --cov=app.core.limiter --cov-branch --cov-report=term-missing
  11 passed · TOTAL 3 0 0 0 100%
pytest (same file), 3 more runs                               11 passed each
drive.py bases limiter; drive.py vars limiter; rebuild.py
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctv\`. Private `COVERAGE_FILE`. Only this report was written in the repo. No commit. Nothing was killed.

## Fix list
1. **Describer (fill-gaps):** name `limiter._key_prefix` and `limiter._swallow_errors` in the Notes (closes cases Spec gap 2).
2. **Case designer:** the two LIM-01 lines above.
3. **Executor:** implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 3, narrow)

> **Verdict:** NEEDS WORK — the executor has one docstring line to change. The rule gap is closed.
> Tests: 11 passed · 0 xfail (reproduced ✅) · coverage 100% branch
> Mutation: not re-run; 0 mutants (round 1)
> Fidelity: **0 of 11 unfaithful** (LIM-01 read by eye; all 11 rebuilt by script)
> Source commit: e48a092 · Cases revision: 3; spec Gap log G2

**Correction to round 1.** My recipe said `lim._key_prefix == ""`. That was wrong: from the repository root the value is `None` (checked again: `repr(limiter._key_prefix)` gives `None`). The card's `not lim._key_prefix` (spec G2) is right.

### Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | traceability | LIM-01 docstring | The docstring's Rules line is the old one. The card now reads `` `limiter` R1, R3, R5, R6, R7 (incl. no key prefix, storage errors not swallowed) ``; the test says `` Rules: `limiter` R1, R3, R5, R6, R7 ``. The assertions are right. | `rebuild.py`: `LIM-01 doc: docstring Rules differ` | **executor** |

### New lines
| Card | Recipe | Fails |
|---|---|---|
| LIM-01, Then 9 `not lim._key_prefix` | round 1 Finding 1 | `lim_r5_prefix` |
| LIM-01, Then 10 `lim._swallow_errors is False` | round 1 Finding 1 | `lim_r7_swallow` |

Both variants fail LIM-01 on all three plans; every run reached all 11 tests. Hand variants now: 10, 9 caught by a pass card, 1 equivalent (`lim_r7_memory_uri`).

### Reproduced
- **Result line of the notes holds:** `11 passed` in 3 of 3 runs, the coverage run among them; `--runxfail` 11 passed. `ruff check` passes.
- **Traceability:** cases 11 · tests 11 · unmatched: none · marker mismatches: none · docstring mismatch: LIM-01 (Finding 1).

### Commands run
```
rebuild.py                                                     LIM-01 doc: docstring Rules differ
var:limiter:lim_r5_prefix, var:limiter:lim_r7_swallow × 3 plans    both fail LIM-01
drive.py bases limiter; pytest tests/unit/core/test_limiter.py --cov=app.core.limiter --cov-branch, then 2 more runs
```
No full mutation run (narrow round). Only this report was edited in the repo. No commit. Nothing was killed.

### Fix list
1. **Executor:** copy LIM-01's Rules line into its docstring. That makes it PASS; the variants do not need re-running.

## Main session, 2026-11-03
LIM-01's docstring Rules line copied from its card, the one fix round 2 named; the file passes (11 passed). Verdict: PASS.
