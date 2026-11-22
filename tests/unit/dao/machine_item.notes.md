# Execution notes — `app/dao/machine_item.py`

> Cases: `tests/unit/dao/machine_item.cases.md` (revision 1, READY, 198 cases; spec APPROVED 2026-10-30) · Tests: `tests/unit/dao/test_machine_item.py` · Source commit: e48a092
> Result: **198 tests for 198 cases — 156 passed · 42 xfail (28 strict, 14 non-strict) · 0 discrepancies · 0 errors** — line and branch coverage 100% (16 statements, 0 branches). The 14 non-strict order cards may XPASS without turning the run red, and how many do changes with the plan and the heap (see Stability). The last default runs read `156 passed, 36 xfailed, 6 xpassed`; only `156 passed` and "no strict XPASS" are fixed.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine_item.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept; session scratchpad), so values are the card's own text. The fixtures and helpers were written by hand. An AST pass checked: each ID exactly once, `# Then 1..N` matches the card's Then count in order, marker and bug match the Expect line, no unused or missing fixture. The 9 revision 1 tests were written by hand from their cards, and the same check was run again on all 198.

## How the tests are built
- **Nothing is patched** (Conventions, Externals: None). The commit spy of INH-03, INH-34, INH-40, INH-51 wraps the real `db.commit` (`patch.object(db, "commit", wraps=db.commit)`). INH-51 has no savepoint, as its card says.
- **Constants:** `dao` (= `machine_item_dao`, a module-level name) and `MISSING = 999999999`.
- **Standing rows:** one fixture per Conventions row (`w1`, `w2`, `f1`, `fd`, `fi`, `f9`, `m1`, `m2`, `m3`, `md`, `mi`, `mf`, `mg`, `m9`, `i1`, `i2`, `i3`, `ix`, `i9`); the autouse `standing_rows` makes all of them exist in every test. Each test lists only those it names. `w2` depends on `w1`, so ids rise in Conventions order.
- **Builders (keyword-only fixtures, flush before returning):** `mk_stock(machine_id=, item_id=, **columns)` = "stock" (W1, qty 5, req_qty and defective_qty None); `mk_item(**columns)` = "item" (W1 unless the card gives `workspace_id`, as GM-53 does); `mk_part_stock(count)` = the Nk items flushed one by one, then Sk with `add_all`, returns `all_ids` (GW-15…17, GM-37…39); `mk_press_stock(count)` = the Pk machines, then Sk, both with `add_all` (GT-25, GT-26).
- **Reading helpers (no expected values inside):** `ids`, `item_names`; `reread(db, row)` (expire_all, then select by identity key); `snap(db, row)` (every column of any table, Core select, for "unchanged"); `count_rows(db, **where)`; `written(db)` ("nothing written").
- **Given rows no line names again** are built without a variable (F841), and the "Snapshot of X taken here" lines keep their place in the Given.
- **Database-error cards:** `with pytest.raises(X) as exc:` around `with db.begin_nested():`; that block is Then 1. INH-09 (`TypeError`) uses a plain `pytest.raises`, as the card says.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection. GW-14, GM-36, GT-28, INH-45, GT-32: around the When only, then `[sql] = recorder.selects()` (fails loudly unless exactly one SELECT) and, except in GT-32, `order_part_of(sql)`. GW-32, GM-51, GT-31: the Then lines sit inside the `with`, so a lazy load would be counted.
- **Probe:** `machine_items` and `machine_item_ledger` have 0 committed rows in `marker_test`, so the absolute `count:` lines hold. The constraints `machine_items_machine_id_fkey`, `machine_items_item_id_fkey`, `machine_items_workspace_id_fkey` exist. `items` has no unique index on the name, so GM-32 / GM-33 can hold "Bolt" and "bolt" next to I1 ("Bolt").
- **xfail markers:** strict → `strict=True, reason="BUG-NNN: <bug title>"`; non-strict → `strict=False` with the bug title and why it cannot be strict.

## xfail location (`--runxfail`, reading the failing value)
Every card fails on the Then its `Fails today on` names.

