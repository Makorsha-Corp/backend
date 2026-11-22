# Execution notes — `app/dao/inventory_ledger.py`

> Cases: `tests/unit/dao/inventory_ledger.cases.md` (READY, 170 cases) · Tests: `tests/unit/dao/test_inventory_ledger.py` · Source commit: e48a092
> Result: 150 passed · 20 xfailed · 0 discrepancies · 0 errors — coverage 97% (52 statements, 2 missed; 20 branches, 0 missed or partial). Same outcome in three consecutive runs.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_inventory_ledger.py -q -p no:cacheprovider --cov=app.dao.inventory_ledger --cov-branch --cov-report=term-missing`

## How the tests are built
- **Local-coder mode.** The scaffold, four exemplars and the five `Author: claude` cards are hand-written; the 161 tests under a `# [local-coder] <ID>` comment were written by the local model from one card each, with `inventory_ledger.helpers.md` as its only view of the file.
- **Nothing is mocked**, no clock is patched (spec: no externals).
- **Constants:** `dao` (module-level name, not a fixture), `STORAGE`/`DAMAGED`/`WASTE`/`SCRAP`, `MISSING`, `T1`…`T5`, `HIGH_ID`.
- **`HIGH_ID`** is a marker object. `mk_entry(id=HIGH_ID)` replaces it at insert time by `high_id(db)` = max(greatest `inventory_ledger.id` or 0, `last_value` of `inventory_ledger_id_seq`) + 1000000, so the value is computed when the row is inserted, as Conventions require, and the model writes the card's own word.
- **Fixtures:** `w1`, `w2`, `u1`, `u2` (from `tests/unit/factories.py`), and the eight standing rows `f1`, `f2`, `f9`, `fd` (soft-deleted factory), `i1`, `i2`, `i9`, `ir` (removed item). The autouse fixture `standing_rows` makes all of them present in every test, so a test only requests the ones it names.
- **Builders (fixtures, flush before returning):** `mk_entry(*, performed_at, **columns)` — the Conventions "entry"; keyword-only, so no positional argument can be wrong. `mk_x9()` — the Conventions shorthand X9, with no arguments, so the shorthand is never expanded by hand.
- **`mk_101(mk_entry)`** (plain function, hand-written tests only): the Given of the five 101-entry cards — N1 … N101 inserted in that order, Nk at `datetime(2026, 1, 1, 0, 0) + timedelta(minutes=k)`, otherwise the default entry. Returns `{k: Nk}`, so the tests read `n[101].id`, `n[2].id`, `n[1].id` as the cards do.
- **Reading helpers (plain functions):** `reread(db, row)`, `snap(db, row)` (unchanged), `count_rows(db, Model)`, `written(db)` (row counts of `inventory_ledger`, `factories`, `items`), `ids(result)` — **keeps the returned order** (unlike the inventory DAO file, where it sorts).
- **Database-error cards** (`raises: DataError`) wrap the call in `db.begin_nested()` inside `pytest.raises`; `raises: ArgumentError` cards use a plain `pytest.raises` (the error is raised before any query).
- **Exemplars:** LED-PF-01 (list, order asserted, U1 and U2, four "but" values), LED-W-04 (X9 via `mk_x9()`, call for W2), LED-W-33 (`DataError` + `begin_nested`, nothing written, unchanged), LED-BAL-12 (xfail BUG-655: the call raises today and is not wrapped; W2 in a Given row).
- **No error exemplar without a "nothing written" snapshot exists:** all ten `raises:` cards of this module (LED-W-33/34, TT-29/30, DR-07/08/28/29, PF-18/19) carry "nothing written" and "unchanged(E1)". Three of the four exemplars have no snapshot, and the sheet says "only when the card has that Then line".
- **File layout:** scaffold → exemplars → `Author: claude` cards → local-model tests (trial cards first, then the rest in cases-file order).

## Local-coder run
- Model: Qwen3.6-35B-A3B Q4_K_M, n_ctx 16,384, thinking off. Helper sheet 8,439 characters. Report: `inventory_ledger.local-run.json`.
- **161 cards sent, 161 accepted: 160 on the first attempt, 1 on the second, 0 escalated.** 4,722.9 s in total (about 29 s per card), 780,792 prompt tokens, 27,920 completion tokens. The 12 trial cards (LED-W-02, TT-04, TT-22, DR-02, DR-07, DR-19, PF-03, BAL-11, BAL-13, LE-06, LE-18, EX-10) are part of the 161.
- The one retry: LED-BAL-01 — first attempt used `f1`, `i1`, `w1` without requesting them (the card has no Given row, so the model wrote an argument list of `db` only); the tool's "fixture used but not requested" rejection fixed it. Root cause: model. No change to the sheet.
- No escalation, so nothing was written by hand in place of the model.
- The helper sheet and the scaffold were not changed after the trial.
- Tool observations (tool not edited here):
  - `normalize` cuts the name slug at 70 characters, in the middle of a word (`…_keep_only_the_middle_e`, `…_the_greatest_id_gives_th`). Cosmetic, left as is.
  - Unused builder bindings (`e1 = mk_entry(...)` never read) occur only in the 12 trial tests (16 bindings in 8 of them); the 149 tests of the full run have none and no unused argument, so the runner as used for the full run already handles this.

