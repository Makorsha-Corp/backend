# Verification — `app/dao/inventory_ledger.py`

> **Verdict:** PASS
> Tests: 150 passed · 20 xfailed (reproduced ✅) · coverage 97% branch (52 statements, 2 missed: lines 48, 109 — dead code; 20 branches, 0 missed)
> Mutation: 65 mutants · 56 killed · 9 survived → score 100% (after excluding 0 equivalent, 6 dead, 3 bug-path)
> Source commit: e48a092 · Cases revision: none stated (READY, 170 cases)

## Summary
These tests can be trusted. All 170 tests were read against their cards line by line (every Given row and column value, the When call and each argument, every numbered Then line); nothing was sampled. As a second, independent check a script rebuilt the expected test body from each of the 161 local-model cards (rows in card order, keywords in card order, a variable only where the card uses it later, snapshots before the call, one assertion block per `# Then N`) and compared it with the test: 0 differences in 161 bodies, 161 docstrings and 20 markers.

- **Local-model tests (161): functional findings in 0 / 161 tests · cosmetic findings in 22 / 161 tests** (21 test names cut at 70 characters by the tool, 1 argument list in a non-standard order).
- **Claude-written tests (9): functional findings in 0 / 9 tests · cosmetic findings in 1 / 9 tests** (one name cut at 70 characters).
- All 20 xfail tests fail, under `--runxfail`, on the line their card names. Three consecutive runs gave the same outcome (no flaky test).
- Every surviving mutant is in dead code (6) or on the line that only the BUG-655 xfail tests reach (3).
- Nothing must change. The cosmetic findings are optional and do not affect what is checked; they are the reason for no change of verdict.
- Open item carried over from the cases file, not a finding of this run: spec gap 1 (`get_by_performer` R6, last sentence — "the performer's own profile state is not consulted" has no card because the spec does not name the column). It stays with the describer.

Limits of this verdict: the nine `calculate_balance` cards for a bucket with history (LED-BAL-08 … BAL-16) fail today inside the call, so their assertions have never run against working code. Their text matches the cards exactly, but they get their first real exercise when BUG-655 is fixed.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Naming (local) — COSMETIC | LED-W-01, W-02, W-05, W-06, W-07, W-22, TT-16, TT-23, TT-31, DR-02, DR-22, DR-30, PF-06, PF-12, PF-20, BAL-07, BAL-13, LE-02, LE-08, EX-03, EX-13 (21 tests) | The test name is cut at 70 characters and no longer carries the whole title; two are cut inside a word. The docstring carries the full ID and title, so traceability is intact. Caused by the tool's `normalize`, not by the model. | `test_led_dr_02__…_keep_only_the_middle_e`, `test_led_bal_13__…_the_greatest_id_gives_th` | optional — tool (`tests/unit/_tools/local_coder.py`, cut at a word boundary) |
| 2 | Naming (claude) — COSMETIC | LED-PF-01 | Same cut in the hand-written exemplar: the name ends `…_item_and_transaction`, the title ends "… and transaction type". | `test_led_pf_01__returns_that_user_s_entries_of_every_type_factory_item_and_transaction` | optional — executor |
| 3 | Style (local) — COSMETIC | LED-BAL-01 | Argument list is `(db, f1, i1, w1)`; every other test lists workspaces first (`db, w1, …, f1, …, i1`). Left over from the one retry (fixtures added after the "used but not requested" rejection). No effect: all three fixtures are requested and used. | `def test_led_bal_01__…(db, f1, i1, w1):` | optional — executor |

No FUNCTIONAL finding. Checked for and not found, in all 161 local tests: a missing or extra Given row, a wrong or missing column value (workspace, factory, item, type, transaction type, performer, source, quantity, price, `id HIGH_ID`), a wrong `performed_at`, rows in another order than the card, a changed or dropped call argument (including `None`, `0`, `-1`, the trailing space of LED-TT-04, the microsecond bounds of LED-DR-02), a skipped Then line, an assertion weaker than the card (`in`, `len` only, `sorted` where order is required — the only `in [...]` is LED-LE-08, where the card asks for it; the only `sorted(...)` are the four tie cards W-22, TT-23, DR-22, PF-12, as designed), a wrong expression under a `# Then N`, expected values read from a row instead of the card's literal, a snapshot taken at the wrong moment, `try/except`, a broad `pytest.raises`, a mock or patch, an unused or unrequested fixture.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 5 | 48 | `return …` → `return None` | dead | Body of the `get_by_id_and_workspace` override; spec "Not specified": dead code, to be removed (Q2). | — |
| 48 | 49 | `==` → `!=` (`id`) | dead | Same override (Q2). | — |
| 49 | 50 | `==` → `!=` (`workspace_id`) | dead | Same override (Q2). | — |
| 14 | 109 | `return …` → `return None` | dead | Body of `get_by_order`; spec "Not specified": dead code, to be removed (Q1). | — |
| 54 | 112 | `==` → `!=` (`workspace_id`) | dead | `get_by_order` (Q1). | — |
| 55 | 113 | `==` → `!=` (`order_id`) | dead | `get_by_order` (Q1). | — |
| 28 | 157 | `return (…)` → `return None` | bug-path | Line 157 runs only when the bucket has an entry; it raises `AttributeError` today (BUG-655). Only LED-BAL-08 … BAL-16 reach it, all xfail and excluded from the run. | — (resolves with BUG-655) |
| 46 | 157 | `or` → `and` | bug-path | Same line; the NULL-price fallback is asserted by LED-BAL-09 (xfail BUG-655). | — (resolves with BUG-655) |
| 50 | 157 | `'0.00'` → `''` | bug-path | Same line and fallback; LED-BAL-09 (xfail BUG-655). | — (resolves with BUG-655) |

