# Verification — `app/dao/machine_item_ledger.py`

> **Current verdict (round 2, 2026-10-31): PASS.** See "Round 2" at the end. Everything down to that section is round 1 as written.

> **Verdict:** NEEDS WORK — only the case designer has work: 4 small groups of missing cards. No test is wrong; no test-side fix was needed, no test edited.
> Tests: 329 passed · 57 xfailed (reproduced ✅) · coverage 98% branch (37 statements, 10 branches, 0 partial; only dead line 105 missed)
> Mutation: 56 mutants · 53 killed · 3 survived → score 100% (53 / 53, after excluding 0 equivalent, 3 dead, 0 bug-path)
> Fidelity: **0 of 386 unfaithful as delivered** (386 / 386 right)
> Hand variants: 267 · 243 caught · 24 survived (22 `case-missing`, 1 equivalent, 1 caught by `test_base.py`)
> Source commit: e48a092 · Cases revision: 1 (386 cases; spec APPROVED)

## Summary
- **The generated tests can be trusted as written.** I read all 386 tests against their cards: every Given row, When call and numbered Then line, plus the helpers and fixtures once. No swapped row, wrong object, weakened or vacuous-by-mistake check, or extra mock turned up, in one test or repeated.
- **The evidence goes beyond reading.** A reference fix written from the spec passed 386 of 386 on its first run. Each of the 57 xfails fails today on the line and for the reason its card gives; none is a setup error. Every mutant in live code is killed by a real failing assertion.
- **Why NEEDS WORK:** rules with no card. All 3 mutant survivors are in dead code, but 22 hand variants break a written rule and no test notices. They fall into 4 groups, all for the case designer. Scratch tests show each is closed by a small card.
- **No money or order-workflow question arises.** Rounding is answered (half up, BUG-1040) and INH-51 … INH-61 match it. RS-16 … RS-18 stand, per the delegated decision on Spec gap 13.
- **Test-side fixes: none.** The test file is byte-identical to the delivered copy.

