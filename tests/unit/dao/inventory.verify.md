# Verification — `app/dao/inventory.py`

> **Verdict:** PASS
> Tests: 158 passed · 32 xfailed · 1 xpassed (reproduced ✅) · coverage 91% branch
> Mutation: 96 mutants · 86 killed · 10 survived → score 100% (after excluding 2 equivalent, 8 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: not numbered (READY, 191 cases)
> Previous round: round 1 — NEEDS WORK (2 functional + 9 cosmetic findings, all in local-written tests; same mutation result). This is the re-verification after "Fix round 1" in the notes; all 11 findings are fixed.

## Summary
The tests can be trusted: every mutant in specified code is killed, the runs reproduce the notes' Result line four times over, all 32 strict xfails fail on the assertion inside the Then line their card names, and nothing is mocked beyond what Conventions declare.
All 11 findings of round 1 are fixed, and the 11 changed tests were re-read in full against their cards: Given, When and every Then line are the card's, and nothing else in them changed.
No other test changed: compared with the previous round's dump of all 191 tests, 186 are textually identical (docstring aside) and the 5 that differ are five of the 11; compared with the local model's as-delivered file, every difference outside the 11 is the scripted clean-up (an unused `name = mk_…(…)` binding reduced to the bare call, unused arguments dropped).
**Local-written tests with at least one finding: 0 / 178** (round 1: 11 / 178 — functional 2, cosmetic 9).
**Claude-written tests with at least one finding: 0 / 13** (round 1: 0 / 13).
Judged, not findings: INV-ST-03 XPASSes as its card (`xfail BUG-719 (non-strict)`) and the spec's designer note anticipate, with the assertion unweakened; the 91% coverage gap is exactly the spec's dead code (Q3, Q4, Q5) plus the branch the Branch map calls unreachable.

## Findings
None.

Round-1 findings, re-checked:

| # (round 1) | Case | Was | Now (`test_inventory.py`) | Fixed |
|---|---|---|---|---|
| 1 | INV-ST-13 | S9 built in `f2` | line 2014: `mk_stock(i9, f9, workspace_id=w2.id)`, `f9` added to the arguments; the other three Given rows, the When call and the four Then assertions unchanged and equal to the card | yes |
| 2 | INV-EN-13 | Then 6 `== before_count + 1` | `# Then 6` → `assert count_rows(db, Inventory) == 2`; the `before_count` snapshot is gone; `before_s1 = snap(db, s1)` is still taken before the call; Then 1–5 unchanged | yes |
| 3 | INV-CNT-11 | slug copied from INV-ST-12 | `test_inv_cnt_11__filtering_by_a_soft_deleted_factory_counts_nothing` (the card title); body unchanged; still fails in Then 1 with `1 == 0` under `--runxfail` | yes |
| 4 | INV-FQ-40 | slug copied from INV-ST-12 | `test_inv_fq_40__listing_leaves_the_stock_row_of_a_soft_deleted_factory_untouched` (the card title); body unchanged | yes |
| 5 | INV-EN-17 | `# Given 1: …` and `# When` comments | both removed; the only comments left are `# Then 1..3`; code unchanged | yes |
| 6 | INV-FQ-24, FQ-25, FQ-26, FQ-34, L-06, ST-25 | docstring first line without full stop | all six end with a full stop; `<ID> — <title>.` and the `Rules:` line equal the card in all 191 tests (script) | yes (6 / 6) |

## Surviving mutants
Same ten as in round 1 (same mutant numbers, lines and mutations); classification re-checked against the source and the spec.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 10 | 153 | `return self.list_filtered(…)` → `return None` | dead | body of the `get_by_workspace` override — spec "Not specified", review Q3 (remove) | — |
| 22 | 318 | `return db_obj` → `return None` | dead | `soft_delete` — spec "Not specified", review Q4 (remove) | — |
| 24 | 31 | default `include_zero_qty=False` → `True` in `_filtered_query` | equivalent | the helper is internal and its only three callers (lines 74, 100, 121) pass `include_zero_qty` explicitly, so its own default is never used; the public defaults on lines 69 / 98 / 119 were mutated separately and killed | — |
| 33 | 150 | default `skip=0` → `1` | dead | signature of the `get_by_workspace` override (Q3) | — |
| 34 | 150 | default `limit=100` → `101` | dead | signature of the `get_by_workspace` override (Q3) | — |
| 40 | 312 | `is_active = False` → `True` | dead | `soft_delete` (Q4) | — |
| 41 | 313 | `is_deleted = True` → `False` | dead | `soft_delete` (Q4) | — |
| 69 | 158 | `include_zero_qty=True` → `False` | dead | inside the `get_by_workspace` override (Q3) | — |
| 73 | 306 | `inventory_type == …` → `!=` | dead | `get_by_item`'s `inventory_type` filter — dead parameter, review Q5 (remove) | — |
| 96 | 139 | `coalesce(sum(qty), 0)` → `coalesce(sum(qty), 1)` in the per-type query | equivalent | the query is grouped by `inventory_type`, so every group has at least one row, and `inventory.qty` is `nullable=False`: `sum(qty)` is never NULL and the fallback can never be used (the un-grouped fallbacks on lines 132 / 133 were mutated separately and killed) | — |

No `test-weakness`, `case-missing`, `spec-gap` or `bug-path` survivor.

## Traceability
cases 191 · tests 191 · unmatched: none (each case ID appears in exactly one test name and docstring; no test without a case ID; the 178 `# [local-coder] <ID>` comments all match the ID of the test below them) · marker mismatches: none.
- 158 `pass` cards → no marker. 32 `xfail BUG-NNN` cards → `xfail(strict=True)` whose reason names the BUG ID. 1 card `xfail BUG-719 (non-strict)` (INV-ST-03, Author: claude) → `xfail(strict=False, reason="BUG-719: …")`, as the card prescribes.
- BUG IDs used (BUG-664, BUG-701, BUG-702, BUG-719, BUG-880, BUG-881, BUG-882, BUG-883, BUG-884) all exist in `docs/testing/bugs.md`.
- `# Then N` comments: in every test exactly 1..K in order, K = the card's number of Then lines, and each block contains at least one `assert` / `pytest.raises`.
- Comments inside test bodies other than `# Then N`: none. `try` statements: none. Skips: none.
- Extra mocks: none. The only patches are `race_r9()` / `race_r10()` (INV-EN-22, EN-23, EN-24) and `commit_spy(db)` (INV-SY-16, EN-25, EN-26, R-05), both declared in the cases file's Conventions.
- Function names: every name starts with `test_<id>__`; the exemplar slug `factory_filter_soft_delete_and_scope` now occurs once (INV-ST-12, its own card).
- Observations, not findings: the tests are not in card order in the file; six slugs occur twice under different case IDs because the card titles themselves are identical (INV-GF-01…05 / INV-GA-01…05) or differ only in a trailing parenthesis (INV-L-04 / L-05).

Fidelity in this round:
- The 11 changed tests were read in full against their cards (see the table above): no missing, weakened or changed assertion, no wrong setup, snapshots before the call, stored values asserted on a re-read row.
- Proof that nothing else changed since round 1 (which read all 191 tests):
  - against the previous round's dump of all 191 tests (decorators, signature, body and comments; docstring excluded): 186 identical, 5 differ — INV-ST-13, INV-EN-13, INV-FQ-40, INV-CNT-11, INV-EN-17, each only in the lines the notes' Fix round 1 describes. Docstrings: the only differences from the as-delivered file are the six added full stops. The 9 `Author: claude` tests are among the 186 identical ones.
  - against the as-delivered file (182 tests: 178 local + 4 exemplars; AST-normalised bodies): 57 identical, 123 differ only by `name = mk_…(…)` → `mk_…(…)` where the name is never read in the as-delivered body (225 bindings; with INV-ST-13's four, the notes' 229), 2 differ otherwise (INV-ST-13, INV-EN-13 — the two functional fixes). No decorator changed; no argument that the as-delivered body uses was dropped; the only argument added anywhere is `f9` in INV-ST-13. All non-test top-level code (fixtures, builders, helpers) is identical to the as-delivered file; the only additions are the three declared helpers `race_r9`, `race_r10`, `commit_spy`.

Coverage against the spec: missing lines 153 (Q3), 306 with branch 305->306 (Q5), 311–318 (Q4) are the three dead-code items of the spec's "Not specified" section; partial branch 260->262 is the `False` side of `if existing.is_deleted:`, which the Branch map (row 260–261) states is "not reachable in a single session, no rule". No spec gap.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory.py -q -p no:cacheprovider --cov=app.dao.inventory --cov-branch --cov-report=term-missing
  app\dao\inventory.py     102     10     30      2    91%   153, 260->262, 306, 311-318
  158 passed, 32 xfailed, 1 xpassed in 10.57s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory.py -q -p no:cacheprovider --runxfail -rf
  32 failed, 159 passed in 5.23s
  (the 32 failures are exactly the 32 strict xfail tests; mapped by script from the traceback line to the enclosing
   `# Then N`: every one fails on an `assert` line inside the Then line its card's "Fails today on" names, with the
   value the card predicts — SY-17 `15 == 10` in Then 2, L-04 `['bolt', 'Bolt']` in Then 2, L-19 / L-21 in Then 2,
   EN-07 `updated_by` still U1 in Then 3, the other 27 in Then 1; no setup or import error. INV-ST-03 passes.)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory.py -q -p no:cacheprovider -rxX     (run 2)
  158 passed, 32 xfailed, 1 xpassed in 5.22s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory.py -q -p no:cacheprovider -rxX     (run 3)
  158 passed, 32 xfailed, 1 xpassed in 5.19s
  (same outcome in all runs — no flaky test; XPASS is INV-ST-03 each time)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/inventory.py tests/unit/dao/test_inventory.py --json <scratch>/r2_mut.json
  Mutants: 96 · killed 86 · timeout 0 · survived 10 · score 90%   (raw; 100% after exclusions)

.venv/Scripts/python.exe -m ruff check --select F tests/unit/dao/test_inventory.py
  All checks passed!
```

## Local-coder patterns
Measured in round 1 on 178 local-written tests as delivered (no functional repair by the finishing step): 176 functionally faithful, 2 not; 9 with cosmetic defects only. No dropped Given qualifier, no wrong row order, no wrong When argument, no weakened operator, no skipped Then line, no dishonest xfail. All 11 affected tests were fixed by hand in Fix round 1; the "Status" column says what is fixed in the test file and what was seen in the tool (read in `tests/unit/_tools/local_coder.py`, not exercised by this verification).

| # | Pattern | Count | Cases | What would prevent it | Status after fix round 1 |
|---|---|---|---|---|---|
| 1 | Function-name slug copied from an exemplar instead of derived from the card title | 2 | INV-FQ-40, INV-CNT-11 (both took INV-ST-12's `factory_filter_soft_delete_and_scope`) | Tool: build the `def test_<id>__<slug>(` line itself from the card title, or reject a slug that equals an exemplar's slug / already exists in the file. | Tests fixed. The tool now has a `normalize()` step that builds the name from the card title. |
| 2 | Docstring first line without the final full stop | 6 | INV-FQ-24, INV-FQ-25, INV-FQ-26, INV-FQ-34, INV-L-06, INV-ST-25 | Tool: generate the docstring (ID, title, Rules) from the card, or normalise it on acceptance. | Tests fixed. `normalize()` builds the docstring from the card. |
| 3 | A `count:` line asserted relative to a snapshot (`before_count + 1`) instead of the card's bare number | 1 | INV-EN-13 | Tool: for a Then line "`<table>` has exactly N rows" require `count_rows(db, <Model>) == N` under that `# Then` comment. Helper sheet: "count: lines are always `count_rows(db, Model) == N` with the card's number". Same root as the retry cause "`before = written(db)` copied from the INV-L-17 exemplar" (6 retries) — here the copied snapshot was used, so the unused-variable check did not fire. | Test fixed. `static_check` now rejects a `count:` Then block without `== N`. |
| 4 | A fixed shorthand row expanded with the wrong positional argument ("S9" built in `f2` instead of `f9`) | 1 | INV-ST-13 | Helper sheet / scaffold: give S9 its own builder (e.g. `mk_s9()`), so the model never expands the definition. Tool: check the positional `(item, factory)` arguments of the n-th `mk_stock` / `mk_entry` call against the n-th Given line ("default stock of <I> in <F>", "S9", "entry of <I> in <F>") — the keyword check cannot see positionals. | Test fixed. Still open in the tooling: the helper sheet only spells S9 out (`s9 = mk_stock(i9, f9, workspace_id=w2.id)`); no builder and no positional check seen in the tool. |
| 5 | `# Given` / `# When` comments restating the card | 1 | INV-EN-17 | Tool: reject (or strip) any comment in the body other than `# Then N`. | Test fixed. `normalize()` strips comment lines other than `# Then N`. |
