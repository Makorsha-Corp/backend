# Execution notes — `app/utils/item_name_normalize.py`

> Cases: `tests/unit/utils/item_name_normalize.cases.md` (revision 4) · Tests: `tests/unit/utils/test_item_name_normalize.py` · Source commit: e48a092
> Result: 74 passed · 22 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_item_name_normalize.py -q -p no:cacheprovider --cov=app.utils.item_name_normalize --cov-branch --cov-report=term-missing`

## How the tests are built
- **No database, no mocks.** Pure function (spec: "Externals to mock: none"); no test takes the `db` fixture.
- **Conventions → helpers** (top of the test file):
  - `f(x)` → module alias `f = normalize_item_name`.
  - "returns exactly S" → `assert_exact(result, S)`: `result == S` then `type(result) is str`.
  - Code points → module constants `CHAL`, `CHUL`, `CHIL`, `CHOL`, `RAB_ZWJ`, `RAB`, `PHRASE`, `KEJI_5`, `CAFE_PRE`, `CAFE_DEC`, `FW_BOLT`, `FW_10MM`, `X_SQUARED`, `FI_LIGATURE_FILE`, `NBSP`, `SOFT_HYPHEN`, `ZWNJ`, `ZWSP`, `ENCLOSING_CIRCLE`, `Q_ACUTE`, all written with explicit `\u` escapes. Since notes rev 2 the whole test source is pure ASCII: every non-ASCII character, including inline literals and docstrings (the em dash is `—`), is a `\u` escape. Check with `LC_ALL=C grep -c '[^ -~]' tests/unit/utils/test_item_name_normalize.py` (must print 0). Do not paste raw Unicode back in: precomposed vs decomposed `é`, NBSP, ZWSP, ZWNJ, ZWJ, soft hyphen and U+0301 are invisible or look identical, and an editor NFC pass could silently turn `CAFE_DEC` into `CAFE_PRE`.
  - Bug titles → `BUG_180`..`BUG_183` reason strings (titles from `item_name_normalize.bugs-staging.md`). Multi-bug cases (INN-N-47, INN-N-58) join both reasons with `"; "`.
- **Test count vs case count:** 73 cases → 96 test items. INN-N-69 (16 inputs) and INN-N-70 (9 inputs) are parametrized, one param per listed input, with ids `INN-N-69[<ascii repr of x>]` / `INN-N-70[<constant name>]`, as the case asks ("the subtest/param id names x"). So 51 pass-cases = 49 plain tests + 25 params = 74 passed. INN-N-68 (four variants) and INN-N-71 (xfail, three inputs plus an extra assertion) loop inside one test; INN-N-71 names the failing input in the assertion message.
- **Xfail honesty check:** ran with `--runxfail`; every one of the 22 xfail tests fails on the assertion named in "fails today on" (e.g. INN-N-58 `'5kq' == '5 kq́'`, INN-N-56 fails on `f(CHUL)`, INN-N-60 on `f(RAB_ZWJ)`, INN-N-71 on the idempotence of `"Bolt 10-mm"`).
- Stability: 3 runs, identical outcome (74 passed, 22 xfailed).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (14 statements, 2 branches).

(The coverage report also lists `app/utils/attachment_allowlist.py` at 100%; that module is imported through the app package during collection and is unrelated to this file.)

## Factories added
None. No DB models involved; `tests/unit/factories.py` not touched (batch mode). Nothing worth promoting — the code-point constants are specific to this module.

## Revision history
- **Rev 1**: first implementation of cases revision 3 (74 passed, 22 xfailed, 100% branch).
- **Rev 2**: fixed verify.md finding 1 (`test-weakness`, convention violation). The code-point constants (`CHAL` … `Q_ACUTE`) and the inline literals in INN-N-05, 06, 07, 16, 38, 39, 40, 41, 55, 56 and 60 were raw UTF-8. Every non-ASCII character in the file is now a `\u` escape, and the notes' false "pure ASCII except in docstrings" claim is corrected. The conversion was mechanical and the module AST is identical before and after, so every string value (inputs, expected values, docstrings) is unchanged. The cases file is unchanged (still revision 3); no test was added, removed or changed in behavior. Re-run: 74 passed and 22 xfailed, identical across 3 runs; `--runxfail` gives 22 failed (exactly the 22 xfail cases); branch coverage 100%.
- **Rev 3**: cases revision 4 (batch re-run; no case added, removed, renumbered or changed). All tests kept unchanged. Re-checked: 73 test functions map one-to-one to the 73 case IDs, the file is still pure ASCII (0 non-ASCII bytes), 3 runs give 74 passed and 22 xfailed each time, `--runxfail` gives 22 failed (exactly the xfail cases), and branch coverage is 100%. No discrepancies; no new decisions needed.

## Notes for maintainers
- **When BUG-181 (NFKC) ships:** INN-N-07..11 XPASS → remove their markers. INN-N-70 stays green (its inputs were chosen to be idempotent before and after every fix).
- **When BUG-180 (combining marks / joiners) ships:** INN-N-41, 55, 56, 57, 59, 60, 61, 62 XPASS → remove markers. INN-N-58 stays xfail until BUG-182 also ships (with only BUG-180 fixed it returns `"5kq́"`).
- **When BUG-182 (glue after punctuation) ships:** INN-N-42, 43, 44, 46, 71 XPASS → remove markers; INN-N-47 needs BUG-183 too; INN-N-58 needs BUG-180 too.
- **When BUG-183 (underscore) ships:** INN-N-63, 64 XPASS; INN-N-47 needs BUG-182 too.
- Every fix requires the `items.name_normalized` backfill (deferred to the migration that ships the fix — see the cases file's Deferred table).
- INN-N-40 and INN-N-54 are bug-independent regression guards; they must stay green through the BUG-180 fix.
- A legacy test `tests/test_item_name_normalize.py` exists outside `tests/unit/`; it asserts today's behavior and will need updating when the bugs are fixed.
