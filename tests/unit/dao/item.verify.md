# Verification — `app/dao/item.py`

> **Verdict:** NEEDS WORK (round 2, 2026-10-17)
> Fix round after round 2 (main session, 2026-10-17): ITEM-S-25 / S-26 re-marked non-strict (bodies unchanged); new strict ITEM-S-28 (statement recorder) fails today on Then 2 — no `lower(items.name)` / `items.id` after the score. File: 77 passed · 34 xfailed, 3 runs. With the round-2 finding closed this module meets PASS.
> Tests: 77 passed · 33 xfailed (reproduced ✅) · coverage 97% branch
> Mutation: 66 mutants · 51 killed · 15 survived → score 100% (51/51, after excluding 1 equivalent, 14 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

# Round 2

## Summary
All four round-1 findings are closed. AF-46/47/48 put the search text in the middle of a sku, a unit and a tag name, and mutants 46, 48 and 51 are now killed. S-01 and S-05 assert the tuple-like `Row` properties that spec R10 (fill-gaps G7) states. Every survivor is dead code (14) or the documented equivalent mutant 39. Traceability is clean, the run matches the notes, and the file gave the same result in 5 normal runs and under a forced sequential and a forced index scan. One new finding blocks PASS, under today's pipeline rule: the strict xfails ITEM-S-25 and ITEM-S-26 rest on the physical order of tied rows, because the similar-name query has no tie-breaker. No pass test depends on row order. No approved rule conflicts with the later soft-delete decisions.

## Round-1 findings — status
| R1 # | Finding | Status | Evidence |
|---|---|---|---|
| 1 | sku matched only at start (mutant 46) | ✅ closed | ITEM-AF-46: sku `"XX-ZETA-YY"`, search `"zeta"`, no other field of A contains it. test_item.py:660–667 asserts `== srt(a)` and B absent. Mutant 46 (L49:29 leading `%` removed) KILLED, and twin 47 (trailing `%`) KILLED too |
| 2 | unit matched only at start (mutant 48) | ✅ closed | ITEM-AF-47: unit `"bigzetaroll"`, search `"ZETA"`. test_item.py:670–677. Mutant 48 (L50:30) KILLED, mutant 49 KILLED |
| 3 | tag name matched only at start (mutant 51) | ✅ closed | ITEM-AF-48: active tag `"Hot-dip galvanized"`, search `"GALV"`, no field of A contains it. test_item.py:680–689. Mutant 51 (L61:37) KILLED, mutant 52 KILLED |
| 4 | S-01 "2-tuples" wording | ✅ closed | Spec G7 adds Returns + R10 (`list` of `sqlalchemy.engine.Row`, not `tuple`). The S-01 card asserts `type(result) is list`, len 1, `isinstance(row, Row)`, `len(row) == 2`, `row[0]` Item A, `row[1]` float 1.0, unpacking, B absent, session clean, and no `isinstance(row, tuple)`. test_item.py:1093–1111 has every line, in order. The S-05 card adds `type(result) is list` to `[]` with 0 statements: test_item.py:1135–1143, split out of the S-06..08 parametrization, which is unchanged |

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | row-order dependence (strict xfail) | ITEM-S-25, ITEM-S-26; source L218–220 (`order_by(desc("score"))`, no tie-breaker) | Both cards are `xfail BUG-018` **strict**, and both expect a specific order of 7 rows tied at score 1.0. Today Postgres returns ties in physical row order, and the top-N sort is not stable, so the failure rests on row order. If physical order ever matches the expected order (or, for S-25, the 5 rows kept by the limit happen to be the right ones in the right order), the strict xfail XPASSes and the run fails. If it does not, the test cannot tell a fix from luck. The cases file says so itself (Reviewer summary: "strict xfail could flake"). Today's rule: no strict xfail may depend on physical row order. | `--runxfail`: test_item.py:1349 `['delta', 'Bravo', …, 'echo'] == ['alpha', 'Bravo', …, 'delta']`; test_item.py:1361 same, starting with `'delta'` (storage order). Stable over 7 runs, but stability is not the criterion. | **case designer**: re-mark S-25 and S-26 `xfail BUG-018 (non-strict)`, `Author: claude`, and add one **strict** statement-recorder card for `find_similar_by_name_in_workspace` that records the emitted SQL and asserts its `ORDER BY` has the BUG-018 tie-breakers after the score (name case-insensitive, then `id`), per test-case-designer SKILL "Missing sort order". Then the **executor** implements it. |

No other fidelity findings in the 110 cases. The three new tests (AF-46/47/48) and the changed S-01/S-05 were read line by line against their cards: there are no missing or weakened assertions, wrong setups, extra mocks or swallowed failures.

### Order assertions checked (today's row-order rule)
| Query | ORDER BY today | Order-comparing cases | Depends on physical order? |
|---|---|---|---|
| `list_active_items_filtered` | `DISTINCT ON (id) … ORDER BY id` | pass L-01, L-05, L-06, L-07, L-09. Strict xfail L-04, L-13, L-14, L-15 | No. `id` is unique, so the order is total. The xfails fail on the id-order result (deterministic) |
| `_apply_item_catalog_filters` (via list) | — | AF-* compare `sorted(ids)` | No |
| `count_active_items_filtered` | n/a (scalar) | — | No |
| `distinct_units_in_workspace` | `ORDER BY unit` over `DISTINCT unit` | pass U-01, U-08 (distinct lowercase letters). Xfail U-05/U-07/U-12 | No. The values are distinct, so the order is total. The xfails fail on content (case/whitespace spellings), whatever the order |
| `find_similar_by_name_in_workspace` | `ORDER BY score DESC` only | pass S-23/S-24 (distinct scores 1.0 > 0.583 > 0.368). S-14/S-19..22 compare **sets**. S-15 checks only the score | Pass cases: no. **Strict xfail S-25/S-26: yes**, see Finding 1 |

## Check against later decisions (spec predates them)
- **Soft-deleted rows hidden:** consistent. Items with `is_active = False` are never returned: AF R2, S R6 and U R2.
- **Things of a soft-deleted parent hidden, not cascaded:** consistent. Items' only soft-deletable parent here is the tag (`Workspace` has no deleted flag). Spec Q7/Q8 background says tag assignments are kept when a tag is deleted. AF R6 and R12 hide matches through a deleted tag by the tag's current state alone, so a restored tag matches again. This agrees with BUG-935 ("links to deleted tags … hidden while the tag is deleted and shown again once it is restored").
- **Raw lookups may return deleted rows:** consistent. Inherited `BaseDAO` methods are "Not specified" and deferred to the BaseDAO spec (HR-4 scope).
- No approved rule needs the describer.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 7 | 89 | `return None` in `search_by_name_in_workspace` | dead | Spec "Not specified": dead code, to be removed (Q4) | — |
| 8 | 116 | `return None` in `get_active_items_in_workspace` | dead | same (Q4) | — |
| 17, 18 | 74 | default `skip` 0→1, `limit` 100→101 | dead | `search_by_name_in_workspace` signature (Q4) | — |
| 19, 20 | 102 | default `skip` 0→1, `limit` 100→101 | dead | `get_active_items_in_workspace` signature (Q4) | — |
| 56, 57, 62 | 92, 94 | `==`→`!=` (workspace, is_active), `True`→`False` | dead | `search_by_name_in_workspace` (Q4) | — |
| 65, 66 | 93 | leading / trailing `'%'`→`''` | dead | same | — |
| 58, 59, 63 | 119, 120 | `==`→`!=` (workspace, is_active), `True`→`False` | dead | `get_active_items_in_workspace` (Q4) | — |
| 39 | 210 | `score >= 0.35` → `>` | equivalent | `similarity()` is `real`. Widened to double, it can never equal the double 0.35 (nearest float4 is 0.3499999940…), so `>=` and `>` select the same rows. The case is covered by the S-11 xfail (BUG-034) once fixed | — |

Totals: 66 mutants · 51 killed · 0 timeout · 15 survived (14 dead + 1 equivalent) → 51/51 = 100%. Mutants 46, 48 and 51 (round-1 survivors) are now KILLED. The kill/survive set otherwise matches round 1 exactly, so the run was not disturbed.

## Traceability
Cases 110 (77 pass · 33 xfail) · test functions 105 (110 test items; L-10/11, S-03/04, S-06..08 and S-21/22 are parametrized with one `pytest.param(id=…)` per case; S-05 now has its own test).
- Every case ID is in exactly one test, and no test lacks a case ID (AST script).
- Marker mismatches: none. Every `pass` case has no xfail. All 33 `xfail BUG-NNN` cases have `xfail(strict=True)` whose reason names the bug.
- BUG IDs used (012, 013, 014, 015, 017, 018, 033, 034) all exist in `docs/testing/bugs.md`.
- xfail honesty (`--runxfail -rf`): exactly the 33 xfail cases fail, each on its "fails today on" assertion. AF-33/34 and CNT-08 fail with `ValueError: invalid literal for int()` at item.py:53. S-11 fails `0 == 1` at test_item.py:1193 after its precondition passes. L-14 page 1 is `['Zeta echo', 'Zeta delta']`. U-05 is `['kg','Kg','KG']`. S-25/26 start with `'delta'`. None fail on setup or import errors.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item.py -q -p no:cacheprovider --cov=app.dao.item --cov-branch --cov-report=term-missing
  app\dao\item.py   49 stmts  2 miss  12 branch  0 brpart  97%   Missing: 89, 116
  77 passed, 33 xfailed in 7.30s          (matches notes Result: 77 passed · 33 xfailed · 97%)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item.py -q -p no:cacheprovider --runxfail -rf
  33 failed, 77 passed in 3.94s           (failed set = exactly the 33 xfail cases)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item.py -q -p no:cacheprovider   (x5)
  77 passed, 33 xfailed  (all 5 runs)
PGOPTIONS='-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off'  (forced sequential scan)
  77 passed, 33 xfailed
PGOPTIONS='-c enable_seqscan=off'  (forced index scan; confirmed reaching the test DB: SHOW enable_seqscan = off)
  77 passed, 33 xfailed

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/item.py tests/unit/dao/test_item.py --json <scratch>/itemv/mut1.json
  Mutants: 66 · killed 51 · timeout 0 · survived 15 · tool score 77% (raw, before exclusions)
```

## Fix list (round 2)
1. **Case designer**: ITEM-S-25 and ITEM-S-26 become `xfail BUG-018 (non-strict)`, `Author: claude`. Add one strict statement-recorder card for `find_similar_by_name_in_workspace` asserting the emitted SQL's `ORDER BY` has the tie-breakers after `score DESC` (name case-insensitive, then `id`). It fails today and is the alarm when BUG-018 is fixed. (Finding 1)
2. **Executor**: implement the revised cards (change the two markers, add the recorder test), then re-run. (Finding 1)

---

# Round 1

> **Verdict:** NEEDS WORK
> Tests: 74 passed · 33 xfailed (reproduced ✅) · coverage 97% branch
> Mutation: 66 mutants · 48 killed · 18 survived → score 94.1% (48/51, after excluding 1 equivalent, 14 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests are mostly trustworthy. Every case is implemented. Setup matches the cases, assertions check exact values, nothing is mocked, and every write-free call is checked against the database. All 33 strict xfails fail today on the assertion their case names. Three runs gave the same result. What needs work: the search cases only ever match `sku`, `unit` and tag name at the **start** of the text. Because of that, anchoring those three `ILIKE` patterns as "starts with" goes unnoticed (3 surviving mutants), so the case designer must add mid-string cases. There is also one small wording question: S-01 expects "2-tuples" but the DAO returns SQLAlchemy `Row` objects. The describer and case designer should settle this rather than leave it to the executor's reading.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `_apply_item_catalog_filters` R9 (sku), line 49 | No case matches the search text in the middle or end of a `sku`. The only passing sku match is ITEM-AF-22 C, where sku `"ZETA-AB"` starts with the search `"zeta"`. R9 says "literal substring". | Mutant 46 (`f"%{term}%"` → `f"{term}%"` on `Item.sku`) survived | case designer |
| 2 | case-missing | `_apply_item_catalog_filters` R9 (unit), line 50 | Same problem for `unit`. The only unit search match is ITEM-AF-22 D, unit `"zetaroll"`, which also starts with the search. | Mutant 48 (leading `%` removed on `Item.unit`) survived | case designer |
| 3 | case-missing | `_apply_item_catalog_filters` R12, line 61 | Every passing tag-name match starts with the search text: AF-36 `"Galvanized"`/`GALV`, L-03 and CNT-04 `"Galvanized …"`/`galv`. No case matches a tag name in the middle (e.g. `"Hot-dip galvanized"`). | Mutant 51 (leading `%` removed on `ItemTag.name`) survived | case designer |
| 4 | changed expectation (minor) | ITEM-S-01 | The case says "returns a `list` of 2-tuples `(Item, float)`". The test checks `len(row) == 2`, `row[0]` is an `Item` and `row[1]` is a `float`. It never checks `isinstance(row, tuple)`, because the DAO returns `sqlalchemy.engine.Row`, which is not a `tuple` subclass. The executor used its own reading (logged in the notes) instead of recording a DISCREPANCY. The behavior callers rely on is still asserted. | test_item.py:1066–1069; notes "S-01 '2-tuples'" | describer (fill-gaps: state the return is a tuple-like `Row`), then case designer (reword S-01) |

No missing or weakened assertions, wrong setups, swallowed failures, extra mocks or dishonest xfails were found in the other 106 cases.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 7 | 89 | `return None` in `search_by_name_in_workspace` | dead | Spec "Not specified": dead code, to be removed (Q4) | — |
| 8 | 116 | `return None` in `get_active_items_in_workspace` | dead | Same (Q4) | — |
| 17 | 74 | default `skip` 0 → 1 | dead | `search_by_name_in_workspace` signature (Q4) | — |
| 18 | 74 | default `limit` 100 → 101 | dead | same | — |
| 19 | 102 | default `skip` 0 → 1 | dead | `get_active_items_in_workspace` signature (Q4) | — |
| 20 | 102 | default `limit` 100 → 101 | dead | same | — |
| 56 | 92 | `workspace_id ==` → `!=` | dead | `search_by_name_in_workspace` (Q4) | — |
| 57 | 94 | `is_active ==` → `!=` | dead | same | — |
| 62 | 94 | `True` → `False` | dead | same | — |
| 65 | 93 | leading `'%'` → `''` | dead | same | — |
| 66 | 93 | trailing `'%'` → `''` | dead | same | — |
| 58 | 119 | `workspace_id ==` → `!=` | dead | `get_active_items_in_workspace` (Q4) | — |
| 59 | 120 | `is_active ==` → `!=` | dead | same | — |
| 63 | 120 | `True` → `False` | dead | same | — |
| 39 | 210 | `score >= 0.35` → `score > 0.35` | equivalent | `similarity()` returns `real`. Widened to double, a `real` can never equal the double 0.35, because 0.35 is not a float4 value (the nearest is 0.3499999940…). So `>=` and `>` pick the same rows. Once BUG-034 is fixed (compare in `real`), this boundary becomes observable and ITEM-S-11 covers it. | — |
| 46 | 49 | leading `'%'` → `''` on `Item.sku` (prefix-only match) | case-missing | See Finding 1: no case has a sku that contains the search text somewhere other than at the start | case designer |
| 48 | 50 | leading `'%'` → `''` on `Item.unit` | case-missing | See Finding 2 | case designer |
| 51 | 61 | leading `'%'` → `''` on `ItemTag.name` | case-missing | See Finding 3 | case designer |

(The mutant id is the id in the mutation JSON. For lines 49, 50 and 61 the trailing-`%` twin was killed and the leading-`%` one survived. This is inferred from the test data: every sku, unit and tag-name match starts with the search text, so only a "starts with" pattern can survive.)

## Traceability
Cases 107 · test functions 101 (107 test items, because L-10/11, S-03/04, S-05..08 and S-21/22 are parametrized with one `pytest.param(id=…)` per case).
- Every case ID appears in exactly one test, and no test lacks a case ID.
- Marker mismatches: none. All 74 `pass` cases have no xfail. All 33 `xfail BUG-NNN` cases have `xfail(strict=True)` whose reason names the case's bug.
- BUG IDs used (012, 013, 014, 015, 017, 018, 033, 034) all exist in `docs/testing/bugs.md`.
- xfail honesty (`--runxfail`): all 33 fail on the "fails today on" assertion, and none fail on setup or import errors. AF-33/34 and CNT-08 fail with `ValueError: invalid literal for int()` at item.py:53. S-11 passes its similarity precondition and fails on `len(result) == 1` (0 rows). S-25/26 return a list starting with `"delta"`. L-14 page 1 is `['Zeta echo', 'Zeta delta']`. The U-cases return the spellings exactly as stored.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item.py -q -p no:cacheprovider --cov=app.dao.item --cov-branch --cov-report=term-missing
  app\dao\item.py   49 stmts  2 miss  12 branch  0 brpart  97%   Missing: 89, 116
  74 passed, 33 xfailed in 5.92s          (matches notes: 74 passed · 33 xfailed · 97%)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item.py -q -p no:cacheprovider --runxfail -rf
  33 failed, 74 passed in 3.30s           (failed set = exactly the 33 xfail cases)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item.py -q -p no:cacheprovider   (x2, flakiness)
  74 passed, 33 xfailed in 3.30s
  74 passed, 33 xfailed in 3.25s

Mutation: results from the pre-run of the unchanged tool
  (.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/item.py tests/unit/dao/test_item.py --json <scratch>/mut_item.json)
  66 mutants · 48 killed · 18 survived · tool score 72.7% (raw, before exclusions)
```
