# Execution notes — `app/dao/payment_transaction_event.py`

> Cases: `tests/unit/dao/payment_transaction_event.cases.md` (revision 1, READY, 23 cases; spec APPROVED 2026-11-01) · Tests: `tests/unit/dao/test_payment_transaction_event.py` · Source commit: e48a092
> Result: **23 tests for 23 cases — 15 passed · 8 xfail (5 strict, 3 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (7 statements, 0 branches). The non-strict cards may XPASS without turning the run red (see Stability), so a default run reads `15 passed, 6 xfailed, 2 xpassed` or `15 passed, 5 xfailed, 3 xpassed`. Only PTE-G-15 of the BUG-1190 cards must always xfail.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_payment_transaction_event.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. Built in one batch with its seven siblings. The card bodies were transcribed by a throwaway parser of the cases file (not kept; `scratchpad\evx\`), so values are the card's own text. The standing rows and helpers were written by hand. A separate AST pass, reading the cards again, checked: each ID exactly once and in card order, `# Then 1..N` matches the card's Then count in order with a check under each, every backticked Then expression is present and in order, marker and bug match the Expect line, one builder call per Given row, no unused argument, no fixture used without being an argument.

## How the tests are built
- **Nothing is patched** (Conventions, Externals: None).
- **Constants:** `dao` (the singleton, a module-level name), `MISSING = 999999999`, `T1`, `T2`, `T3`.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `u1`, `tx1`, `tx2`, `tx9`); the autouse `standing_rows` makes all of them exist in every test. Each test lists only those it names. `w2` depends on `w1`, so ids rise in Conventions order.
- **Builders (keyword-only fixtures, flush before returning):** `mk_event(created_at=, **columns)` = "event"; `metadata_json` and `performed_by` stay out of the constructor unless the card gives them, so `metadata_json=None` (JSON `null`) differs from no keyword (SQL `NULL`). `mk_log(count)` = the `add_all` Given of the long-log cards, returns `oldest_first`.
- **Reading helpers (no expected values inside):** `ids`; `snap(db, row)` (every column, Core select, for "unchanged"; the check runs `db.expire_all()` first, as "re-read" says); `stored_count(db)` ("nothing written"); `stored_json(db, row)`.
- **Given rows no line names again** are built without a variable (F841).
- **U2, U3** (the id-against-other-columns cards) are local to their tests: `make_profile(db)` twice, first in the body, so they come after U1.
- **Row letters** of the cards are lower case in the code (`A` → `a`, `P` → `p`).
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` is the one SELECT naming this table and fails loudly unless there is exactly one. `order_part_of(sql)` is the Conventions' `order_part`.
- **xfail markers:** `reason` is `BUG-NNN: <bug title>`; the non-strict ones add why they cannot be strict. PTE-G-06 is `with pytest.raises(TypeError) as exc:` as Then 1, with its second `raises:` line as an `assert` after the block.

## xfail location (`--runxfail`, reading the failing value)
### Revision 0
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| PTE-G-03 | yes | the When line, ahead of `# Then 1`, as the card's "Fails today on" says | `TypeError: ... got an unexpected keyword argument 'workspace_id'` |
| PTE-G-04 | yes | same | same |
| PTE-G-05 | yes | same | same |
| PTE-G-06 | yes | Then 1 | `Failed: DID NOT RAISE TypeError` |
| PTE-G-13 | no | Then 1, when it fails | `assert [42431, 42430] == [42430, 42431]`: the higher id first |
| PTE-G-14 | no | Then 1, when it fails; it did not fail on its own in any run | XPASS, see Stability |
| PTE-G-15 | yes | Then 3, every run on every plan; **it never XPASSED** | `assert '.id' in ' payment_transaction_events.created_at ASC'` |

**Proof that both non-strict cards can fail on their Then 1.** A scratch plugin (`scratchpad\evx\evx_order.py`, `-p evx_order`, a `before_cursor_execute` rewrite of the statement's text, nothing in `app/`) appended an explicit tie order. An explicit order is a legal result for a query that asks for none among ties, and it depends on neither plan nor heap. It rewrote all 16 statements of the file's successful calls. Same result on the default plan, with `enable_seqscan=off`, and with index and bitmap scans off.

| Appended order | PTE-G-13 | PTE-G-14 | Whole file |
|---|---|---|---|
| `, payment_transaction_events.id DESC` (the wrong one) | **fails on Then 1**, `assert [43734, 43733] == [43733, 43734]` | **fails on Then 1**, `assert [43736, 43735] == [43735, 43736]` | 12 passed, 7 xfailed |
| `, payment_transaction_events.id ASC` (the rule) | passes | passes | 12 passed, 5 xfailed, 2 XPASS |

So no pass card depends on the order of tied rows; PTE-G-12 holds under both. The recorder saw the original text in these runs (the rewrite comes after its listener), so PTE-G-15 stayed on Then 3 here.

**Proof of the lines past a failure point, and of the alarm.** A second scratch plugin (`scratchpad\evx\evx_fix.py`, `-p evx_fix`) replaced the method in-process with a reference of the fix.

| Reference (`EVX_FIX`) | `--runxfail` | Markers on |
|---|---|---|
| `order`: today's signature, `created_at`, then `id` | 15 passed; G-03 ... G-06 fail on the missing parameter | **PTE-G-15 XPASS(strict), the red run the card is there for.** `1 failed, 12 passed, 4 xfailed, 2 xpassed` |
| `optional`: `workspace_id` optional, filter when given, full order | 18 passed; only G-06 fails, by the design of this reference | G-03, G-04, G-05, G-15 XPASS(strict), so all four alarms sound |
| `required`: the spec's fix, `workspace_id` required, full order | G-03 ... G-06 pass; the other 15 fail with `TypeError` | 16 failed, 3 xfailed (G-13, G-14, G-15, on `TypeError`) |

The `optional` line reaches every assertion of every card, G-06's second Then aside; the `required` line reaches that one. The `required` line is cases Spec gap 5 as run: the fix must add the argument to the whole file, and if BUG-1191 is fixed first, G-15 stays xfail on `TypeError` and its alarm is silent.

### Revision 1
`--runxfail` on the patched file: 6 failed, 17 passed. G-03, G-04, G-05 on the same `TypeError`, G-06 `DID NOT RAISE TypeError`, G-13 `assert [233540, 233539] == [233539, 233540]`, G-15 on Then 3 as before. G-14 and G-20 passed.

| Card | Strict | Fails on | Actual |
|---|---|---|---|
| PTE-G-20 | no | Then 1, when it fails; it did not fail on its own in any run | XPASS in all 8 runs, as expected |

**Proof that PTE-G-20 can fail on its Then 1.** `evx_order.py` (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evx\`) appended each of these to the tied rows' order, rewriting all 20 statements, on the default plan, `enable_seqscan=off`, and index and bitmap scans off. Result per plan, in that order.

| Appended order | PTE-G-20 | Whole file |
|---|---|---|
| `id DESC` | fails on Then 1, `[236672, 236671, 236670] == [236670, 236671, 236672]`, all 3 plans | 15 passed, 8 xfailed, all 3 plans |
| `id ASC` (the rule) | passes, all 3 plans | 15 passed, 5 xfailed, 3 XPASS, all 3 plans |
| `event_type` | fails on Then 1, `[236674, 236673, 236675] == [236673, 236674, 236675]`, all 3 plans | 15 passed, 6 xfailed, 2 XPASS; 15 passed, 6 xfailed, 2 XPASS; 15 passed, 7 xfailed, 1 XPASS |
| `description` | fails on Then 1, `[236677, 236676, 236678] == [236676, 236677, 236678]`, all 3 plans | 15 passed, 6 xfailed, 2 XPASS, all 3 plans |
| `performed_by` | fails on Then 1, `[236680, 236679, 236681] == [236679, 236680, 236681]`, all 3 plans | 15 passed, 6 xfailed, 2 XPASS; 15 passed, 6 xfailed, 2 XPASS; 15 passed, 7 xfailed, 1 XPASS |

The other XPASSes in those lines are G-13 and G-14: on `event_type` and `performed_by` the two rows of those cards tie, so physical order still shows, and on `description` G-13's `"Edited"` sorts ahead of `"Logged"` while G-14's rows tie. The values are from one run on the default plan, one `-k g_20 --runxfail` each. No pass card failed under any order.

**The reference fix, again.** `evx_fix.py`, same three modes.

| Reference (`EVX_FIX`) | `--runxfail` | Markers on |
|---|---|---|
| `order` | 19 passed; G-03 ... G-06 fail on the missing parameter | **PTE-G-15 XPASS(strict): the alarm.** `1 failed, 15 passed, 4 xfailed, 3 xpassed` |
| `optional` | 22 passed; only G-06 fails, by the design of this reference | G-03, G-04, G-05, G-15 XPASS(strict). `4 failed, 15 passed, 1 xfailed, 3 xpassed` |
| `required` | G-03 ... G-06 pass; the other 19 fail with `TypeError` | 19 failed, 4 xfailed (G-13, G-14, G-15, G-20, on `TypeError`); cases Spec gap 5 as run |

## Discrepancies
None. No card was changed and no marker was loosened.

Prose only, no test affected: PTE-G-13's `Fails today on` and the spec's Notes say the higher id came first when run. That did not hold in every run: it XPASSED in 2 of 5 default runs at revision 0 and 1 of 3 at revision 1, and which way it went changed between runs with no change to the file (see Stability). The card already says this can match by accident. Its proof is the explicit order above.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/payment_transaction_event.py` (7 statements, 0 branches, 0 missed). The inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
### Revision 1
8 runs, one process each, on the patched file: 3 default, 5 forced plans.

In every run all pass cards passed, G-03 ... G-06 and G-15 xfailed, and nothing was red. G-14 and G-20 XPASSED in all 8. G-13 XPASSED in 4 of 8, and the plan does not decide it.

| Run | Result | XPASS |
|---|---|---|
| Default, run 1 | 15 passed, 6 xfailed, 2 xpassed | G-14, G-20 |
| Default, run 2 | 15 passed, 6 xfailed, 2 xpassed | G-14, G-20 |
| Default, run 3 | 15 passed, 5 xfailed, 3 xpassed | G-13, G-14, G-20 |
| `PGOPTIONS="-c enable_seqscan=off"` | 15 passed, 5 xfailed, 3 xpassed | G-13, G-14, G-20 |
| `PGOPTIONS="-c enable_seqscan=off -c enable_hashjoin=off -c enable_nestloop=off"` | 15 passed, 5 xfailed, 3 xpassed | G-13, G-14, G-20 |
| `PGOPTIONS="-c enable_hashjoin=off"` | 15 passed, 5 xfailed, 3 xpassed | G-13, G-14, G-20 |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"` | 15 passed, 6 xfailed, 2 xpassed | G-14, G-20 |
| The line above + `-c enable_hashjoin=off -c enable_mergejoin=off` | 15 passed, 6 xfailed, 2 xpassed | G-14, G-20 |

`ruff check` on the patched file: all checks passed. Line endings: LF. Coverage unchanged: 100% line and branch, with a private `COVERAGE_FILE`.

### Revision 0
10 runs, one process each, on the final file. `PGOPTIONS` reaches the connection (`SHOW enable_seqscan` → `off`).

**What is stable:** in every run all pass cards passed, G-03 ... G-06 and G-15 xfailed, and nothing was red. **What is not:** whether G-13 XPASSES. It follows the heap and the plan, and it changed between runs with no change to the file. G-14 XPASSED in all 10, as its card says.

| Run | Result | XPASS |
|---|---|---|
| Default, run 1 | 12 passed, 6 xfailed, 1 xpassed | G-14 |
| Default, run 2 | 12 passed, 6 xfailed, 1 xpassed | G-14 |
| Default, run 3 | 12 passed, 6 xfailed, 1 xpassed | G-14 |
| Default, run 4 | 12 passed, 5 xfailed, 2 xpassed | G-13, G-14 |
| Default, run 5 | 12 passed, 5 xfailed, 2 xpassed | G-13, G-14 |
| `PGOPTIONS="-c enable_seqscan=off"` | 12 passed, 5 xfailed, 2 xpassed | G-13, G-14 |
| `PGOPTIONS="-c enable_seqscan=off -c enable_hashjoin=off -c enable_nestloop=off"` | 12 passed, 5 xfailed, 2 xpassed | G-13, G-14 |
| `PGOPTIONS="-c enable_hashjoin=off"` | 12 passed, 6 xfailed, 1 xpassed | G-14 |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"` | 12 passed, 6 xfailed, 1 xpassed | G-14 |
| The line above + `-c enable_hashjoin=off -c enable_mergejoin=off` | 12 passed, 5 xfailed, 2 xpassed | G-13, G-14 |

`ruff check` on the file: all checks passed. Line endings: LF.

## Revision history
- **Revision 1 of the cases (`payment_transaction_event.verify.md` Findings 1 ... 5):** added PTE-G-20 (non-strict xfail, BUG-1190), G-21, G-22, G-23, each after the last card. PTE-G-19 gained Then 5, 6, its old Then 5 ... 7 are now 7 ... 9. PTE-G-10 Then 3 replaced by `"payment_transactions" not in sql`. No Rules line changed.
- The file was patched, not regenerated (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\evx\patch.py`): a diff against the delivered file shows those lines and the additions only. The AST pass ran again over all cards: 0 problems.

## Notes for maintainers
- Fix BUG-1190 and BUG-1191 together, or BUG-1190 first. BUG-1191's fix needs `workspace_id=` added to every call in this file (cases Spec gap 5); if it lands first, PTE-G-15 goes silent on `TypeError`.
- When BUG-1190 is fixed with an `ORDER BY`, PTE-G-15 XPASSES and turns the run red: remove the four markers.
- Never read a G-13, G-14 or G-20 XPASS as the bug being gone: all three pass with the bug present. The proof is G-15 and the explicit order above.
- `tran_id` is unique across all workspaces, so a second run of this file at the same moment waits on the first one's open transaction, and a committed `TXN-1` in `marker_test` would break it. Neither happened here.
- `recorder.sql()` picks statements by the table name, so a second statement on this table during a When fails the test at that line, not at a Then.
- "Nothing written" counts committed rows of all workspaces too. A run beside something that commits to this table could break it; nothing did here.
- The file carries a `# ruff: noqa` line: the Conventions prescribe naive datetimes.