Written by Claude (all 386 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 386. No `machine_item_ledger.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence (survives every test) | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | "The call writes nothing": `get_by_machine_and_item` R6, `get_by_transaction_type` R8, `get_by_date_range` R8, `get_by_machine` R6, `get_latest_entry` R6, `get_by_performer` R3 | Only `get_by_item` (IT-10) and `calculate_balance` (BAL-28) have a pending row. A flush in the other six writes that row and is not noticed. A commit inside `get_latest_entry` is not noticed either; that lookup runs inside every machine stock movement, so a commit there would save half a movement. `get_by_machine_and_item`, `get_by_transaction_type`, `get_by_machine` and `get_by_performer` catch a commit only through their negative-paging cards, as an `InvalidRequestError` from the savepoint. | `MI_flush`, `TT_flush`, `DR_flush`, `MA_flush`, `LE_flush`, `LE_commit`, `PF_flush` | **case designer** |
| 2 | case-missing | `GET /ledgers/machine/` R1a "every field of `MachineItemLedgerCreate`" | RS-16 … RS-25 read quantity, costs, `qty_*`, `value_after`, `avg_price_after`, `source_type`, machine and item. Ten fields are never read back: `value_before`, `avg_price_before`, `source_id`, `order_id`, `invoice_id`, `notes`, the four `transfer_*`. A response that lost any of them passes. | `RS_lose_*`, 10 variants | **case designer** |
| 3 | case-missing (low) | R1a "Other columns have no limit" | RS-20 … RS-23 cover `qty_before`, `qty_after`, `value_after`, `avg_price_after`. A `ge=0` on `value_before` or `avg_price_before` would make a page fail, the BUG-990 shape. | `RS_ge_value_before`, `RS_ge_avg_price_before` | **case designer** |
| 4 | case-missing (low) | inherited R2: fields `>= 0`; "Unknown arguments, `workspace_id` and `performed_by` included, are ignored silently" | INH-07 is the only card on `MachineItemLedgerCreate`, with valid fields and no extra argument. Spec gap 1 closed the field list, and no card followed. | `SC_forbid`, `SC_ws`, `SC_noge` | **case designer** |

No fidelity finding. Each of findings 1–4 is a rule already written; none needs an owner decision.

### Recipes
13 scratch tests in `mildv\prop\test_mil_prop.py`, not in the repo. All 13 pass on the reference. Today 12 pass, and the performer one fails as BUG-645 requires.

| New card | Given | When | Then | Fails on |
|---|---|---|---|---|
| MI, TT, DR, MA, LE: a pending row is not seen (5 cards, `pass`) | E1 = entry `performed_at T1`; E2 = entry `performed_at T2`, added with `db.add(E2)` and not flushed | the method, with W1, M1, I1 as it needs (`start_date=T1, end_date=T2` for DR) | `ids(result) == [E1.id]`; for LE `result.id == E1.id` | `MI_flush`, `TT_flush`, `DR_flush`, `MA_flush`, `LE_flush` and `LE_commit` |
| PF: the same (`xfail BUG-645`) | as above | `dao.get_by_performer(db, performed_by=U1.id, workspace_id=W1.id)` | `ids(result) == [E1.id]` | `PF_flush` |
| RS: the other fields are read from the row (1 card, `pass`) | E1 = entry `performed_at T1`, `value_before Decimal("7.00")`, `avg_price_before Decimal("1.75")`, `source_id 77`, `order_id 88`, `notes "Counted"`, `transfer_source_type "machine"`, `transfer_source_id 11`, `transfer_destination_type "storage"`, `transfer_destination_id 12`; then `E1.invoice_id = 99`, not flushed (`invoice_id` has a foreign key, and `model_validate` reads the attribute) | `MachineItemLedgerResponse.model_validate(E1)` | each field equals its Given value | the 10 `RS_lose_*` |
| RS: negative `value_before`, negative `avg_price_before` pass (2 cards, `pass`) | E1 = entry with `Decimal("-12.50")`, `Decimal("-1.25")` | as RS-22, RS-23 | the value is kept | `RS_ge_value_before`, `RS_ge_avg_price_before` |
| INH: schema ignores `workspace_id` and `performed_by` (1 card, `pass`) | none | `dao.create(db, obj_in=MachineItemLedgerCreate(<INH-07 fields>, workspace_id=W1.id, performed_by=U1.id))` | as INH-07: `IntegrityError`, `NotNullViolation`, `column "workspace_id"` | `SC_forbid`, `SC_ws` |
| INH: schema rejects negative `quantity`, `unit_cost`, `total_cost` (3 cards, `pass`) | none | `MachineItemLedgerCreate(<INH-07 fields>, <field>=-1)` | `ValidationError`, `greater_than_equal` | `SC_noge` |

## Questions for the owner
None. No money or order-workflow question arises here. The open point already recorded in the spec stays as it was: FU-1, repair of stored data for machines already at 0.00 (BUG-993).

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 6 | 105 | `get_by_order`: `return` → `return None` | dead | Q5, on the dead-code list; no card, by design. | — |
| 42 | 108 | `get_by_order`: `workspace_id ==` → `!=` | dead | Same. | — |
| 43 | 109 | `get_by_order`: `order_id ==` → `!=` | dead | Same. | — |

Score: 53 / (56 − 0 equivalent − 3 dead − 0 bug-path) = 53 / 53 = **100%**. All 53 kills in the complete run report `failed`, none only `error`.

## Hand variants
`mildv\plug\variants.py`: 267 variants, each an asserted text edit of the reference, so none can be a silent no-op. Each ran over all 386 tests with `--runxfail`. No variant run hit a setup error.

| Group | Variants | Caught | Survivors |
|---|---|---|---|
| `get_by_item` | 22 | 22 | — |
| `get_by_machine_and_item` | 24 | 23 | `MI_flush` |
| `get_by_transaction_type` | 38 | 37 | `TT_flush` |
| `get_by_date_range` | 37 | 36 | `DR_flush` |
| `get_by_machine` | 22 | 21 | `MA_flush` |
| `get_by_performer` (BUG-645) | 26 | 25 | `PF_flush` |
| `calculate_balance` (BUG-641) | 31 | 30 | `BAL_value_is_none`, **equivalent**: the column is `Numeric(15, 2)`, so a stored 0 already reads `Decimal("0.00")` |
| `get_latest_entry` (BUG-664) | 18 | 16 | `LE_flush`, `LE_commit` |
| BUG-992 | 7 | 7 | — |
| BUG-100 | 5 | 4 | `b100_noskip`, in `app/dao/base.py`, where INH-40 is loose on purpose. `test_base.py` fails on it (BASE-GW-09); that file owns generic paging |
| BUG-990 | 4 | 4 | — |
| Response fields | 29 | 17 | findings 2, 3 |
| Input schema | 4 | 1 | finding 4 |

- **What the list groups cover:** each filter dropped and inverted; order ascending, id ascending on a tie, id first, none, no tie-break (BUG-640 and the rest reverted one at a time), tie sorted in Python after paging; offset and limit dropped, capped at 100, negatives clamped, `limit=0` as "all", default limit changed; hidden deleted machine, machine of a deleted factory, removed item; a commit. Lists with optional filters add: `0` as falsy, OR instead of AND, one filter dropped.
- **Exactness:** type match by `ILIKE`, `LIKE`, lower-casing, trimming, prefix, contains. Bounds strict, dropped, swapped, stretched to the day, cut to the second, `None` as no bound.
- **BUG-992:** offset cut off, no conversion, only one bound, aware value passed on, wrong zone, naive bound following the aware one.
- **Tie-order bugs:** `*_pysort` shows why the strict SQL cards matter: IT-27, MI-27, TT-52, DR-51, MA-25, PF-22 are the only cards to notice a list sorted in Python after paging.

**Only one card notices** (keep in mind when a card is edited): the `*_cap100` card (`limit 101`), the `limit 0` card and both negative-paging cards of each list; the soft-delete cards of each method; IT-10, BAL-28; BAL-01, BAL-05, BAL-06, BAL-09; TT-17, TT-24, TT-34, TT-35; DR-23, DR-24, DR-31, DR-33, DR-34, DR-59; INH-39; PF-01, PF-27; RS-15 … RS-18, RS-20 … RS-24. `mildv\variants.json` has the full map.

## xfail tests against the reference
`mildv\plug\ref_mil.py` is a pytest plugin that swaps the source of `app.dao.machine_item_ledger`, `app.dao.base` and `app.schemas.machine_item_ledger` in memory through a meta-path finder, built by asserted text edits in `refsrc.py`. Nothing is written to `app/`. It fixes BUG-100, BUG-640, BUG-641, BUG-645, BUG-664, BUG-990 and BUG-992. BUG-991 is integration-only; BUG-993 and BUG-1040 sit outside this file.

**386 passed**, 3 times with `--runxfail`: every xfail passes in full, so every Then line after a failing line also holds, and no pass test pins a bug. Without `--runxfail` the 49 strict xfails turn into failures and the 8 non-strict ones XPASS, as the notes say.

## Reproduced claims
- The notes' Result line matches: 329 passed, 57 xfailed, 98%, only line 105 missed.
- **All 57 xfails fail where and why the card says**, mapped by a plugin to `# Then N`, with no setup error:

| Cards | Fails on | Value |
|---|---|---|
| IT-26, MI-26, TT-51, DR-50, MA-24 | Then 2 | `[B, C, A]` |
| IT-27, MI-27, TT-52, DR-51, MA-25, BAL-12, LE-10 | Then 4 | clause ends at `performed_at DESC` |
| BAL-11 | Then 2 | `(15, 150.00)` |
| LE-09 | Then 2 | B |
| INH-41 | Then 2 | `[B, C, A]` against `[B, A, C]` |
| INH-42 | Then 2 | no `ORDER BY` |
| DR-16, DR-17, DR-18, DR-59 | Then 1 | `[]` |
| DR-19, DR-57 | Then 1 | the wrong single entry |
| DR-58 | Then 1 | two entries |
| PF-19, PF-20 | Then 1 | `AttributeError` |
| PF, the other 25 | the When, as carded | `AttributeError` |
| RS-09 … RS-15 | the When, as carded | `ValidationError`, pattern mismatch |

- **No flaky test.** 3 plain runs, seqscan off, index and bitmap off, and the coverage run: each 329 passed, 57 xfailed. `--runxfail`: 57 failed, 329 passed, also with the rerun below. `-W error` fails only INH-46, INH-47, the `LegacyAPIWarning` of `app/dao/base.py:136` that the notes name.
- Mocks: none. `commit_spy` wraps the real `db.commit` in INH-06, INH-45, INH-47. No broad `pytest.raises`, no `try`, `if` or `for` in a test body. `raises:` cards name the card's type. `ruff check` passes.
- Code on Spec gap 12: `app/models/profile.py` has no `is_active` or `is_deleted` column, so "the performer's own profile state" has nothing to test today. The case designer can close that gap with no card.

## Traceability
cases 386 · tests 386 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match in all 386. 329 `pass` cards have no marker; 57 xfail cards name exactly the card's bug, 49 strict, 8 non-strict. All 7 BUG IDs are in `docs/testing/bugs.md`. All 386 sit under `# [claude] <ID>`. Every snapshot, `SET LOCAL` and savepoint stands before the When.

Cosmetic, no finding: 22 RS tests list `db` without using it. It is harmless, because the autouse fixtures pull it in anyway.

## Notes for the case designer (out of date wording, no effect on any test)
The cases header, the FU-6 row under Deferred and Spec gap 3 still call rounding open; the owner answered, half up, BUG-1040. Spec gap 13 still reads Open; it is decided: the cards stand as R1a says, since no writer stores a negative value (delegated, not the owner's answer).

## Tool and process notes
- **`mutate.py` and `factories.py` changed during this round.** When I started, `mutate.py` had no re-run for an errored run and `factories.py` had no process-based `_seq`, although my brief said the re-run was in. Another session's edit was held in a shell waiting on `cat > /tmp/p.py`. It landed at 23:49–23:50, during my second run, and I did not touch it. `mut2.json` is a complete run on the old tool; `mut3.json` is a complete run on the patched tool. Both give the same status for all 56 mutants, and no kill in either is error-only, so the score does not rest on one run.
- **Runs were cut off twice.** The first mutation run stopped at 23 of 56 and the variant driver at 68, then at 232. Each was resumed or restarted; `variants.json` holds all 267. `mut1.log` is the partial run and is not used.
- **Runs were not isolated.** Other agents' pytest processes ran at the same time, and my variants ran during some of them. No setup error appeared in any of mine.

## Limits of this round
- **How the reading was done.** I read a condensed listing, `mildv\compact.txt`. A card line is collapsed into the test line only where my own converter finds them equal; everything else showed both sides. 1 460 of 1 890 Given, When and Then lines collapsed, and I read the collapsed text as well.
- **The converter was not self-tested.** A planted-mistake test (`mildv\plant.py`) was refused in the session, so I did not run it to the end and have no figure. The checks that stand in its place are the reference run, the mutants and the variants.
- **The reference is one fix, mine.** Another correct fix could expose a card that assumes something mine happens to do.
- **Pass-card Then lines were not each forced to fail.** They rest on mutation and the variants.
- **Only this file's tests ran against the variants**, apart from `b100_noskip`, which I also ran against `test_base.py`.
- Model limits (`Numeric(15, 2)`, varchar lengths) have cards, but no variant changed the model.
- Not exercised: anything at HTTP level (BUG-990's 500, BUG-991), BUG-993, a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/machine_item_ledger.py tests/unit/dao/test_machine_item_ledger.py --timeout 300 --json <scratch>/mut2.json
  Mutants: 56 · killed 53 · timeout 0 · survived 3 · score 95%      (raw; kills audited, all "failed")
  SURVIVED #6 L105, #42 L108, #43 L109
same, --json <scratch>/mut3.json     (patched tool, factories.py with the process-based _seq)
  Mutants: 56 · killed 53 · timeout 0 · survived 3 · score 95%      (same status for all 56; all kills "failed")
  then 329 passed, 57 xfailed; --runxfail 57 failed, 329 passed

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_item_ledger.py -q -p no:cacheprovider --cov=app.dao.machine_item_ledger --cov-branch --cov-report=term-missing
  app\dao\machine_item_ledger.py     37      1     10      0    98%   105
  329 passed, 57 xfailed, 2 warnings

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_item_ledger.py -q -p no:cacheprovider --runxfail -rf --tb=no
  57 failed, 329 passed, 2 warnings

same, --tb=no (3 times); PGOPTIONS="-c enable_seqscan=off"; PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"
  329 passed, 57 xfailed (each)
same, -W error
  2 failed (INH-46, INH-47), 327 passed, 57 xfailed

MILREF=fix ... -p ref_mil --runxfail      386 passed     (3 times)
MILREF=fix prop/test_mil_prop.py          13 passed
drive.py                                  267 run, 243 caught, 24 survived
.venv/Scripts/python.exe -m ruff check tests/unit/dao/test_machine_item_ledger.py     All checks passed!
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mildv\`: `plug\ref_mil.py`, `plug\refsrc.py`, `plug\variants.py`, `drive.py`, `drive.log`, `variants.json`, `vsum.py`, `x.sh`, `sum.py`, `static.py`, `listing.py`, `compact.py`, `compact.txt`, `plant.py`, `prop\test_mil_prop.py`, `mut1.log`, `mut2.log`, `mut2.json`, `mut3.log`, `mut3.json`, `delivered_test.py`, `res\`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

## Fix list
1. **Case designer:** add cards for findings 1–4, about 13 cards; the recipes above. Close Spec gap 12 and update the out-of-date wording.
2. **Executor,** after 1: implement the new cards and send back for re-verification.

## Round 2 — 2026-10-31

> **Verdict:** PASS
> Tests: 343 passed · 58 xfailed (reproduced ✅) · coverage 98% branch (only dead line 105 missed)
> Mutation: not re-run. Round 1 stands: 56 mutants · 53 killed · 3 dead → score 100%. No existing test, helper, fixture or app file changed
> Fidelity: **0 of 15 new tests unfaithful** · Hand variants: 22 of 22 `case-missing` variants now fail the right card
> Source commit: e48a092 · Cases revision: 2 (401 cases; spec APPROVED)

- **Scope of the change.** The test file gains 15 tests and loses nothing: the diff against my delivered copy is additions only, so the 386 tests and all helpers are byte-for-byte the same. A fresh condensed listing shows every old card and test unchanged.
- **The 15 new tests,** read against their cards, every Given, When and Then line, including the long lines in full: MI-31, TT-58, DR-62, MA-29, LE-24, LE-25, PF-28, INH-77 … INH-81, RS-26, RS-27, RS-28. All faithful. PF-28 is `xfail(strict=True)` naming BUG-645; the other 14 have no marker. LE-25 pulls the commit spy and opens the savepoint before the call.
- **Traceability:** cases 401 · tests 401 · unmatched none · duplicates none · marker mismatches none (343 pass, 50 strict, 8 non-strict). `# Then N` numbers match. `ruff check` passes.
- **Reference:** 401 of 401 with `--runxfail`. The new PF-28 fails today in the When on `AttributeError`, as its card says; no setup error.
- **No flaky test:** plain, seqscan off, index and bitmap off, coverage: each 343 passed, 58 xfailed. `--runxfail`: 58 failed, 343 passed. The notes' Result line matches.

| Finding | Variants | Now fails |
|---|---|---|
| 1 | `MI_flush`, `TT_flush`, `DR_flush`, `MA_flush`, `LE_flush`, `PF_flush` | MI-31, TT-58, DR-62, MA-29, LE-24, PF-28, each alone |
| 1 | `LE_commit` | LE-25, LE-24 |
| 2 | 10 `RS_lose_*` | RS-26 (`value_before` also RS-27, `avg_price_before` also RS-28) |
| 3 | `RS_ge_value_before`, `RS_ge_avg_price_before` | RS-27, RS-28 |
| 4 | `SC_forbid`, `SC_ws` | INH-77 |
| 4 | `SC_noge` | INH-78, INH-79, INH-80 |

- **Survivors left:** `BAL_value_is_none` (equivalent; 401 passed on it again) and `b100_noskip` (owned by `test_base.py`, not re-run here). Neither counts against the verdict.
- **Variant run complete.** `mildv/variants.json` holds all 267 of `plug/variants.py`: none missing, none extra, no error, each over all 386 tests. The cut at 232 of round 1 (the one near 01:18) was resumed and finished with `DONE`. Those figures are from revision 1; on revision 2 only the 22 above and the equivalent were re-run, not the other 244.
- **Round 1's self-test gap stands:** `plant.py` was not run, so the listing has no planted-mistake figure.

Scratch, under `mildv/`: `round2.py`, `round2.diff`, `compact2.txt`, `res/r2_*.json`. Only this report was edited in the repo. No commit.

Commands:
```
round2.py run      fix: 401 passed · today: 58 failed, 343 passed · 22 of 22 · equivalent: 401 passed
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_item_ledger.py -q -p no:cacheprovider --cov=app.dao.machine_item_ledger --cov-branch --cov-report=term-missing
  app\dao\machine_item_ledger.py     37      1     10      0    98%   105
  343 passed, 58 xfailed, 2 warnings
```
