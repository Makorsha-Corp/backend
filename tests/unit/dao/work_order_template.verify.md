# Verification — `app/dao/work_order_template.py`

> **Verdict:** PASS (round 1, 2026-11-09)
> Tests: 85 passed · 10 xfailed · 1 xpassed (AG-09, non-strict, as its card allows) (reproduced ✅) · coverage 100% branch (40 statements, 8 branches)
> Mutation: 43 mutants · 43 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 8 wrong implementations + 1 reference fix · 8 killed · 0 survived
> Source commit: e48a092 · Cases revision: 2

## Summary
The tests can be trusted. All 96 cards are implemented one-to-one, in card order, with every Then line asserted exactly as written. Only `db.commit` is wrapped (DA-05), and the wrapper calls the real method. Three plain runs give the same result. Under `--runxfail`, every one of the 10 failing xfail tests fails on the Then line its card names. All 43 `mutate.py` mutants are killed. My own variants are caught as well: a wrong tie-break direction, the tie-break key placed first, liveness added to only one scope branch, an inner join that drops sectionless templates, due and end-date checks off by one day, the workspace scope dropped, and approvers sorted descending. Under a reference fix of BUG-2330/2331/2332, every xfail test for those bugs passes. Nothing has to change in this module's tests.

## Findings
None in the tests.

Minor wording point in a card, which does not affect the test:
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | card wording (no test impact) | WOTP-M-02 "Fails today on" | The text says the Dhaka `created_at` is "six hours ahead and earlier than `before`". Under `Asia/Dhaka` the local value is later than `after`, not earlier than `before`. The failing check (`before <= created_at <= after`, Then 2) is still correct. | `--runxfail`: M-02 fails at line 1852, `# Then 2` | case designer (optional, wording only; next revision) |

## Surviving mutants
None. All 43 mutants are killed: the workspace, id, template, active, recurring, section and factory comparisons; `is None` / `is not None` on lines 44, 46, 51, 57 and 59; both `<=` on lines 58 and 59; `and`/`or` on 57–59; the `if` on lines 28, 30, 44 and 46; `True→False` on lines 41, 42 and 49 (`isouter`); and `return None` on every method.

## Hand variants
These were run with my own plugin `vplug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tplv\wotdao\plug\`. It is selected with `VARIANT=<name>` and loaded with `-p vplug --runxfail`, and it monkeypatches the DAO methods in the test process; `app/` is untouched.

| Variant | Result | Killed by |
|---|---|---|
| `ref`: `created_at DESC, id DESC`; approvers `ORDER BY id`; deleted section neither filters nor matches | 94 passed, 2 failed (M-02, M-03: BUG-2333 is a model fix the plugin does not make) | — (reference: GW-15…18, AG-08…10 and RD-13/14 all go green) |
| `tie_asc`: tie-break `id ASC` | KILLED | GW-15, 16, 17, 18 |
| `tie_first`: `ORDER BY id DESC, created_at DESC` | KILLED | GW-12, 13, 14, 18, 20, 21, 22, 26, 28 |
| `sec_only_factory`: liveness only in the factory branch | KILLED | RD-14 |
| `inner_join`: factory scope as an inner join (sectionless templates lost) | KILLED | RD-12, 13, 15, 16, 19 |
| `due_lt`: `next_generation_date < target` (off by one day) | KILLED | RD-01, 05, 09 … |
| `end_lt`: `target < recurrence_end_date` (end date off by one day) | KILLED | RD-09 |
| `no_ws`: `list_recurring_due` without the workspace filter | KILLED | RD-02, 10, 11 … |
| `appr_desc`: approvers `ORDER BY id DESC` | KILLED | AG-08, 09, 10 |

Scheduling variants that do not apply here: month end, leap year, and "recurring due date off by one day" in the date arithmetic. This DAO does no date arithmetic; it only compares stored `date` values with `target_date` (lines 58–59), and both sides of each comparison are pinned (RD-05/06, RD-09). Computing the next date is the manager's job, so those variants belong to `work_order_template_manager`.

Audit-log paging tie-break and money rounding: neither applies, because this DAO pages no audit log and does no arithmetic. The `Numeric(15, 2)` rounding is HR-15 in the manager spec.

## Traceability
cards 96 · tests 96 · unmatched: none · duplicates: none · marker mismatches: none.
- 85 `pass` cards: no xfail marker.
- 11 xfail cards: GW-15, 16, 17 and AG-08, 09 carry `strict=False`, as their cards say "(non-strict)". GW-18, RD-13, RD-14, AG-10, M-02 and M-03 carry `strict=True`.
- Each reason constant (`R2330`…`R2333`) names its BUG ID, and all four (BUG-2330…2333) exist in `docs/testing/bugs.md`.
- The check was done with my own AST script (`tplv\wotdao\trace.py`). The card/test pairing for the fidelity read was produced by `tplv\wotdao\pair.py`.

## Fidelity read (all 96 cards)
- Every Given is reproduced:
  - the standing rows in the Conventions order, each flushed;
  - W0/W2 rows on both sides in every isolation card;
  - explicit ids only in AG-08;
  - `add_all` + one flush in GW-23/24, RD-17 and IT-04;
  - `expire_all` where the card has it.
- No `try`/`except`. `pytest.raises(DataError)` wraps `begin_nested()`, as the Conventions prescribe.
- `unchanged(X)` reads the table after `expire_all`.
- The statement recorder requires exactly one SELECT.
- Strict ordering is asserted with `ids(...) ==` wherever the card does so. Sets are compared only where the card uses `idset` (`list_recurring_due` has no order by rule; the approvers' order is BUG-2331).

## Commands run
```
COVERAGE_FILE=<tplv>/wotdao/.cov1
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_template.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.work_order_template --cov-branch --cov-report=term-missing
  → app\dao\work_order_template.py 40 0 8 0 100% · 85 passed, 10 xfailed, 1 xpassed in 14.95s
.venv/Scripts/python.exe -m pytest … --runxfail -rf
  → 10 failed, 86 passed (GW-15/16/17 Then 2, GW-18 Then 4, RD-13/14 Then 1, AG-08 Then 2, AG-10 Then 2, M-02/M-03 Then 2; each the card's line)
.venv/Scripts/python.exe -m pytest … (twice more)
  → 85 passed, 10 xfailed, 1 xpassed in 8.04s · 85 passed, 10 xfailed, 1 xpassed in 7.72s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/work_order_template.py tests/unit/dao/test_work_order_template.py --json <tplv>/wotdao/mut.json
  → Mutants: 43 · killed 43 · timeout 0 · survived 0 · score 100%
VARIANT=<v> PYTHONPATH=<tplv>/wotdao/plug .venv/Scripts/python.exe -m pytest … -p vplug --runxfail --tb=no
  → see Hand variants
```
