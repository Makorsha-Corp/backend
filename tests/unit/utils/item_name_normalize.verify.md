# Verification — `app/utils/item_name_normalize.py`

> **Verdict:** PASS
> Tests: 74 passed · 22 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 13 mutants · 13 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 4 · Notes revision: 3 · Verify round: 3 (batch re-run)

## Summary
These tests can be trusted. All 73 case IDs map one-to-one to 73 test functions, which run as 96 items because INN-N-69 and INN-N-70 are parametrized over their listed inputs. Every xfail is `strict=True`, and its reason names exactly the BUG IDs in the case's Expect column. With `--runxfail`, each of the 22 xfail tests fails on the assertion its case names under "fails today on", and none fails on a setup or import error. Every assertion checks the exact value from its case. The file has no mocks and no try/except, and it is pure ASCII (0 non-ASCII bytes), so the invisible code points cannot drift. The runs reproduce the notes' Result line and gave the same outcome all 3 times. All 13 mutants are killed. Nothing needs to change.

## Findings
None.

Informational only (no stage action required):
- The module docstring in the test file says "cases.md (revision 3)", but the cases file is at revision 4. According to the cases file and notes rev 3, revision 4 changed no case, so the tests are still accurate.
- BUG-180..BUG-183 are not in `docs/testing/bugs.md` yet. They are staged in `tests/unit/utils/item_name_normalize.bugs-staging.md`, which has all four IDs with titles that match the test reason strings, and they will be merged into the shared register later by the batch merge agent (batch-mode rule). This is not counted as a traceability failure: after the merge, every BUG ID used will exist in `bugs.md` (best-practice default, delegated by reviewer).
- The mutation tool's operator set is small: 13 mutants, all constant, return and condition swaps, with no regex-quantifier mutations. The `{1,4}` boundary is still pinned by explicit cases: INN-N-25 `"5 pack"` → `"5pack"` and INN-N-26 `"5 packs"` → `"5 packs"`. INN-N-29 covers `\b`, and INN-N-38/39 cover Unicode `\d`.

## Surviving mutants
None. All 13 killed:

| # | Line | Mutation | Status |
|---|---|---|---|
| 1 | 6 | `3 -> 4` (MIN_SIMILAR_NAME_LENGTH) | killed |
| 2 | 20 | negate if-condition | killed |
| 3 | 28 | `return None` | killed |
| 4 | 10 | glue regex → `''` | killed |
| 5 | 20 | drop `not` | killed |
| 6 | 21 | `return None` | killed |
| 7 | 24 | `'\s+' -> ''` | killed |
| 8 | 24 | `' ' -> ''` | killed |
| 9 | 25 | `'\1\2' -> ''` | killed |
| 10 | 26 | `'[^\w\s]' -> ''` | killed |
| 11 | 26 | `' ' -> ''` | killed |
| 12 | 27 | `'\s+' -> ''` | killed |
| 13 | 27 | `' ' -> ''` | killed |

## Traceability
Cases: 73 (51 pass, 22 xfail). Tests: 73 functions, 96 items. Unmatched: none in either direction; no duplicates. Marker mismatches: none. An AST script compared each test's `xfail` decorator against the case's Expect column. Every xfail case has `strict=True`, and the set of BUG IDs in its reason equals the case's set. That includes INN-N-47 `BUG-182; BUG-183` and INN-N-58 `BUG-180; BUG-182`. No pass-case carries a marker.

Fidelity: every case was read against its test. INN-N-14 and INN-N-16 assert the extra whitespace-shape checks from their cases. INN-N-40 uses `startswith` / `not in`, exactly as its case specifies. INN-N-56 asserts both exact values and the pairwise inequalities. INN-N-60 and INN-N-07 assert both the exact value and the equality with the other spelling. INN-N-71 asserts idempotence for all three inputs plus `f("Bolt 10-mm") == "bolt 10mm"`. INN-N-69 and INN-N-70 have one param per listed input, with ids naming x. No extra mocks (the spec says none), and no swallowed failures.

Xfail honesty (`--runxfail --tb`), sample: INN-N-07 `cafe` vs `café`, INN-N-08 `'ｂｏｌｔ' == 'bolt'`, INN-N-42/43/44 `'bolt 10 mm'`, INN-N-46 `'size 5 pack'`, INN-N-47 `'bolt 10_mm'`, INN-N-56 fails on `f(CHUL)` `'চ ল'`, INN-N-58 `'5kq' == '5 kq́'`, INN-N-60 `'র য ব'`, INN-N-63 `'screw_driver'`, INN-N-64 `'__'`, INN-N-71 `not idempotent for 'Bolt 10-mm'`. All 22 match their cases' "fails today on".

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_item_name_normalize.py -q -p no:cacheprovider --cov=app.utils.item_name_normalize --cov-branch --cov-report=term-missing
  app\utils\item_name_normalize.py  14 0 2 0 100%
  74 passed, 22 xfailed in 0.81s
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_item_name_normalize.py -q -p no:cacheprovider --runxfail -rf
  22 failed, 74 passed in 0.43s   (the 22 failures = exactly the 22 xfail cases)
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_item_name_normalize.py -q -p no:cacheprovider   (x2 more)
  74 passed, 22 xfailed in 0.44s
  74 passed, 22 xfailed in 0.44s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/item_name_normalize.py tests/unit/utils/test_item_name_normalize.py --timeout 180 --json %TEMP%/claude/imn/mut.json
  Mutants: 13 · killed 13 · timeout 0 · survived 0 · score 100%
LC_ALL=C grep -c '[^ -~]' tests/unit/utils/test_item_name_normalize.py
  0
```
