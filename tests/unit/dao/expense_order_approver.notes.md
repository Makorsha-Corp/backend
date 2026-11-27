# Execution notes — `app/dao/expense_order_approver.py`

> Cases: `tests/unit/dao/expense_order_approver.cases.md` (Revision 1, READY, 41 cases; spec APPROVED 2026-11-01) · Tests: `tests/unit/dao/test_expense_order_approver.py` · Source commit: e48a092
> Result: **41 tests for 41 cases — 37 passed · 4 xfail (1 strict, 3 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (10 statements, 0 branches). The non-strict GO-12, GO-13 and GO-22 may XPASS without turning the run red, so a default run reads `37 passed, 2 xfailed, 2 xpassed` or `37 passed, 1 xfailed, 3 xpassed`. Only EOA-GO-14, the strict card, must always xfail.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_expense_order_approver.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `scratchpad\apx\`), so values are the card's own text. The fixtures and helpers were written by hand from the Conventions. A separate audit script checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matches the card's Then count in order with a check under each, every quoted literal of the Then lines present, the When call as written, marker and bug match the Expect line, no unused argument, no fixture used without being an argument, and the autouse fixture lists every standing row.

## How the tests are built
- **Nothing is patched** (Conventions, Externals: None).
- **Constants:** `dao` (= `expense_order_approver_dao`, a module-level name), `MISSING = 999999999`, `T10`, `T11`, `T12`.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `u2`, `u3`, `o1`, `o2`, `o9`, `oc`, `ov`); the autouse `standing_rows` makes all of them exist in every test, so a test lists only those it names. `w2` depends on `w1` and each profile on the one before, so ids rise in Conventions order.
- **Orders:** one `orders` fixture builds them in Conventions order, each flushed alone, and `o1`, `o2`, ... read from it. None: every foreign key of an expense order is a real row or null, and the Conventions name no replica step, so `orders` has no `SET LOCAL` lines.
- **Closed orders:** `oc` has `completed_at T12` and `ov` has `voided True`. Both are real columns; the model's `order_completed` is `completed_at is not None`, so OC is a completed order in the model's own sense.
- **Builders (keyword-only fixtures, flush before returning):** `mk_approver(assigned_at=, **columns)` = "approver"; the columns the Conventions say are not passed stay out of the constructor. `mk_left(user)` = "left U". `mk_many(count)` = the 101-profile and 101-approver `add_all` Given of GO-15, returns `in_order`.
- **Reading helpers (no expected values inside):** `ids`; `snap(db, row)` (every column, Core select, for "unchanged"; the check runs `db.expire_all()` first, as "re-read" says); `stored_count(db)` ("nothing written"; not called `written`, which is the card's name for the recorder's list); `pair_count(db, ...)` (the `count:` lines).
- **Given rows no line names again** are built without a variable (F841). "It is a standing row" lines add no code.
- **Row letters** of the cards are lower case in the code (`A` → `a`, `P` → `p`).
- **Database-error cards** (GU-11, GU-12): `with pytest.raises(IntegrityError) as exc:` around `with db.begin_nested():`; that block is Then 1.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming `expense_order_approvers` and fails loudly unless there is exactly one. `recorder.selects()`, `recorder.written()`, `order_part_of(sql)` are the Conventions' `selects`, `written`, `order_part`.
- **xfail markers:** `reason` is `BUG-1200: <bug title>`; the three non-strict ones add why they cannot be strict.

## xfail location (`--runxfail`, reading the failing value)
Revision 1 runs. Plugin: `apx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\apx\` (`-p apx_plug`, `APX_MODE`, a `before_cursor_execute` rewrite of the 22 `get_by_order` statements of the file, nothing in `app/`).

| Card | Strict | Fails on | Actual |
|---|---|---|---|
| EOA-GO-14 | yes | Then 4, every run on every plan | `assert '.id' in ' expense_order_approvers.assigned_at'`: the query orders by `assigned_at` alone. **It never XPASSED.** |
| EOA-GO-12 | no | Then 2, when it fails | `assert [111732, 111731] == [111731, 111732]` (index and bitmap scans off): the updated lower id comes second. Then 1 holds. |
| EOA-GO-13 | no | Then 2, only under the plugin below | It XPASSED in every run without the plugin: with no update, physical order gives the intended result. |
| EOA-GO-22 | no | Then 2, only under the plugin below | It XPASSED in every run without the plugin, for the same reason. |

**Proof that the non-strict cards can fail on their Then 2.** An explicit order is a legal result for a query that asks for none among ties, and it depends on neither plan nor heap.

| Explicit order | Cards that fail under `--runxfail` | Whole file |
|---|---|---|
| `..assigned_at, ..id DESC` (wrong) | GO-12 `assert [111891, 111890] == [111890, 111891]`, GO-13 `assert [111893, 111892] == [111892, 111893]`, GO-22 `assert [112007, 112006] == [112006, 112007]`, each on Then 2 | markers on: 37 passed, 4 xfailed |
| `..assigned_at, ..id` (right) | none of the three | `--runxfail`: only GO-14 fails |
| `..assigned_at, ..user_id` | GO-22 only, `assert [112325, 112324] == [112324, 112325]` | GO-22 and GO-14 fail, all else passes |
| `..assigned_at, ..approved DESC` | GO-22 only, `assert [112484, 112483] == [112483, 112484]` | GO-22 and GO-14 fail, all else passes |
| `..approved, ..assigned_at` (pending rows first) | GO-21, the pass card, `assert [112641, 112640] == [112640, 112641]`, and GO-12 | those two and GO-14 fail; GO-21 is the only pass card that fails |

So no pass card depends on the order among ties, GO-11 included. GO-22 is the one card that sees a tie-break on the wrong column, and GO-21 the one pass card that sees approval used as the sort key. The recorder saw the original text in these runs (the rewrite comes after its listener), so GO-14 stayed on Then 4 here.

**Proof of the lines past the failure point, and of the alarm.** `APX_MODE=fix` replaced `get_by_order` in-process with the intended query, `.order_by(assigned_at, id)`. With `--runxfail`: **41 passed**, so GO-14's Then 5 and Then 6 and every other line hold on a fixed method. With the markers on: GO-14 is `XPASS(strict)`, the red run the card is there for, and the three non-strict cards XPASS: `1 failed, 37 passed, 3 xpassed`.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

Prose only, no test affected (Revision 1): EOA-GO-22's `Fails today on` says Then 2. Without a plugin it never failed, in any of the 9 runs at the marker and on both `--runxfail` plans, which the same line expects ("physical order usually gives the intended result"). The failure is proved by the explicit orders above.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/expense_order_approver.py` (10 statements, 0 branches, 0 missed), run with a private `COVERAGE_FILE`. The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
Revision 1 runs (41 cases, final text of the file). **What is stable:** in every run below all pass cards passed, GO-14 xfailed, GO-13 and GO-22 XPASSED and nothing was red. **What is not:** whether GO-12 XPASSES (1 of the 3 default runs did). It follows the heap and the plan.

| Run | Result | GO-12 | GO-13 | GO-22 | GO-14 |
|---|---|---|---|---|---|
| Default, run 1 | 37 passed, 2 xfailed, 2 xpassed | XFAIL | XPASS | XPASS | XFAIL |
| Default, run 2 | 37 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS | XFAIL |
| Default, run 3 | 37 passed, 2 xfailed, 2 xpassed | XFAIL | XPASS | XPASS | XFAIL |
| Coverage run | 37 passed, 2 xfailed, 2 xpassed | XFAIL | XPASS | XPASS | XFAIL |
| `enable_seqscan=off` | 37 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS | XFAIL |
| `enable_seqscan=off`, hash join and nested loop off | 37 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS | XFAIL |
| `enable_hashjoin=off` | 37 passed, 1 xfailed, 3 xpassed | XPASS | XPASS | XPASS | XFAIL |
| index, bitmap and index-only scans off | 37 passed, 2 xfailed, 2 xpassed | XFAIL | XPASS | XPASS | XFAIL |
| the line above, hash and merge join off | 37 passed, 2 xfailed, 2 xpassed | XFAIL | XPASS | XPASS | XFAIL |

`PGOPTIONS` carried the forced plans. `ruff check` on the file: all checks passed. Line endings: LF. Coverage ran with a private `COVERAGE_FILE`.

Revision 0 runs (37 cases):

**What is stable:** in every run below all pass cards passed, GO-14 xfailed, GO-13 XPASSED and nothing was red. **What is not:** whether GO-12 XPASSES. It follows the heap and the plan, and it changed between runs with no change to the file (3 of the 5 default runs XPASSED).

| Run | Result | GO-12 | GO-13 | GO-14 |
|---|---|---|---|---|
| Default, run 1 | 34 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS | XFAIL |
| Default, run 2 | 34 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS | XFAIL |
| Default, run 3 | 34 passed, 1 xfailed, 2 xpassed | XPASS | XPASS | XFAIL |
| Default, run 4 | 34 passed, 1 xfailed, 2 xpassed | XPASS | XPASS | XFAIL |
| Default, run 5 | 34 passed, 1 xfailed, 2 xpassed | XPASS | XPASS | XFAIL |
| Coverage run | 34 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS | XFAIL |
| `enable_seqscan=off` | 34 passed, 1 xfailed, 2 xpassed | XPASS | XPASS | XFAIL |
| `enable_seqscan=off`, hash join and nested loop off | 34 passed, 1 xfailed, 2 xpassed | XPASS | XPASS | XFAIL |
| `enable_hashjoin=off` | 34 passed, 1 xfailed, 2 xpassed | XPASS | XPASS | XFAIL |
| index, bitmap and index-only scans off | 34 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS | XFAIL |
| the line above, hash and merge join off | 34 passed, 2 xfailed, 1 xpassed | XFAIL | XPASS | XFAIL |

`PGOPTIONS` carried the forced plans. `ruff check` on the file: all checks passed. Line endings: LF. After these runs the file changed by blank lines only (no non-blank line differs); one more default run and coverage run on the final text gave `34 passed, 2 xfailed, 1 xpassed`, 100%.

## Revision history
- **Revision 1 of the cases (`expense_order_approver.verify.md`, case-missing findings):** added EOA-GO-21, GO-22, GU-18, GU-19, each after the last card of its section. Added Then 10 (`len(db.new) == 1`) to EOA-GO-20 and EOA-GU-17; EOA-GU-17 gains R2 in its Rules line. The file was patched, not regenerated: a diff shows additions, plus the few lines the revision names.

## Notes for maintainers
- When BUG-1200 is fixed with `.order_by(assigned_at, id)`, GO-14 XPASSES and turns the run red: remove the four markers. The same line is in all five sibling DAOs, so five files turn red together.
- Never read a GO-12, GO-13 or GO-22 XPASS as the bug being gone: they pass on most runs with the bug present. The proof is GO-14 and the explicit order above.
- `recorder.sql()` picks statements by the table name, so a second statement on `expense_order_approvers` during a When fails the test at that line, not at a Then.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
- The file carries `# ruff: noqa: SIM117, DTZ001`: the Conventions prescribe the nested `with` and naive datetimes.
