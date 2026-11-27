# Verification — `app/managers/delivery_method_manager.py`

> **Current verdict: PASS** (round 2, 2026-11-04, cases revision 2, 91 cases). Narrow round, see "Round 2" at the end. The block below is round 1.

> **Round 1 verdict:** NEEDS WORK (case designer only; the tests are faithful)
> Tests: 61 passed · 29 xfailed (23 strict, 6 non-strict) (reproduced ✅) · coverage 100% branch (63 statements, 26 branches)
> Mutation: 61 mutants · 59 killed · 2 survived → score 100% (59/59, after excluding 2 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 1

## Summary
The tests can be trusted. Every one of the 90 cards has exactly one test. Every marker matches its Expect line. Each xfail fails today on the Then line its card names. The runs reproduce the notes and stayed the same over 4 plain runs and 2 forced query plans. Mutation testing kills every non-equivalent mutant. The 2 survivors are the same 2 equivalent mutants as in `department_manager`.

The design does not fully follow designer step 1b, so the verdict is NEEDS WORK. Both findings go to the case designer:
- **DMM-S-06** names one chosen row of a page on an unordered query.
- **BUG-1700** (non-strict DMM-N-13) has no strict alarm on the `_check_name_exists` query.

The executor and the describer have nothing to fix.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | design (step 1b: a card names one chosen row of an unordered page) | DMM-S-06 | The card expects `ids(result) == [B.id]` from `skip=1` over 2 live rows. The query has no `ORDER BY`. Which live row comes second depends on physical order, unless BUG-1704 is also fixed. Once BUG-1703 alone is fixed, the result is `[A.id]` or `[B.id]` depending on row order. The card is filed under BUG-1703 only, so it can XFAIL or XPASS at random for a reason its marker does not name. | Cases L929–931: `Then 1. returns: ids(result) == [B.id]`. Source L132–134 → base `get_by_workspace`, which has no ORDER BY (spec Branch map L269). | **case designer**: use a page-size and set check, as step 1b asks, e.g. `len(result) == 1` and `set(ids(result)) <= {A.id, B.id}`. This still fails today in the usual order, because the deleted rows come first and both live rows are returned. |
| 2 | design (step 1b: the unordered query behind a non-strict card has no strict alarm) | DMM-N-13 / `_check_name_exists` L189 | N-13 (BUG-1700, non-strict) rests on physical row order. The only strict statement recorders are S-22 (ORDER BY) and S-23 (`is_deleted` in WHERE), and both record the `search_delivery_methods` call. Nothing records the statement `_check_name_exists` sends. A fix of BUG-1700 would show only as a non-strict XPASS, which fails nothing. The cases file says so itself ("BUG-1700 … has no order-free alarm"), and so does notes L45. | Cases Reviewer summary L12. The coverage matrix row `_check_name_exists` R5 lists only N-12 (pass) and N-13 (non-strict). | **case designer**: add one strict `sql_log` card (Author: claude) on `M._check_name_exists(db, workspace_id=W1.id, name="Courier")`. It should assert that the uniqueness read is not a capped scan: for example, no `delivery_methods` statement has `LIMIT` unless its WHERE compares `name`. It fails today on the `LIMIT 100` statement. Choose the wording so that an EXISTS or `LIMIT 1` fix on the name passes. |

### Step 1b check on the non-strict cards (all six)
| Card | Assertion | Names one chosen row of an unordered page? | Strict alarm for its query |
|---|---|---|---|
| S-05 | `sorted(ids) == [A, B]` (set, limit 2 over exactly 2 live rows) | no | S-23 (BUG-1703) |
| S-06 | `ids == [B]` after `skip=1` | **yes** (Finding 1) | S-23 (BUG-1703) |
| S-07 | `ids == [X]` (X is the only name that matches "our") | no: the whole match set | S-23 (BUG-1703) |
| S-20 | full order of 5 rows | order card (R3), allowed by "Missing sort order" | S-22 (BUG-1704) |
| S-21 | `names == ["Charlie", "delta"]` | order card (R3), allowed by "Missing sort order" | S-22 (BUG-1704) |
| N-13 | `result is True` (a boolean, not a row) | no | **none** (Finding 2) |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 20 | 83:11 | `name and name != current` → `or` | equivalent | The mutant differs only when `name` is `None`, `""` or the current name. For `None` the extra `_check_name_exists(name=None)` is always False, because `name` is NOT NULL. `""` is a BUG-1702 input that the intended schema refuses. For the current name, the method excludes itself, so the check could be True only if another live row had the identical name. The Conventions and the spec invariant forbid that state. The mutant runs an extra query but gives the same results everywhere. This is the same argument as department #20. | — |
| 41 | 93:68 | `exclude_unset=True → False` | equivalent | Column 68 is `exclude_unset`; `exclude_none` is at column 87 and was killed. `DeliveryMethodUpdate` has one field, `name: str \| None = None`. When it is unset it dumps as `None`, and `exclude_none=True` still drops it, so the dict is the same. | — |

## Traceability
- Cases 90 · tests 90 (90 functions, none parametrized) · unmatched: none · duplicates: none · tests without a card: none. Checked with my own AST script on the case ID in each docstring's first line.
- Markers: the 61 `pass` cards have no xfail. The 23 strict cards have `xfail(strict=True)`. The 6 `(non-strict)` cards have `strict=False`, and each reason names its BUG. Every reason names every BUG ID on its Expect line. BUG-1219, 1523 and 1700…1705 all exist in `docs/testing/bugs.md`.
- Mocks: only `app.dao.delivery_method.utcnow` (spec Externals, autouse) and `race` (`patch.object(DeliveryMethodManager, "_check_name_exists", return_value=False)`). `race` is used only by C-12, C-13 and U-21, as the Race-simulations convention lists. The `db.commit` spy (`Mock(wraps=…)`) appears only in C-14, U-22 and D-05, per the "rolled back" convention. The session and the DAOs are not mocked.
- Fidelity: I read every test against its card's Given, When and Then lines, and each Then line is asserted in order under its `# Then N` comment. I found no missing, weakened or changed assertions, no wrong setup, no write check that is only in memory (writes are re-read after `expire_all()`), and no swallowed exceptions. `unchanged(X)` compares every table column.
- xfail honesty (`--runxfail --tb=line`, failures mapped to `# Then N` by my own script): each xfail fails on the line its card names. That is `DID NOT RAISE` in Then 1 for C-05/06/07/08/12/13, U-10/18/19/21 and G-06; an untrimmed name in Then 1 for C-10 and U-17; `updated_by` in Then 2 for U-14/15/16; `TypeError` for G-07 (call line, as its card says) and G-08 (inside the Then 1 block); `assert False` in Then 2 for S-22 and S-23; `False is True` for N-06/07/08/13; and today's row order in Then 1 for S-05/06/07/20/21. The failed set equals the 29 xfail cards.

## Commands run
```
COVERAGE_FILE=<scratch>/.cov_delivery_method .venv/Scripts/python.exe -m pytest tests/unit/managers/test_delivery_method_manager.py -q -p no:cacheprovider --cov=app.managers.delivery_method_manager --cov-branch --cov-report=term-missing
  app\managers\delivery_method_manager.py      63      0     26      0   100%
  61 passed, 29 xfailed, 15 warnings in 6.69s
... --runxfail -rf                                         29 failed, 61 passed (failed set == xfail set)
... --runxfail --tb=line  + <scratch>/thenline.py          each failure in its card's Then block (above)
... (plain, x2)                                            61 passed, 29 xfailed · 61 passed, 29 xfailed
PGOPTIONS="-c enable_seqscan=off" ... -rX                  61 passed, 29 xfailed (no XPASS)
PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off" ... -rX   61 passed, 29 xfailed (no XPASS)
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_delivery_method_manager.py   All checks passed!
.venv/Scripts/python.exe -I <scratch>/trace_v.py <cases> <test> <runxfail> docs/testing/bugs.md
  cards 90 tests 90 pass 61 xfail 29 (strict 23) · problems: 0
COVERAGE_FILE=<scratch>/.cov_mut_dm .venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/delivery_method_manager.py tests/unit/managers/test_delivery_method_manager.py --json <scratch>/mut_dm.json
  Mutants: 61 · killed 59 · timeout 0 · survived 2 · score 97%   (#20 L83:11, #41 L93:68)
```
`<scratch>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr5v2`. The results match the notes: 61 passed · 29 xfailed (23 strict, 6 non-strict) · 100% branch. No flaky tests.

## Round 2 — 2026-11-04 (cases revision 2, narrow)

> **Verdict:** PASS
> Tests: 61 passed · 30 xfailed (24 strict, 6 non-strict) (reproduced ✅) · coverage 100% branch (63 statements, 26 branches)
> Mutation: not re-run, as the coordinator asked. Round 1 stands: 61 mutants · 59 killed · 2 equivalent, on the same source. This round changed one non-strict xfail and added one strict xfail, and mutation runs skip xfail tests.
> Source commit: e48a092 · Cases revision: 2

### Summary
Both round 1 findings are closed. I checked only DMM-S-06 and the new DMM-N-17 against their cards. The other 89 tests were covered only by the mechanical checks below.

| Round 1 finding | Now |
|---|---|
| 1 — S-06 names one chosen row of an unordered page | Closed. The card now checks `len(result) == 1` (Then 1) and `set(ids(result)) <= {A.id, B.id}` (Then 2), and the test asserts exactly these, in that order. It is still non-strict BUG-1703. Today it fails on Then 1 (`assert 2 == 1`), as its card says. |
| 2 — no strict alarm on the `_check_name_exists` query (BUG-1700) | Closed by DMM-N-17 (strict, BUG-1700). Its Given, When and Then 1–3 match the card word for word. Under `--runxfail` it fails on Then 3 (`assert not True`: the `LIMIT 100` statement has no `name` in its WHERE). |

### N-17 against a fixed `_check_name_exists`
I wrote my own scratch plugin, `<scratch>/fixname_v.py` (nothing under `app/` changed). It replaces `_check_name_exists` with the two shapes the card allows:
- `FIXSHAPE=scan`: an uncapped SELECT of the workspace's rows, no LIMIT, normalised compare in Python.
- `FIXSHAPE=exists`: `SELECT id … WHERE workspace_id, NOT is_deleted, lower(btrim(name)) = … LIMIT 1`.

With either shape, `--runxfail -k _n_` gives 17 passed, so N-17 passes on Then 1, 2 and 3. With the markers on, N-17 shows `XPASS(strict)` and fails the run, so it works as the alarm. N-13 (non-strict) shows XPASS, and N-06/07/08 show XPASS(strict) for BUG-1701, which this plugin also fixes.

### Not done
No full mutation run. I did not re-read the 89 unchanged tests.

### Commands run
```
... test_delivery_method_manager.py --cov=app.managers.delivery_method_manager --cov-branch   61 passed, 30 xfailed; 100% (63/26)
... --runxfail -rf                                   30 failed, 61 passed (failed set == xfail set)
... --runxfail --tb=line + <scratch>/thenline.py     S-06 Then 1 `assert 2 == 1`; N-17 Then 3 `assert not True`
... (plain, x3, -rX)                                 61 passed, 30 xfailed ×3, no XPASS
FIXSHAPE=scan|exists PYTHONPATH=<scratch> ... -p fixname_v --runxfail -k _n_    17 passed (each shape)
FIXSHAPE=scan|exists ... -p fixname_v -k _n_ -rX     N-17 XPASS(strict) → failed (each shape)
<scratch>/trace_v.py                                 cards 91 tests 91 pass 61 xfail 30 (strict 24) · problems: 0
ruff check                                           All checks passed!
```