| Cards | Strict | Fails on | Actual |
|---|---|---|---|
| GW-14, GM-36, GT-28, INH-45 | yes | Then 2 | the SELECT has no `ORDER BY` |
| GT-32 | yes | Then 2 | the SELECT carries `LIMIT` (and `OFFSET`) |
| GM-16, GM-17, GM-18, GM-52, GM-54 | yes | Then 1 | one row returned (A, Z, A, Z, Z) instead of `[]` |
| GM-25, GM-53 | yes | Then 1 | `[A.id, B.id]`, not `[B.id]` |
| GM-26, GM-27 | yes | Then 1 | one row, not `[]` (GM-27: one of three left after `skip=2`) |
| GT-13, GT-16 | yes | Then 1 | `[A.id, B.id]`, not `[A.id]` |
| GT-14, GT-15, GT-17, GT-33 | yes | Then 1 | one row, not `[]` |
| GT-25 | yes | Then 1 | `500 == 501` |
| INH-10 … INH-14 | yes | Then 1 | `DID NOT RAISE IntegrityError` |
| INH-39, INH-51 | yes | the When, before Then 1, as the card says | `sqlalchemy.orm.exc.UnmappedInstanceError: Class 'builtins.NoneType' is not mapped` |
| GM-31, GM-34, GM-35 | no | Then 2 | `["Zulu", "apple", "Banana"]`, `["Zulu", "apple"]`, `["Banana", "mango"]`: the card's values, on every plan tried |
| GM-28 | no | Then 2 (when it fails) | `[A.id]`, not `[B.id]` |
| GW-11, GM-32, GM-33, GT-27, GT-34, GW-33, INH-44, INH-50 | no | Then 2 (when it fails) | the two ids swapped (`[B.id, A.id]`; INH-50 `[A.id, Z.id]`) |
| GW-12, GW-13 | no | Then 2 (when it fails) | see below |

**Proof that the non-strict cards can fail on Then 2.** The planner cannot give this proof (see Stability). An explicit wrong `ORDER BY` can: it is a legal result for a query that asks for no order, and it does not depend on the plan or the heap. Today's filters with an explicit order, in a scratch pytest plugin (nothing in `app/`), under `--runxfail`:

| Explicit order | Non-strict cards that fail on Then 2 | Other failures |
|---|---|---|
| `ORDER BY machine_items.id DESC` | 13 of 14: GW-11, GW-12, GW-13, GW-33, GM-31, GM-32, GM-33, GM-34, GM-35, GT-27, GT-34, INH-44, INH-50 | strict xfail cards only (GW-14, GT-28, INH-45 now on Then 4, GM-36 on Then 3) |
| `ORDER BY machine_items.id` | GM-28 (the 14th), and GM-31, GM-34, GM-35 | strict xfail cards only (GM-36 on Then 3) |

Every one of the 14 fails on its Then 2 in at least one row, and no pass card fails in either. This is the proof to use for these cards.

**Proof of the later Then lines.** With an in-process simulation of every fix (the five query changes and a unique index on `(workspace_id, machine_id, item_id)`, in a scratch pytest plugin, nothing in `app/`), `--runxfail` gives **198 passed**: every Then line after the failing one is reachable and right, and no pass card depends on a bug. This includes the refused-update cards INH-12 … INH-14 with their `db.refresh`.

## Discrepancies
None. No card was changed and no marker was loosened.