## Step D — what was done
1. **Written by hand (5, all `Expect: pass`, all pass):** LED-W-28, LED-W-29, LED-TT-26, LED-DR-25, LED-PF-15, plus the setup helper `mk_101`.
2. **Changes to local-written tests — cosmetic only, 8 tests, 16 lines.** In each, an unused variable binding of a builder result was dropped (`e1 = mk_entry(...)` → `mk_entry(...)`); the builder call, its arguments and the order of the rows are untouched. Done by script from ruff F841, restricted to lines of the form `<name> = mk_entry(` / `<name> = mk_x9(`. None of them was a "before" snapshot, so no check was dropped.

   | Test | Bindings removed | Kind |
   |---|---|---|
   | LED-TT-04 | `e1`, `e2` | cosmetic |
   | LED-DR-02 | `e1`, `e2` | cosmetic |
   | LED-DR-19 | `e1`, `e2` | cosmetic |
   | LED-PF-03 | `x9` | cosmetic |
   | LED-BAL-11 | `e1`, `e2`, `e3` | cosmetic |
   | LED-BAL-13 | `eb`, `ec`, `ea` | cosmetic |
   | LED-LE-06 | `eb`, `ea` | cosmetic |
   | LED-EX-10 | `e1` | cosmetic |

   **Functional changes to local-written tests: none.** The other 153 local-written tests are byte-identical to what the model delivered. The file as delivered (before any Step D edit) is kept at `…\scratchpad\test_inventory_ledger.asdelivered.py` of the executing session for comparison.
3. **Scaffold (hand-written part), cosmetic:** three `# noqa: F401` comments on the imports removed (every imported name is used now); a section comment added above the local-model tests.
4. **Not done on purpose:** the local-written tests were not read against their cards and no functional repair was attempted — the verifier measures them as delivered. Ruff style findings that would change the prescribed shape were left: SIM117 (nested `with pytest.raises` / `with db.begin_nested()` is the Conventions form), DTZ001 (the cards use naive datetimes), FURB157 (one `Decimal("…")` literal copied from its card).
5. **Mechanical checks (script, all clean):** 170 case IDs in the cases file, 170 tests, each ID exactly once, function name matches the ID; every `Expect: pass` test has no marker, every `Expect: xfail BUG-…` test has exactly one `xfail(strict=True)` whose reason lists exactly the card's BUG ids (20 tests); no unused or unknown argument, no fixture used without being requested; `# Then N` comments present and in order in every test; `ruff --select F,E9,RUF100` clean.

## xfail location check (`--runxfail -rf`)
All 20 xfail tests fail under `--runxfail`, each in the Then line its card names in "Fails today on", and each agrees with `fails_in_then` in the run report (LED-BAL-12 is an exemplar and is not in the report).

| Cards | Card says | Fails today at |
|---|---|---|
| LED-W-15, W-18, TT-20, TT-21, DR-19, DR-20 (BUG-885) | Then 1 | Then 1, `assert result == []` — two entries returned |
| LED-W-21, TT-22, DR-21, PF-11 (BUG-640) | Then 2 | Then 2, `assert ids(result) == [ec.id, ea.id, eb.id]` — returned `[EB, EC, EA]` (W-21, TT-22, PF-11) or `[EA, EC, EB]` (DR-21), the two orders the cards predict |
| LED-LE-06 (BUG-641) | Then 1 | Then 1, `assert result.id == ec.id` — EB returned |
| LED-BAL-08 … BAL-16 (BUG-655; BAL-13 also BUG-641) | Then 1 (the call raises AttributeError) | the When call itself, `AttributeError: 'InventoryLedger' object has no attribute 'value_after'`, not wrapped in `pytest.raises` (report: `fails_in_then` 0 = before the first Then) |

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 48 | dead | Body of the `get_by_id_and_workspace` override (identical to the inherited `BaseDAO` method). Spec, Not specified: dead code, to be removed (Q2). No cards by design. |
| 109 | dead | Body of `get_by_order` (filters on `order_id`, a column the table does not have; nothing calls it). Spec, Not specified: dead code, to be removed (Q1). No cards by design. |

Every other statement and all 20 branches are covered. No `spec-gap`, `deferred` or `unreachable` line.

## Seen, left for verifier
- No functional mistake was noticed in the local-written tests — but they were deliberately **not** read against their cards, so this is not a finding of faithfulness. All 161 are to be measured as delivered (apart from the 16 dropped bindings listed above).
- The mechanical checks above cannot see: a wrong row or value that still gives the designed outcome, an assertion weaker than the card's, a Then line implemented under the right comment with the wrong expression.

## Factories added
None.

## Notes for maintainers
- When BUG-655 is fixed, LED-BAL-08 … BAL-16 XPASS (remove the markers), except LED-BAL-13, which then keeps failing on BUG-641 (tie) in Then 1.
- When BUG-640 / BUG-641 / BUG-885 are fixed, their xfail tests XPASS → remove the marker.
- The tie cases depend on `HIGH_ID` being far above the sequence; an explicit id does not advance the sequence, so EA gets `EB.id + 1`.
- When `get_by_order` and the `get_by_id_and_workspace` override are removed (dead-code checklist), coverage becomes 100%.
- The five 101-entry tests insert 101 rows each with one flush per row (ids must rise in insertion order); they account for most of the file's run time (about 4.5 s without coverage).
