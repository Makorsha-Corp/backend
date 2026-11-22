# Execution notes — `app/dao/machine_item_ledger.py`

> Cases: `tests/unit/dao/machine_item_ledger.cases.md` (revision 2) · Tests: `tests/unit/dao/test_machine_item_ledger.py` · Source commit: e48a092
> Result: 343 passed · 58 xfailed · 0 discrepancies · 0 errors — branch coverage 98%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_item_ledger.py -q -p no:cacheprovider --cov=app.dao.machine_item_ledger --cov-branch --cov-report=term-missing`

## How the tests are built
- Normal mode, no local model. Form model: `tests/unit/dao/test_inventory_ledger.py`; fixture layout as in `test_machine_item.py`. Every test sits below `# [claude] <ID>`, in card order, with `# Then N` comments. For a `raises:` first Then, `# Then 1` stands before the `with pytest.raises` line.
- The tests were converted from the card text by a throwaway script (not kept), which stopped on any line it could not read. The fixtures and helpers were written by hand. Checked afterwards by script against the cases file: 386 cards to 386 tests in order, `# Then` numbers 1…n per card, marker and strictness per Expect line. A sample of the unusual cards was read by hand. The per-card audit is still the verifier's job.
- Conventions: `w1`, `w2`, `u1`, `u2`, `f1`, `f9`, `fd`, `m1`, `m2`, `md`, `mf`, `i1`, `i2`, `ir` are fixtures, all pulled by the autouse `standing_rows`. `full` = FULL. `mk_entry` = **entry**, inserted and flushed, resolves the `HIGH_ID` marker at insert time. `mk_pending` = "added with `db.add` and not flushed". `mk_n` = the N1 … Nk Given, returns `{k: Nk}`.
- Variable names: the cards' uppercase names become lowercase (`E1` → `e1`, `N1` → `n[1]`). A Given row no check refers to has no variable.
- Named checks: `ids`, `reread`, `snap`, `written`, `count_rows`. `snap` reads the table with Core, so it needs no expire.
- Nothing is mocked. `commit_spy` wraps the real `db.commit` (`patch.object(..., wraps=...)`). No race simulations.
- Statement recorder: a `before_cursor_execute` listener on the session's connection. `[sql] = rec.selects()` raises if the call did not send exactly one `SELECT`, which keeps "the one SELECT" honest without an extra assertion.
- Database errors: `pytest.raises` around `db.begin_nested()` around the call. `ArgumentError` and `ValidationError` use a plain `pytest.raises`. `SET LOCAL TIME ZONE` lasts until the fixture's rollback.
- `# ruff: noqa: SIM117, DTZ001, FURB157`: nested `with` blocks, naive datetimes and `Decimal("-10000000000000")` are all prescribed by the cards.

## Run log
- Revision 2 (2026-10-31): 3 plain runs, each 343 passed, 58 xfailed; no XPASS, no flake (about 11 s each; other test files were running).
- Revision 2, forced plans: `PGOPTIONS="-c enable_seqscan=off"` and `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"`: same result.
- Revision 1 (2026-10-30): 8 plain runs and both forced plans, each 329 passed, 57 xfailed; both settings confirmed with `SHOW`.
- ruff: clean. LF: no CR in the file.
- The `plan-{n}` setup collision did not appear.

## xfail honesty (checked with `--runxfail`, reading each failing value)
All 58 fail where their `Fails today on` line says.

| Cards | Fails on | Value read |
|---|---|---|
| IT-26, MI-26, TT-51, DR-50, MA-24 (non-strict) | Then 2 | `[B, C, A]` against `[C, A, B]` |
| IT-27, MI-27, TT-52, DR-51, MA-25, BAL-12, LE-10 | Then 4 | `order_part` ends at `performed_at DESC` |
| BAL-11 (non-strict) | Then 2 | `(15, 150.00)` against `(10, 100.00)` |
| LE-09 (non-strict) | Then 2 | B returned, not C |
| INH-41 (non-strict) | Then 2 | `[B, C, A]` against `[B, A, C]` |
| INH-42 | Then 2 | no `ORDER BY` in `sql` |
| DR-16, DR-17, DR-18 | Then 1 | `[]` |
| DR-19 | Then 1 | `[E2.id]`: E2 back, E1 missing, as carded |
| DR-57 | Then 1 | `[E3.id]`, as carded |
| DR-58 | Then 1 | `[E2.id, E1.id]`, as carded |
| DR-59 | Then 1 | `[]`, as carded |
| PF-01 … PF-28 | Then 1 | `AttributeError: 'MachineItemLedgerDAO' object has no attribute 'get_by_performer'`; in PF-19 and PF-20 inside the `pytest.raises` block, in the others on the When line just above `# Then 1` |
| RS-09 … RS-15 | Then 1 | `ValidationError`, pattern mismatch on `transaction_type`, on the When line just above `# Then 1` |

MIL-DR-19 and MIL-DR-59, the two derived and unrun cards, did not XPASS. Their derivation holds.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 105 | dead | body of `get_by_order`, listed under Not specified (Q5: remove); no card, as designed |

No partial branches. `app/schemas/machine_item_ledger.py`, measured alongside in revision 2, is at 100%. The inherited methods live in `app/dao/base.py`, outside this measurement; `tests/unit/dao/test_base.py` owns them.

## Factories added
None.

## Notes for maintainers
- **A plain run hides setup errors on xfail tests**: pytest reports them as xfailed. After any fixture or factory change, re-run with `--runxfail`.
- **Fixing a bug**: its strict xfails turn into XPASS failures, so remove those markers. The non-strict order cards pass silently, so remove their markers in the same step. BUG-640 lands in five lists, and the `order_part` check needs `performed_at DESC, id DESC`.
- **BUG-341 fix**: MIL-DR-23, DR-24 pin the `None` bound raising `ArgumentError` and must be rewritten with that fix.
- **Spec gap 13** is closed under delegation: R1a stands, so MIL-RS-16 … RS-18 stay pass cards.
- **Rounding**: the owner answered on 2026-10-30: half up, which matches the database, so MIL-INH-51 … INH-61 stand as designed.
- **Fragile spots**: `HIGH_ID` reads the sequence, which other test files move, so it is resolved at insert time. Tie cards rest on physical row order only in the non-strict ones. The pass tie cards (`*-25`, `*-49`, `*-50`, BAL-10, LE-08, MA-23) assert membership, not an order.
- **Coverage next to other runs**: pytest-cov writes `.coverage` in the repo root, and a run at the same time can mix in another module's lines. Set `COVERAGE_FILE` to a private path. The Run line above assumes nothing else is measuring.
- `dao.remove` shows a `LegacyAPIWarning` from `Query.get()` in `app/dao/base.py:136` (MIL-INH-46, INH-47). Harmless here.

## Revision history
- **Revision 2 (2026-10-31):** added the 15 cards of `machine_item_ledger.verify.md` findings 1–4, all `case-missing`: MIL-MI-31, TT-58, DR-62, MA-29, LE-24, PF-28 (pending row stays pending), LE-25 (commit spy), RS-26, RS-27, RS-28, INH-77 … INH-81. They were inserted in card order by hand-written blocks; the existing 386 tests and the helpers are unchanged. No new fixture or import. PF-28 is the one new xfail (BUG-645, strict). Audit repeated over all 401 cards: same order, `# Then` numbers, markers, and all 58 xfails at their carded line under `--runxfail`.
- **Revision 1 (2026-10-30):** first version, 386 cards.