Prose only, no test affected: the "usually" in some `Fails today on` lines does not describe the default plan. Today's order changes between runs, so these are observations, not rules.
- **GW-11, GM-32, GT-27, INH-44:** "the updated row A usually comes back after B". They mostly XPASS on the default plan (8 of 8 runs in the first round, 3 of 3 in the second). The verifier saw INH-44 fail there.
- **GW-12, GW-13:** "A usually lands in the second window / in this window". When GW-12 failed on the default plan the window was A and D, not "A left out"; GW-13's held B and C. A and D are the two rows on I1, so the order seen follows `item_id` rather than the update. On a sequential scan the card's picture held: GW-12 `[B.id, C.id]`, GW-13 `[D.id, A.id]`.
- **GW-33, INH-50 (new):** "this card usually passes today". In all 3 default runs of revision 1 and with `enable_seqscan=off` they xfailed on Then 2 with the two ids swapped. They XPASS with index and bitmap scans off. **GT-34 (new)** XPASS on every run, as its card says.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/machine_item.py` (16 statements, 0 branches). The inherited `create`, `update`, `remove`, `get`, `get_multi` live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
**What is stable:** in every run of both rounds, and in the verifier's runs, all 156 pass cards passed, all strict cards xfailed, and nothing was red. **What is not:** which non-strict cards XPASS. It depends on the plan and on the heap, so no XPASS count and no forced plan gives a fixed result. The proof that these cards can fail is the explicit wrong `ORDER BY` above, not a planner setting.

**Corrected (verifier's Finding 6).** The first version of this section said the extra plan gives "33 xfailed, 0 XPASS" and shows all non-strict cards failing. That rested on one run and is wrong: over 14 forced runs the verifier saw GM-33 pass in 3, because its result follows the heap and not the plan alone. It also gave the default line as `5–7 xpassed` and INH-44 as XPASS 8 of 8. The verifier saw 3 and 6 XPASS on the default plan, and saw INH-44 fail there. Those figures described the runs I made, not a range to expect.

Revision 1 runs (198 cases):

| Run | Result | XPASS |
|---|---|---|
| Default, 3 runs + the coverage run | 156 passed, 36 xfailed, 6 XPASS each | GW-11, GM-28, GM-32, GT-27, GT-34, INH-44 |
| `PGOPTIONS="-c enable_seqscan=off"` | 156 passed, 36 xfailed, 6 XPASS | the same six |
| `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"` | 156 passed, 39 xfailed, 3 XPASS | GW-33, GT-34, INH-50 |
| The line above + `-c enable_hashjoin=off -c enable_mergejoin=off`, 6 runs | 156 passed, 39 xfailed, 3 XPASS each | GW-33, GT-34, INH-50 |

GM-33 stayed xfailed in those 6 runs, which does not contradict the verifier's 3 of 14. The three new order cards XPASS on a sequential scan because their intended order is the insertion order.

First round (189 cases), 8 default runs: 5–7 XPASS. GW-11, GM-32, GT-27, INH-44 in 8; GW-12, GW-13 in 5; GM-33 in 4; GM-28 in 4; GM-31, GM-34, GM-35 in 0. On `enable_seqscan=off`, 7 XPASS; with index and bitmap scans off, 3 XPASS.

The shift between runs happened with no change to the file. Autovacuum changing the planner's view of the tables is a likely part of it (`pg_stat_user_tables` showed a `last_autovacuum` on `items` and `machine_items`; the plan was not captured inside a test's transaction). `tests/unit/dao` as a whole, after revision 1: 1552 passed, 276 xfailed, 15 xpassed.

## Revision history
- **Revision 1 of the cases (`machine_item.verify.md` Findings 1–5):** added MIT-GT-32, GT-33, GT-34, GM-52, GM-53, GM-54, GW-33, INH-50, INH-51 (6 strict, 3 non-strict), each after the last card of its section. No existing test changed. One helper changed: `mk_item` now lets a card override `workspace_id` (GM-53); it behaves the same for every earlier card. The recipes in the verifier's scratch file were used as a cross-check; the tests follow the cards.
- **Finding 6:** Stability section corrected, the explicit wrong `ORDER BY` proof added (extended to the 3 new cards), and the prose notes under Discrepancies reworded to match.

## Notes for maintainers
- When a BUG is fixed, its strict cards XPASS and turn the run red: remove the marker. BUG-983's index also makes EMI-07 in `tests/unit/managers/inventory_movements.*` fail (cases file, Deferred FU-3 (b)).
- The joined eager load of `MachineItem.item` is what lets GW-32, GM-51, GT-31 see one SELECT. It also means every query here joins `items`, so today's row order is not the physical order of `machine_items` alone.
- GM-36 asserts `lower(` and `.name` before `machine_items.id` (Spec gap 4): a fix using a collation instead of `lower` changes those lines.
- `remove` emits a `LegacyAPIWarning` (`Query.get`, `app/dao/base.py:136`): four warnings in each run, from INH-38, INH-39, INH-40, INH-51.
- The file has LF line endings. `test_item_tag.py` has CRLF.