Killed: all 56 mutants in specified, reachable code — every filter comparison of the four lists, the three optional-filter `if`s of each list, both date bounds (`>=`, `<=`), the `skip` / `limit` defaults of all four lists, the four bucket keys of `calculate_balance` and `get_latest_entry`, the three keys and the `is not None` of `exists_for_source`, and the empty-bucket result `(0, Decimal('0.00'))`.
Note on the tool, not a finding: its operators do not mutate `order_by(desc(...))`, `.offset()` or `.limit()` calls. Ordering and paging are nevertheless asserted with exact id lists in every list callable (e.g. LED-W-01, W-23 … W-27, TT-01, DR-03, PF-10, LE-02/04/05).

## Traceability
cases 170 · tests 170 · unmatched: none (each case ID appears in exactly one test name and docstring; no test without a case ID) · marker mismatches: none.
- 150 `Expect: pass` cards → no marker. 20 `Expect: xfail` cards → one `xfail(strict=True)` each, reason naming exactly the card's BUG IDs (LED-BAL-13 names both BUG-641 and BUG-655).
- BUG IDs used: BUG-640, BUG-641, BUG-655, BUG-664, BUG-885 — all present in `docs/testing/bugs.md`.
- 161 tests carry `# [local-coder] <ID>` with the ID of the test below it; the same 161 IDs are in `inventory_ledger.local-run.json` (161 accepted, 1 retry: LED-BAL-01). The 9 others are the exemplars LED-PF-01, W-04, W-33, BAL-12 and the `Author: claude` cards LED-W-28, W-29, TT-26, DR-25, PF-15.
- Local tests read per callable: `get_by_workspace` 35 · `get_by_transaction_type` 30 · `get_by_date_range` 29 · `get_by_performer` 18 · `calculate_balance` 15 · `get_latest_entry` 18 · `exists_for_source` 16.
- xfail honesty (`--runxfail -rf`, 20 failed): BUG-885 cards LED-W-15, W-18, TT-20, TT-21, DR-19, DR-20 fail in Then 1 (`assert result == []`, two entries returned). BUG-640 cards LED-W-21, TT-22, DR-21, PF-11 fail in Then 2 (`ids(result) == [ec.id, ea.id, eb.id]`; returned `[EB, EC, EA]`, and `[EA, EC, EB]` for DR-21 — the two orders the cards predict). LED-LE-06 fails in Then 1 (`result.id == ec.id`, EB returned). LED-BAL-08 … BAL-16 fail in the When call with `AttributeError: 'InventoryLedger' object has no attribute 'value_after'`, as their "Fails today on" lines say. None fails on a setup or import error.
- Scaffold (hand-written) checked against Conventions: the eight standing rows, the default entry, X9, T1 … T5, MISSING, HIGH_ID (computed at insert time), `mk_101`, and the reading helpers `reread`, `snap`, `written`, `count_rows`, `ids` (keeps order). No deviation. Nothing is mocked or patched.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory_ledger.py -q -p no:cacheprovider --cov=app.dao.inventory_ledger --cov-branch --cov-report=term-missing
  app\dao\inventory_ledger.py      52      2     20      0    97%   48, 109
  150 passed, 20 xfailed in 9.32s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory_ledger.py -q -p no:cacheprovider --runxfail -rf
  20 failed, 150 passed in 4.84s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory_ledger.py -q -p no:cacheprovider      (twice more)
  150 passed, 20 xfailed in 4.73s
  150 passed, 20 xfailed in 4.75s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/inventory_ledger.py tests/unit/dao/test_inventory_ledger.py --json <scratch>/mut.json      (run alone, before pytest)
  Mutants: 65 · killed 56 · timeout 0 · survived 9 · score 86%
```
Results match the Result line of the notes (150 passed · 20 xfailed · coverage 97%, 2 statements missed, 0 branches missed).

## Local-coder patterns
No recurring functional mistake: 0 of 161 local-written tests deviate from their card in a row, a value, an argument or an assertion.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| Test name cut at 70 characters (twice inside a word) | 21 | LED-DR-02, LED-BAL-13, LED-W-02 | cosmetic — tool, not model | Tool: let `normalize` cut at the last `_` before the limit, or raise the limit. |
| Card without Given rows: fixtures named only in the When call were not requested on the first attempt; after the retry they were appended in a non-standard order | 1 | LED-BAL-01 | cosmetic (the tool's "fixture used but not requested" check caught the real error) | Helper-sheet line: "A card that says 'No ledger entries exist.' still needs every fixture its When call names (`w1`, `f1`, `i1`)." Optionally let the tool sort the argument list. |
| Blank line between docstring and the call when the card has no Given row | 3 | LED-BAL-01, LED-LE-01, LED-EX-04 | style only, not counted as a finding | Nothing needed. |

Observations for `docs/testing/local-coder-improvements.md`:
- What worked here and is worth keeping: keyword-only `mk_entry` (no positional argument can be wrong), `mk_x9()` without arguments (the shorthand is never expanded by hand), `HIGH_ID` as a constant the model copies, Then lines written as ready expressions, and "expected values are the card's literals".
- The accepting tool's known blind spots (wrong value that still gives the designed outcome, weaker assertion, wrong expression under the right `# Then N`, dropped qualifier, row order) can be closed mechanically for cards in this vocabulary: build the expected body from the card (Given rows → builder calls in card order, When → call, Then → assertion per line) and compare it with the model's body. The verifier did this by script for all 161 cards and found 0 differences; as a check in the tool it would reject such a test at acceptance time instead of at stage 5.
- This module is read-only and its cards are highly regular (one builder, seven call shapes, about a dozen Then forms). The clean result should not be assumed for modules with writes, mocks or free-form Then lines.
