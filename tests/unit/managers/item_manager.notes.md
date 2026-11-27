# Execution notes — `app/managers/item_manager.py`

> Cases: `tests/unit/managers/item_manager.cases.md` (revision 8) · Tests: `tests/unit/managers/test_item_manager.py` · Source commit: e48a092
> Result: 275 of 275 cases implemented · 143 passed · 132 xfailed · 0 discrepancies · 0 errors — branch coverage 96% (the 3 missed lines are dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider`

## How the tests are built
Local-coder mode. Scaffold and exemplars are hand-written; tests under `# [local-coder] <ID>` come from the local model, which sees `item_manager.helpers.md` and nothing else of this file.

- **Standing rows** (Conventions "exist in every test"): only `w1`, `w2`, `u1`, `u2`. They are chained fixtures, so ids rise W1 < W2 < U1 < U2, and an autouse `standing_rows` fixture creates them in every test. No other row is standing. The cards build every item, tag, link, stock row and order row in their Given lines, and some count `items` across all workspaces from zero.
- **Row builders** (fixtures returning keyword closures; each inserts one row and flushes, so ids follow the order of the Given lines):
  - `mk_item("I1"|"I2"|"IX"|"I9", **but)` uses a recipe. `mk_item(name=, name_normalized=, **but)` builds a plain "item". A positional value that is not a recipe raises a `TypeError` that names the right form.
  - `mk_tag("T1"|"T2"|"K3"|"TD"|"T9", **but)` and `mk_link(of=, to=)` build tags and links.
  - `mk_f1()`, `mk_mc1(factory=)`, `mk_ac1()`, `mk_wt1()` and `mk_stage("X")` build the support rows.
  - `mk_stock(of=, factory=, qty=)` and `mk_machine_stock(of=, machine=, qty=)` build stock rows.
  - `mk_po(factory=, current_status_id=)`, `mk_so(factory=, account=, current_status_id=)`, `mk_wo(factory=, wo_type=, status=)` and `mk_to(factory=, current_status_id=)` build orders.
  - `mk_line(of=, order=)` is one line builder for all four order tables; the order's class picks the table.
  - All defaults come from Conventions. Every NOT NULL column without a default was checked against the models (SQLAlchemy metadata probe). A rolled-back probe built every builder with every "but" variant the cards use (DAMAGED stock, deleted stock, req/defective qty, voided PO, line_number 2, completed SO, deleted WO, replaced_item_id, deleted WO line, completed TO).
- **Keyword check:** keywords that do not appear in a card's Given text (`factory`, `account`, `wo_type`) are implied by helper-sheet definition rows whose first cell names `F1`, `AC1` or `WT1`. The recipe names are positional strings, which the runner cannot check.
- **Reading helpers:**
  - `reread`, `snap` (any model, read by identity key so expired or deleted rows are safe), `count_rows(db, table, **filters)` (`None` means IS NULL) and `written` (counts `items`, `item_tags` and `item_tag_assignments`).
  - `stored_count`, `links_of`, `tag_ids_of`, `link_of` (returns `None` if the link is missing) and `ids` (sorted).
- **Patches:** none (spec: Externals to mock — none), except the race card ITM-C-32, which patches `ItemManager._check_sku_exists` with `create=True` (Conventions, Race simulations; the name is Spec gap 3 — revise the card and the test with the BUG-946 fix).
- **Rolled back** cards (C-40, U-45, D-12, A-13): `sp = db.begin_nested()` right before the call and `_commit_spy(db, monkeypatch)` (a `Mock(wraps=db.commit)` set on the session); the first checks run inside the savepoint, then `sp.rollback()` and the "after the savepoint rollback" checks.
- **Database-error cards** (`IntegrityError` / `DataError`): `with pytest.raises(...)` around `with db.begin_nested():`; `as exc` only when a further `raises:` line reads `exc.value`.
- **Exemplars** (all pass `local_coder.static_check` unchanged after `tidy_args` / `normalize`):
  - Printed in the sheet: ITM-C-11 (schema xfail), C-33 (create with tags), U-34 (strict xfail, Given code lines, `link_of`), L-01 (list), D-06 (ValueError without "nothing written"), D-39 (in-use refusal, `args[0]` / `args[1]`).
  - Kept unprinted to stay near 10k chars: C-01 (create), U-33 (tags kept / removed / added), D-08 (delete with counters).
- Every xfail exemplar was run with `--runxfail` and fails on the card's "Fails today on" line: C-11 Then 1, U-34 Then 3, D-39 Then 1.
- Helper sheet: 10,348 characters.

## Local-coder run (trial)
Model Qwen3.6-35B-A3B Q4_K_M, n_ctx 16384.
- **Batch 1** (20 cards): 18 accepted (14 on the first try), 2 escalated (C-19, UN-01).
- **Batch 2** (U-08 and UN-01 again, after the fixes below): both accepted on the first try.
- **Kept now:** 19 trial tests: C-12, C-38, U-02, U-08, U-40, G-02, G-06, L-07, L-08, N-03, UN-01, FS-03, D-21, D-29, D-44, A-07, A-10, TI-01, TS-01.

Fidelity reading (every Then check, against the card):
- All 19 kept tests match their cards, with no swapped rows, extra keywords or extra Then lines.
- Each xfail fails where its card says: C-12, U-08, D-21, D-44 and A-07 at Then 1; U-40 at Then 2; G-06 in the When call with TypeError, as the card says.
- One test was deleted: the first ITM-U-08. Its Then 3 called `links_of(ix)` without `db`. The tool kept it because the xfail stops at Then 1, but it would crash once BUG-938 is fixed.

Escalations and causes:
- **ITM-C-19 — runner fault, the card goes to Claude.** Then 4 is one filtered count (`count: items with workspace_id == W1.id and name == "Bolt M8" has exactly 2 rows`). The runner's "one assert per listed check" rule counts the two filter conditions as two checks and rejects the faithful single assert `count_rows(db, "items", workspace_id=w1.id, name="Bolt M8") == 2` every time. The runner was not edited. No other card has a `count:` line with two `==` filters.
- **ITM-UN-01 — sheet fault, fixed.** The model wrote the plain item as `mk_item("Hex Screw", unit="pcs", name_normalized="hex screw")`: positional, plus `unit` taken from the bracketed remark.

Changes after the trial:
1. Sheet: the plain-item row now says "both keywords, nothing positional".
2. Sheet: added "`links_of(IX) == []` -> `assert links_of(db, ix) == []` (every reading helper takes `db` first)".
3. `mk_item`: a non-recipe positional value raises a `TypeError` with the right form.
4. Sheet: merged the F1 / AC1 / WT1 rows to stay near 10k.

Left for the finishing step:
- ITM-L-08 keeps an unused `as exc` (ruff F841). The card has no `exc.value` line, so drop `as exc`, or tell the sheet that DataError cards without a further `raises:` line take no `as exc`.
- C-19 and the 9 `Author: claude` cards.

## Local-coder run (full)
Model Qwen3.6-35B-A3B Q4_K_M, n_ctx 16384, thinking off. 169 cards sent (trial and full run together; the 9 exemplars and the 9 `Author: claude` cards were not sent).
- Accepted first try: 143. Accepted after retry: 22 (17 on the 2nd attempt, 5 on the 3rd). Escalated: 4 (ITM-FS-11, D-17, D-33, D-47).
- ITM-C-19, handed back in the trial (P26), was accepted on the first try after the runner fix.

Escalations and causes — in all four the card is right and the model failed; the helper sheet already showed the right form each time:
- **ITM-FS-11 (pass) — model.** The model called `find_similar_items(limit=-1)` inside `pytest.raises(DataError)` without `db.begin_nested()` and then called `db.rollback()`. That rollback undoes the test's savepoint and the Given rows with it, so `reread(db, i1)` found nothing and the test failed. Attempt 2 was a syntax error. The sheet's "`raises: IntegrityError` / `DataError` -> the call inside `db.begin_nested()`" row was ignored. With the savepoint the card holds today: Postgres refuses `LIMIT -1` with a `DataError`.
- **ITM-D-17 (xfail BUG-948) — model.** The model skipped the Given line "MC1" and passed the factory as the machine (`mk_machine_stock(of=i1, machine=f1, qty=5)`). That fails the `machine_items.machine_id` foreign key in setup, before Then 1, so the runner refused all three attempts. The sheet has `mc1 = mk_mc1(factory=f1)`.
- **ITM-D-33 (pass) — model.** The model built WT1 as `mk_wo.__globals__['mk_wo']("Repair")` instead of `mk_wt1()`, three times. The runner's text check refused it each time. The sheet lists `mk_wt1` in the F1 / AC1 / WT1 row.
- **ITM-D-47 (xfail BUG-948) — model.** The model built both stock rows with a raw `Inventory(...)` and no `workspace_id` instead of `mk_stock(...)`, so a NOT NULL error came in setup. Attempt 1 also wrote a string that is not in the card. The sheet has `sk = mk_stock(of=i1, factory=f1, qty=400)`.

Helper sheet: not changed in the full run.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 195–204 | dead | `search_items` — listed as dead code in the spec's Not specified (item DAO spec Q4, on the dead-code removal checklist). |

Branch partials: 0. The two `hasattr(item_data, 'tag_ids')` checks (P9, dead branches) are conditional expressions / a one-line `if` whose false side coverage.py does not count separately.

## Factories added
None (the builders are local to this module; `make_workspace` / `make_profile` are reused).

## Notes for maintainers
- `mk_line` picks the table from the class of the order passed in. A new order type needs a branch in `_line_fields`.
- The order numbers (`PO-ITM-1`, `SO-ITM-1`, `WO-ITM-1`, `TR-ITM-1`) are fixed. Sales and transfer numbers are unique across all workspaces, which is fine because every test is rolled back and builds at most one order of each kind.

## Step D — finishing
Hand-written under `# [claude] <ID>` at the end of the file (after a `_commit_spy` helper):
- The 9 `Author: claude` cards:
  - C-29, C-30 (strict xfail BUG-946; a direct insert inside `begin_nested`; they fail at Then 1 with "DID NOT RAISE IntegrityError").
  - C-31 (pass).
  - C-32 (strict xfail BUG-946; the race patch; it fails at Then 1 with "DID NOT RAISE ValueError").
  - C-40, U-45, D-12, A-13 (pass; savepoint rollback and commit spy).
  - D-13 (pass; follow-up calls after the When).
- The 4 escalated cards, FS-11, D-17, D-33 and D-47, written from the cards unchanged. None of the four cards was wrong, so the cases file was not edited. D-17 and D-47 fail at Then 1 with "DID NOT RAISE ValueError", as their cards say.

Changes to local-model tests (cosmetic only):
- Dropped the unused `as exc` (ruff F841) in ITM-L-08, U-05 and D-04. The cards have no further `raises:` line, so no check was lost.
- Removed the stale `# noqa: F401` comments on three imports (ruff RUF100). The import of `Mock` and `patch` was added for the hand-written cards.
- `ruff check` on the file now passes. The file was not run through `ruff format`, because the scaffold and the delivered tests keep their long one-line calls.

Checks:
- **Fidelity of the local tests:** no local test was found unfaithful to its card. This was a mechanical sweep, not a line-by-line reading, which is the verifier's job:
  - every xfail was run with `--runxfail` and its failing line mapped to its `# Then N`;
  - `# Then` numbering was compared with each card;
  - the number of asserts per Then line was compared with the number of checks it lists;
  - ruff F841/F811 and an AST pass for unused fixture arguments found nothing (only the three `as exc` above).
- **xfail markers:** all 83 are strict, as the cards say (no card is non-strict). Every reason names the card's bug. Each one fails in the Then line its card's "Fails today on" names, on the right field and value. G-06, G-07 and G-08 fail in the When call with `TypeError` (no `include_deleted` parameter), which is what their cards' "Fails today on: Then 1" says.
- **Stability:** 8 whole-file runs, plus one run each with `PGOPTIONS="-c enable_seqscan=off"` and `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"` (checked that the setting reaches the test connection). All 10 runs ended 104 passed, 83 xfailed.
- **Coverage:** 96% with branches; only `search_items` (dead) is missed.
- **Cases summary counts:** no change needed (187 cases · 104 pass · 83 xfail; the file gives the same result).
- **Self-check:** every case ID is in exactly one test. No expected value was changed. The only mock is the C-32 race patch, plus the commit spies the rolled-back cards ask for. Every write case re-reads from the database. Nothing under `app/`, the spec or the cases file was modified.

## After verification (2026-10-18), main session
- Verifier: NEEDS WORK only for two missing cases (mutation survivors #36, #37). Added ITM-L-09 (default `limit` 100 of `list_items_filtered`) and ITM-FS-12 (default `limit` 5 of `find_similar_items`), both `Author: claude` (rows built in a loop) and passing. Counts now 189 tests · 106 passed · 83 xfailed.
- Spec gaps 4–6 (error order for an in-use item with an unknown user; a stock / order row in another workspace; cards for R9a's ledger / return / template / formula / project rows) stay open: they touch the stock and order workflow, so they wait for the owner.

## Revision 4 (2026-10-30) — ITM-D-48 … D-79
Stage 4, normal mode (not local-coder). 32 new `Author: claude` tests at the end of the file under `# [claude] ITM-D-NN`: 18 strict xfail BUG-948, 14 pass. Existing tests unchanged. Spec gaps 4–6 from the entry above are closed by this revision.

- **New builders**, next to the old ones, same keyword style; each inserts one row and flushes: `mk_f9()`, `mk_mc9(factory=)`, `mk_ac9()`, `mk_wt9()`, `mk_st9("X")` (a stage of W2), `mk_product(of=, factory=, qty=)`, `mk_pl1(factory=)`, `mk_pl9(factory=)`, `mk_batch(line=, status=)`, `mk_batch_line(of=, batch=)`. `mk_batch_line` takes the batch by name instead of remembering "the last batch built"; the value is the same.
- **Rows of W2:** the old builders already accept `workspace_id=w2.id` as a "but" keyword, so no old builder changed.
- **R9a rows** have no builder: the Given line lists every column, so the test calls `_add(db, Model(...))` with those columns and reads like the card. Their classes are imported at the top of the file.
- **`item_manager.helpers.md`:** not changed. All 32 cards are `Author: claude`, so the local model never needs these builders. Regenerate the sheet only if one of them goes to the local model.
- **Given lines that only state a fact** (D-55 line 6, D-57 line 4, D-58 line 5): no row is built, and a `# Given N` comment says so.

Checks:
- **Counts:** 8 whole-file runs, all 120 passed, 101 xfailed: 6 plain, one with `PGOPTIONS="-c enable_seqscan=off"`, one with `PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off"` (checked with `SHOW` that the setting reaches a connection). The numbers match the cases file. A coverage run gives the same. Coverage is 96% with branches; only `search_items` (195–204, dead) is missed, so no new gap. The new tests add no covered line: `delete_item` has no blocking code yet.
- **Strict xfails:** with `--runxfail` the 18 new xfails fail inside `# Then 1`: 17 with `DID NOT RAISE ValueError`, and D-48 with `IntegrityError` on `items_updated_by_fkey`, raised at `app/managers/item_manager.py:315` (the write). A script confirmed every xfail in the file is strict and names a bug from its card: BUG-948 has 38, as in the Reviewer summary.
- **D-48 teardown:** no savepoint, and the fixture copes today. The failed flush leaves the session needing a rollback, and the fixture's `session.close()` then `outer.rollback()` handle that. It passes with `-W error`, the test database still has 0 rows in the tables counted before and after, no connection stays idle in a transaction, and the tests after it run normally in all 8 whole-file runs.
- **Lines after Then 1 never run today**, so they were run against a stand-in fix: a scratch pytest plugin, outside the repo, that patches `ItemManager.delete_item` at run time with R9 (a)–(h), R9b and R10a. `app/` was not edited, and the plugin is not kept. Every `delete_item` test ran with `--runxfail`: all 38 BUG-948 tests and all pass cards passed, including D-48 with the checks that prove the transaction stays usable. Only D-05 (BUG-941) and D-09 (BUG-945) failed, and neither bug was part of the stand-in.
- **Wrong fixes are caught by the cards meant to catch them** (same plugin, beyond D-05 and D-09):
  | Wrong fix | Fails |
  |---|---|
  | Rows filtered on the item's workspace | D-49 … D-54, D-56, D-69, D-73 |
  | "Complete" stage looked up in the item's workspace | D-55 only |
  | Alphabetical type order | D-56, D-75 |
  | Refusal raised after the write and flush | every BUG-948 card, D-48 among them |
- **Mechanical:** a script matched each of the 221 cards to one test (id, title, `# Then` numbers for the new cards, marker, unused arguments and variables). `ruff check` passes. Line endings are still LF.

## Discrepancies (revision 4)
None. bugs.md not changed: no new defect found.

## Notes for maintainers (revision 4)
- The R9a cards, D-55 and D-76 … D-79 pass today only because `delete_item` reads none of these rows. They begin to test something when the BUG-948 fix lands; run them then.
- R9 (c) says "status rows of the workspace, matched by exact name", while the R9 intro says no `workspace_id` is compared on the stage row. The intro rules, and D-55 pins it. A fixer who reads only (c) would write the "wrong fix" of D-55.
- D-48 has an unbounded strict xfail: it would also pass as xfail for another exception in the call, because the marker has no `raises=` (the convention writes none). The Then 1 check under `--runxfail` is what shows the reason.
- `batch_number` is unique per workspace, so D-75 gives its second batch `"PB-ITM-2"`, as the card says.

## Revision 5 (2026-10-30) — ITM-D-80 … D-86, D-48 changed
Stage 4, normal mode. 7 new `Author: claude` tests at the end of the file under `# [claude] ITM-D-NN`: D-80, D-81, D-84, D-85, D-86 strict xfail BUG-948; D-82, D-83 pass. D-48 changed as its card says: new Then 4 (`i1 not in db.dirty`) and Then 5 (`db.flush() is None`), both before any re-read; the old Then 4 … 8 are now Then 6 … 10. No other existing test changed. The verifier's scratch test was only a starting point; each test follows its card.

- **Column names read from the models** (Spec gap 9):
  - D-85: `app/models/production_batch_item.py` has three quantity columns, `expected_quantity`, `actual_quantity` and `variance_quantity`, all set to 0. `variance_percentage` is a percentage, not a quantity, so it stays NULL.
  - D-86: `app/models/factory.py` and `app/models/machine.py` both have `is_deleted` and `is_active`. F1 and MC1 both get `is_deleted=True`, `is_active=False`, as the card says. Since revision 8, D-86 is a pass card: stock with a deleted parent does not block (see the revision 8 section).
- **New builders:** `mk_f1_deleted()` and `mk_mc1_deleted(factory=)`. `mk_f1` and `mk_mc1` take no "but" keywords and were left alone. `item_manager.helpers.md` is still unchanged.

Checks:
- **Counts:** 7 whole-file runs, all 122 passed, 106 xfailed, which matches the cases file: 5 plain and one under each forced plan. Coverage is unchanged at 96% with branches; only `search_items` (195–204, dead) is missed. `ruff check` passes, line endings are LF. A script matched each of the 228 cards to one test, and BUG-948 now has 43 strict xfails.
- **Strict xfails:** with `--runxfail`, D-80, D-81, D-84, D-85 and D-86 fail inside `# Then 1` with `DID NOT RAISE ValueError`. D-48 still fails inside Then 1 with `IntegrityError` on `items_updated_by_fkey`.
- **Reference plugin:** the verifier's `ref948.py` (scratch, written from the spec; it also fixes BUG-941 and BUG-945) was used to run the lines after Then 1. With `--runxfail`, all 86 `delete_item` tests pass, so D-48's new Then 4, 5 and renumbered lines hold and every new card holds.
- **Wrong fixes in that plugin, and the cards that catch each one:**
  | Wrong fix | Fails |
  |---|---|
  | `mix_a_row_factory`, `mix_b_row_machine`, `mix_g_row_factory`, `mix_h_line_batch` | D-80 only |
  | `mix_c_line_order`, `mix_c_order_stage`, `mix_d_line_order`, `mix_e_line_order`, `mix_f_line_order` | D-81 only |
  | `mix_c_stage_lookup` | D-82 only |
  | `o_ws_only` | D-83 only |
  | `o_before_ws` | D-36, D-83 |
  | `ret_po_exempt`, `ret_so_exempt` | D-84 only |
  | `h_in_out_only`, `h_qty_zero_skips` | D-85 only |
  | `a_factory_live`, `b_machine_live`, `g_factory_live` | D-86 only |
  | `r_dirty`, `r_write_first`, `r_broken_tx`, `r_rollback`, `r_skip_unknown` | D-48 only |
  `r_dirty` fails at the new Then 4, the case revision 5 added it for. `r_savepoint` (the write tried in a savepoint, then the refusal) passes D-48: it leaves nothing written and the transaction usable, so R10a holds.

## Discrepancies (revision 5)
None. bugs.md not changed: no new defect found.

## Revisions 6 and 7 (2026-10-30) — `other_workspace`, ITM-D-87 … D-98
The owner corrected gap 5: a cross-workspace row still blocks, but shows only as one `{"type": "other_workspace"}` entry, no id, last. This replaces "by item id only" wherever the sections above say it, including their wrong-fix tables for D-49 … D-56, D-69, D-73, D-80 and D-81.

- **Changed tests:** D-49 … D-54, D-56, D-69, D-73, D-80, D-81 have the new title, Rules line and function name, and Then 3 is exact equality on the card's list. D-56 now expects `factory_stock` SK1, `work_order`, then the generic entry.
- **D-81 Given:** one W1 stage "Draft" for all four orders; the W2 stage and the second stage are gone.
- **D-80:** `sk`, `ms` and `pr` are no longer assigned, since Then 3 no longer names them.
- **Rules lines only:** D-11, D-55, D-82.
- **New tests:** D-87 … D-90 and D-92 … D-98 are strict xfail BUG-948; D-91 passes. Under `# [claude] ITM-D-NN`, no new builder. `item_manager.helpers.md` unchanged.

Checks:
- **Counts:** 5 whole-file runs, all 123 passed, 117 xfailed, which matches the cases file: 3 plain and one under each forced plan. A coverage run gives the same. Coverage is unchanged at 96% with branches; only `search_items` (195–204, dead) is missed. `ruff check` passes, line endings are LF.
- **Card match:** a script matched each of the 240 cards to one test, and every docstring Rules line in the file equals its card. BUG-948 now has 54 strict xfails.
- **Strict xfails:** with `--runxfail`, all 25 new or changed xfails fail on the `with pytest.raises` line under `# Then 1` with `DID NOT RAISE ValueError`.
- **Reference plugin:** a scratch copy of the verifier's `ref948.py` (original untouched) sorts blockers into normal entries and one generic entry, line by line. With it and `--runxfail`, all 98 `delete_item` tests pass, so every Then line of the new and changed cards has run.
- **Wrong fixes in that copy, and the cards that catch each one:**
  | Wrong fix | Fails |
  |---|---|
  | Cross-workspace rows listed as normal entries | all 21 cards that expect the generic entry |
  | Generic entry carries an id | the same 21 |
  | Factory stock rows dropped | D-49, D-92 |
  | Machine stock rows dropped | D-50, D-93 |
  | `products` rows dropped | D-69, D-94 |
  | Purchase order rows dropped | D-51, D-87, D-89 |
  | Sales order rows dropped | D-52, D-95 |
  | Work order rows dropped | D-53, D-96 |
  | Transfer order rows dropped | D-54, D-97 |
  | Batch rows dropped | D-73, D-88, D-98 |
  | Only the line's workspace compared | D-87, D-88 |
  | Only the order's workspace compared | D-80, D-81, D-89, D-95 … D-98 |
  | One W2 line makes the whole order generic | D-89 |
  | Generic entry first | D-56, D-89 |
  | One generic entry per row | D-56, D-80, D-81 |
  | Stage or factory counted as cross-workspace | D-90 |
  | W2 row at quantity 0 blocks | D-91 |

## Discrepancies (revision 7)
None. bugs.md not changed: no new defect found.

## Revision 8 (2026-10-31) — deleted parents, verification round 6, ITM-D-99 … D-133
Owner's answer: stock with a deleted parent does not block. "Deleted" means `is_deleted`; a parent that is only deactivated still blocks. Open orders and batches tied to a deleted factory still block. This replaces what the sections above say about D-86: it is now a pass card, so the lines calling it an xfail, and `a_factory_live`, `b_machine_live`, `g_factory_live` as wrong fixes, are history.

- **D-86:** no xfail, `result = M.delete_item(...)`, new title, function name, Rules and Then lines. The `mk_f1_deleted` and `mk_mc1_deleted` builders and their `# Card ITM-D-86` comments stay; the comments already match the card's Given.
- **New tests:** 35 under `# [claude] ITM-D-NN`. D-99 … D-102, D-104 … D-114 and D-123 … D-126 pass (19). D-103, D-115 … D-122 and D-127 … D-133 are strict xfail BUG-948 (16). The title, Rules, When and Then lines were generated from the card text, so no expected value was retyped; only the Given lines are hand-written.
- **Builders:** `mk_f1`, `mk_mc1`, `mk_f9` and `mk_mc9` now take "but" keywords (`mk_f1(is_deleted=True)`). Their defaults did not change, so the old calls and `item_manager.helpers.md` still hold. F2 of D-115 is `mk_f1(name="Side Plant", abbreviation="SP", is_deleted=False)`.
- **New row combinations D-115, D-116 and D-127:** all three build and reach the call, with no constraint in the way, and all three pass on the reference plugin.

Checks:
- **Counts:** 5 whole-file runs, all 143 passed, 132 xfailed, which matches the cases file: 3 plain and one under each forced plan. A coverage run with a private `COVERAGE_FILE` gives the same. Coverage is unchanged at 96% with branches; only `search_items` (195–204, dead) is missed. `ruff check` passes, line endings are LF.
- **Card match:** a script matched each of the 275 cards to one test, and every docstring Rules line equals its card. BUG-948 now has 69 strict xfails.
- **Strict xfails:** with `--runxfail`, all 16 new xfails fail inside `# Then 1`: 15 with `DID NOT RAISE ValueError`, and D-133 with `IntegrityError` on `items_updated_by_fkey`, as its card says.
- **Reference plugin:** a scratch copy of the verifier's `ref6.py` (original untouched) adds deleted parents. With it and `--runxfail`, all 133 `delete_item` tests pass, so every Then line has run.
- **Wrong fixes in that copy, and the cards that catch each one:**
  | Wrong fix | Fails |
  |---|---|
  | Deleted factory ignored for `inventory` | D-86, D-99, D-104 … D-106, D-115 |
  | Deleted factory ignored for `products` | D-86, D-100, D-107 … D-109, D-115 |
  | Deleted machine ignored | D-101, D-110 … D-112 |
  | Factory of the machine ignored | D-102, D-113 … D-115 |
  | Same, for cross-workspace rows only | D-104, D-105, D-115 (inventory); D-107, D-108 (products); D-110, D-111 (machine); D-113 (factory of the machine) |
  | `is_active False` also counts as deleted | D-103 |
  | Needs `is_deleted` and `is_active False` | D-99 … D-102, D-104 … D-115 |
  | Parent of another workspace not followed | D-104, D-106, D-107, D-109, D-110, D-112 … D-115 |
  | Orders and batches of a deleted factory stop blocking | D-116 |
  | W1 line on W2 sales, work, transfer order dropped | D-117, D-118, D-119, one each |
  | `replaced_item_id` line shapes dropped | D-120, D-121, D-122, one each |
  | A cross row blocks in a non-blocking state | D-123 (stock), D-124 (purchase, sales, transfer), D-125 (work), D-126 (batch) |
  | W1 row on a W2 machine, factory, account, type, stage or line treated as cross | D-127 |
  | One W2 line hides the normal entry, or the reverse | D-128 … D-131, one per type |
  | Generic entry before another type | D-132, with D-130 or D-131 |
  | Only-generic refusal skipped for an unknown user | D-133 |

## Discrepancies (revision 8)
None. bugs.md not changed: no new defect found.
