# Verification — `app/managers/item_manager.py`

> **Verdict:** PASS (round 7, 2026-10-31) — all 7 findings of round 6 are closed, and the deleted-parent rule is covered. The module is closed. Spec gaps 8 and 9 stay open, non-blocking. Details in "Round 7" just below.
> Tests: 143 passed · 132 xfailed (reproduced ✅) · coverage 96% branch (only dead `search_items`, 195–204, missed)
> Mutation (`delete_item`, lines 290–323, from round 6, not re-run; reason in Round 7): 19 mutants · 17 killed · 2 survived → score 100% (17 / 17, after excluding 0 equivalent, 0 dead, 2 bug-path)
> Hand variants, round 7: 123 · 122 caught · 1 survived (a further shape, not a rule gap)
> Source commit: e48a092 · Cases revision: 8 (275 cases; spec APPROVED, owner's answers on deleted parents, 2026-10-30 and 2026-10-31)
> Round 6 (2026-10-31): NEEDS WORK — 7 case gaps, 54 variants survived; all closed by revision 8. 240 tests · 123 passed · 117 xfailed.
> Round 5 (2026-10-30): PASS, on cases revision 5, now superseded. 228 tests · 122 passed · 106 xfailed.
> Round 4 (2026-10-30): NEEDS WORK — one gap: D-86 kept F1 `is_active True`. The 7 new tests and the D-48 change were faithful to their cards.
> Round 3 (2026-10-30): NEEDS WORK — 6 case gaps; all 6 are closed by revision 5 (one only in part, see Round 4). 221 tests · 120 passed · 101 xfailed; 117 variants, 20 survived.
> Round 2 (2026-10-18): PASS — round 1 was NEEDS WORK for two missing cases; ITM-L-09 and ITM-FS-12 added (`Author: claude`), survivors #36 and #37 now killed (mutation re-run on lines 211-275: 8 of 8 killed). 189 tests · 106 passed · 83 xfailed.
> Round 1: NEEDS WORK (two small case gaps for the case designer; every test-side finding is fixed and re-run). The lines below are round 1's.
> Tests: 104 passed · 83 xfailed (reproduced ✅) · coverage 96% branch (96 statements, 36 branches, 0 partial; 3 missed lines = dead `search_items`)
> Mutation: 91 mutants · 75 killed · 16 survived → score 97% (75 / 77, after excluding 2 equivalent, 6 dead, 6 bug-path; 2 `case-missing` remain)
> Source commit: e48a092 · Cases revision: 2 (READY, spec APPROVED 2026-10-18, 187 cases)

## Round 7 (2026-10-31) — scoped to cases revision 8: D-86, ITM-D-99 … D-133

**Verdict: PASS. The module is closed.**

- **Read line by line:** D-86 and the 35 new tests match their cards: every Given row and column, When and Then line, in order. `mk_f1`, `mk_mc1`, `mk_f9` and `mk_mc9` take "but" keywords with their defaults unchanged, so older calls build the same rows. No finding, and no test was edited.
- **Round 6 survivors:** all 54 now fail, on the right card:

| Round 6 finding | Variants | Now fail |
|---|---|---|
| 1. W1 line on a W2 sales, work, transfer order | 6 | D-117, D-118, D-119 (T1, T3) |
| 2. `replaced_item_id` lines, three shapes | 6 | D-120, D-121, D-122 (T1, T3) |
| 3. Cross rows in non-blocking states | 12 | D-123 (stock), D-124 (purchase, sales, transfer), D-125 (work), D-126 (batch), in the call |
| 4. W1 rows on W2 parents | 18 | D-127 T3 |
| 5. Lines judged one at a time | 8 | D-128 … D-131 T3, one per type |
| 6. Generic entry always last | 3 | D-132 T3, with D-130, D-131 |
| 7. Unknown user, only the generic entry | 1 | D-133 T1 |

  `s_to_before_wo`, the regression from revision 6, now fails D-116, D-127 and D-132.

- **Deleted parents (R9 (a), (b), (g)):** my reference now follows them. It passes all 133 `delete_item` tests. One variant for each state keeps that state blocking:

| State (row workspace / parent workspace) | Fails |
|---|---|
| (a) factory stock: W1/W1, W2/W2, W2/W1, W1/W2 | D-99 and D-86, D-104, D-105, D-106 |
| (g) products: W1/W1, W2/W2, W2/W1, W1/W2 | D-100 and D-86, D-107, D-108, D-109 |
| (b) deleted machine: W1/W1, W2/W2, W2/W1, W1/W2 | D-101, D-110, D-111, D-112 |
| (b) live machine of a deleted factory: W1/W1, W2/W2, W1/W2 | D-102, D-113, D-114 |
| (b) W2 row on a live W1 machine of a deleted W1 factory | **none** |
| state ignored for cross rows only | 8 cards, D-104 … D-115 |
| `is_active False` counted as deleted, each of 4 parents | D-103 T3 |
| `is_deleted` and `is_active False` both required, each of 4 parents | D-99 … D-102, D-104 … D-115 by parent |
| orders or batches of a deleted factory stop blocking, each of 5 kinds | D-116 T3 |

- **The one survivor is not a finding.** `pblock:bf_W2_W1` is a further shape of covered rules: the same state has cards for W1/W1, W2/W2 and W1/W2, and the same mixed shape has D-111 for a deleted machine. The spec's Notes do not list it as built. Only a fix that singles out this one combination would pass.
- **Then lines:** all 169 lines of the 36 cards pass on the reference, and each was made to fail on its own line. Then 1 of the xfails fails today.
- **Also read as no-ops:** 7 per-row write entries found no such row in any card (for example a third order line), so they test nothing and are not counted.

**Reproduced:** 143 passed, 132 xfailed, 96%, only 195–204 missed. `--runxfail` 132 failed, 143 passed. All 132 xfails fail on the card's line, including the 16 new ones. Traceability is clean for all 275: one test per card, titles, Rules lines, markers, `# Then N`. BUG-948 has 69 strict xfails. No flaky test: 4 plain runs (2 with planner settings), 1 coverage run and 2 `--runxfail` runs. `ruff check` passes. All 36 tests are Claude-written, so no local-coder note applies. The coverage run used a private `COVERAGE_FILE`.

**Mutation not re-run.** The source is unchanged. Outside the scope no card changed, and the builders' defaults did not. D-86 moved from xfail to pass and 19 new tests pass, and added passing tests can only kill more. Round 6's result stands: 17 of 17, with #13 and #14 bug-path (BUG-941).

**Round 6's open items:** `item_manager.notes.md` line 155 is corrected. `s_w1_first` stays retired, and `r_savepoint` and `r_savepoint_all` stay equivalent.

**Open, non-blocking:**
- **Spec gap 8:** `product_ledger`, `project_component_item_ledger`, `sales_delivery_items` and `invoice_items.item_id` wait for the owner; no card until then.
- **Spec gap 9:** the spec does not name the quantity or soft-delete columns. The tests read them from the models and are right.
- **All R9 behaviour is still unproven against real code:** 69 strict xfails wait for the BUG-948 fix. These variants and the reference are scratch only, so run the whole file when the fix lands.
- "Unchanged" for tests outside the scope is still shown indirectly.

Scratch, under `<scratchpad>/itmv7/`: `plug/ref7.py`, `drive7.py`, `variants7.txt`, `audit7.py`, `res/`.

Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

---

## Round 6 (2026-10-31) — scoped to cases revisions 6 and 7: the reversed cross-workspace rule

Scope: D-49 … D-54, D-56, D-69, D-73, D-80, D-81 and D-87 … D-98 read line by line against their cards, and the Rules lines of D-11, D-55, D-82 (26 tests); spec `delete_item` R9 intro, R9b, Errors, Notes "Cross-workspace rows", Gap log G5.

### Summary
- **The 26 tests match their cards.** Every Given row and column, When and Then line, in order. No test-side finding, and no test was edited.
- **Why the verdict is NEEDS WORK:** the revised rule covers all order types and all states, but several cards cover it for one type only. A wrong fix limited to one type or state passes every test. 54 of my 123 variants survive, in 7 gaps.
- **The two gaps that matter most:**
  - **Finding 1:** a W1 line on a W2 sales, work or transfer order has no card. A fix can list that W2 order's real id, which is the leak the owner ruled out ("exposes nothing of the other workspace").
  - **Finding 3:** the "does not block" states are checked for cross-workspace rows in only 2 of 14 states. A fix with a separate "any row of another workspace" query refuses deletes it should allow.
- **All 54 are closable.** 14 scratch tests pass on the reference, and every survivor fails at least one of them.
- **Why the executor's 17 wrong fixes did not show this:** all 17 behave as the notes say, but most act on every type at once, so the one card that exists for one type is enough to catch them. `cx_line_only` is caught by D-87 and D-88 only, and with those two types excepted it would pass.
- **Mutation:** the false-kill doubt is cleared. All 17 kills are real test failures (`1 failed`), none error-only. As in round 3, `delete_item` has no blocking code yet, so this score says nothing about R9.

### Findings (all `case-missing`, rules already in the spec)
| # | Rule | What is wrong | Variants that survive | Closes it (scratch test, passes on the reference) | Fix by |
|---|---|---|---|---|---|
| 1 | R9 intro: "for (c)–(f) and (h), a line whose order or batch has a `workspace_id` that differs" | D-87 and D-88 cover a W1 line on a W2 order for (c) and (h) only. Nothing covers (d), (e), (f). `normal:` lists the W2 order's real id in the refusal. | `drop:` and `normal:` of `d_L1O2`, `e_L1O2`, `f_L1O2` (6) | 3 tests, one per order type | **case designer** |
| 2 | R9 (e) with the R9 intro: a line naming the item by `replaced_item_id` | No cross-workspace card has a `replaced_item_id` line. A fix can judge `item_id` lines only. | `drop:` and `normal:` of `e_repl_L2O2`, `e_repl_L1O2`, `e_repl_L2O1` (6) | 3 tests, one per shape | **case designer** |
| 3 | R9 intro: "a cross-workspace row blocks and does not block in exactly the states (a)–(h)"; Notes | Only `qty 0` of (a) (D-91) and stage `Complete` of (c) (D-55) are covered. | `nostate:` of `a_deleted`, `b_qty0`, `c_voided`, `d_completed`, `e_line_deleted`, `e_order_deleted`, `e_closed`, `f_completed`, `g_deleted`, `g_qty0`, `h_completed`, `h_cancelled` (12) | 1 pass test, all 12 states on one item | **case designer** |
| 4 | R9 intro: "The factory, machine, stage or production line a row points at is not part of this test" | D-90 and D-82 cover stock on a W2 factory and a purchase order on a W2 stage only. A W1 row on any other W2 parent has no card. | `parent:` and `parentdrop:` of `b_machine`, `g_factory`, `h_line`, `d_factory`, `d_account`, `d_stage`, `e_factory`, `e_type`, `f_stage` (18) | 1 test, W1 rows on all those parents | **case designer** |
| 5 | R9b: "Lines are judged one at a time" | D-89 covers purchase orders only. | `whole:` and `normalwins:` of `sales_order`, `work_order`, `transfer_order`, `production_batch` (8) | 4 tests, one per type. One combined test does **not** work: another type's generic entry hides the missing one. | **case designer** |
| 6 | R9b sort: generic entry "always last"; normal types in the listed order | D-56 and D-89 have no normal `transfer_order`, `product_stock` or `production_batch` entry with a generic one. **Regression from revision 6:** D-56's transfer order became W2, so no card now holds a normal work order and transfer order together, and `s_to_before_wo` survives. | `gen_before_transfer`, `gen_before_product`, `gen_before_batch` (3), plus `s_to_before_wo` on the executor's plugin | 1 test: work order, transfer order, products row, batch and a W2 row | **case designer** |
| 7 (low) | R10a: "Same `ValueError` and blocker list"; Errors row 5 | D-48 has a normal blocker. No card has an unknown user with only a cross-workspace row. | `r_generic_skips_unknown` (1) | 1 test | **case designer** |

Finding 6 also corrects the cases file's picture of D-56: it no longer guards the order of work and transfer orders.

Nothing here needs an owner decision. Parents `account` and `work_order_type` in finding 4 are not named in R9, but the definition of a cross-workspace row does not include them either. Spec Notes list a W1 line on a W2 order as verified only for purchase orders and batches; the scratch tests show it builds for the other three, so the spec's list could be widened.

### Variants
Reference and variants are mine (`itmv6/plug/ref6.py`), written from the spec. Each row is classified by shape, so one variant changes one shape, state or parent. `--runxfail`, 98 `delete_item` tests. Reference: **98 passed**. "T" = Then line.

**One shape, per type: dropped, then listed as a normal entry**
| Shape | `drop:` fails | `normal:` fails |
|---|---|---|
| (a) W2 row on W2 / W1 factory | D-49 T1 / D-92 T1 | D-49, D-56 T3 / D-80, D-92 T3 |
| (b) W2 row on W2 / W1 machine | D-50 T1 / D-93 T1 | D-50 T3 / D-80, D-93 T3 |
| (g) W2 row on W2 / W1 factory | D-69 T1 / D-94 T1 | D-69 T3 / D-80, D-94 T3 |
| (c) line and order W2 | D-51 T1 | D-51 T3 |
| (c) W1 line, W2 order | D-87 T1 | D-87 T3 |
| (c) W2 line, W1 order | D-89 T3 | D-81, D-89 T3 |
| (d) line and order W2 | D-52 T1 | D-52 T3 |
| (d) W2 line, W1 order | D-95 T1 | D-81, D-95 T3 |
| (e) line and order W2 | D-53 T1 | D-53 T3 |
| (e) W2 line, W1 order | D-96 T1 | D-81, D-96 T3 |
| (f) line and order W2 | D-54 T1 | D-54, D-56 T3 |
| (f) W2 line, W1 order | D-97 T1 | D-81, D-97 T3 |
| (h) line and batch W2 | D-73 T1 | D-73 T3 |
| (h) W1 line, W2 batch | D-88 T1 | D-88 T3 |
| (h) W2 line, W1 batch | D-98 T1 | D-80, D-98 T3 |
| (d), (e), (f) W1 line, W2 order; (e) by `replaced_item_id` | **none: findings 1, 2** | **none: findings 1, 2** |

**Other variants caught**
| Variant | Failed by |
|---|---|
| all cross rows listed as normal | the 21 cards that expect the generic entry, T3 |
| all cross rows ignored | the same 21, T1 or T3 |
| generic entry with an id / extra key / other type name | the same 21, T3 (each) |
| generic alone: ignored / other message / one arg | 19 cards, T1 / T2 / T3 |
| generic first | D-56, D-89 T3 |
| one generic per row | D-56, D-80, D-81 T3 |
| only the line's workspace compared | D-87, D-88 T3 |
| only the order's workspace compared | D-80, D-81, D-89, D-95 … D-98 T3 |
| cross rows ignore every state | D-55, D-91 in the call |
| only `qty 0` / only `Complete` ignored | D-91 / D-55 in the call |
| W1 row on W2 factory or W1 order on W2 stage: generic, or dropped | D-90 T3 (each) |
| one line at a time, purchase orders | D-89 T3 |
| other-workspace item in use gets the generic refusal | D-83 T2 |

**Executor's 17 wrong fixes (`rev7plug/ref948.py`, run on a copy):** its reference passes all 98, and all 17 fail exactly the cards in the notes' table.

**Older non-cross variants, on the executor's plugin:** 101 run, 97 fail a card.
- `s_to_before_wo` no longer fails anything (finding 6).
- `s_w1_first` no longer means anything: W2 stock is not listed now. Retired.
- `r_savepoint`, `r_savepoint_all`: equivalent, as ruled in Round 4.
- 19 of the 101 differ from round 4 in which cards fail. Other than the two above, each still fails a card. Some now fail at Then 1, an artefact of that plugin: its cross-workspace step crashes on the wrong ids those variants pass in.

### Then lines the xfails never reach
The 23 xfails in scope plus D-91 have **102 Then lines after Then 1**. All pass on the reference. D-48's were each made to fail in round 4. Every other line was made to fail on its own line in this round: `bw_active`, `bw_stamp` (T4), `bw_stock_*`, `bw_line_*` (the unchanged lines, including D-56, D-89, D-90 T5 and T6), `msg_all` (T2), `ok_no_stamp`, `ok_stock` (D-91).

### Reproduced claims
- Notes' Result line matches: 123 passed, 117 xfailed, 96%, only 195–204 missed. BUG-948 has 54 strict xfails.
- All 117 xfails fail on the card's line.
- Traceability clean for all 240: one test per card, titles, Rules lines, markers, `# Then N` numbers. D-11, D-55, D-82 Rules lines equal their cards. `ruff check` passes. Nothing is mocked in the 26. No test is local-written, so no local-coder note applies.
- No flaky test: 5 plain runs (2 with planner settings) and 2 `--runxfail` runs.

### Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 13, 14 | 307 | the "does not belong to workspace" message emptied | bug-path (BUG-941) | As in rounds 1 and 3. D-83's checks are met by an emptied message too. | — (resolves with BUG-941) |

Score: 17 / (19 − 2 bug-path) = **100%**. Raw 89%.

### Open
- The 7 findings above.
- Spec gaps 8 and 9, as in Round 5.
- `item_manager.notes.md` line 155 still says F1 "keeps `is_active` True".
- **Unexplained, scratch only:** 2 scratch-test runs ended in `1 error` at about 0.34 s, on different variants. It did not come back in 12 repeats and I did not find the cause. Those two variants were then killed on re-run. All 123 variant runs on the real test file recorded their 98 tests.
- "Unchanged" for tests outside the scope is still indirect. Outcomes, markers and numbering all hold.

### Commands run (round 6)
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/item_manager.py tests/unit/managers/test_item_manager.py --lines 290-323 --timeout 300 --json <scratchpad>/itmv6/mut.json
  Mutants: 19 · killed 17 · timeout 0 · survived 2 (raw 89%)    SURVIVED #13 #14 (L307)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --cov=app.managers.item_manager --cov-branch --cov-report=term-missing -rX
  app\managers\item_manager.py      96      3     36      0    96%   195-204
  123 passed, 117 xfailed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider -rX     (twice)
  123 passed, 117 xfailed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --runxfail
  117 failed, 123 passed

PGOPTIONS="-c enable_seqscan=off" | "-c enable_indexscan=off -c enable_bitmapscan=off"
  123 passed, 117 xfailed   (each)

git diff --stat app/managers/item_manager.py     (empty)
```
Scratch, under `<scratchpad>/itmv6/`: `plug/ref6.py`, `drive6.py`, `variants6.txt`, `finish6.txt`, `final6.txt`, `prop/test_prop6.py`, `mut.json`, `mut.log`.

Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

---

## Round 5 (2026-10-30) — scoped to the D-86 change

**Verdict: PASS. The module is closed.** D-86 Given 2 now reads "F1, but `is_deleted True`, `is_active False`", and `mk_f1_deleted` sets `is_active=False`.

| Run (`--runxfail`, 86 `delete_item` tests) | Result |
|---|---|
| reference | 86 passed, D-86 among them |
| `a_factory_active` | D-86 T2 only; 85 passed |
| `g_factory_active` | D-86 T2 only; 85 passed |

- Today's code: D-86 still fails at Then 1 with `DID NOT RAISE ValueError`, as its card says. Whole file: 122 passed, 106 xfailed; `--runxfail` 106 failed, 122 passed. `ruff check` passes. `git diff --stat app/managers/item_manager.py` is empty.
- Survivors now: `r_savepoint` and `r_savepoint_all` (equivalent, rulings in Round 4), and mutants #13, #14 (bug-path, BUG-941). No `case-missing` remains.
- Run in this round: only the reference and the 2 variants, as scoped. The other 131 results are from round 4. The change adds one column to one row of one card, so they cannot depend on it, except that `a_factory_live` and `g_factory_live` still rest on `is_deleted True`, which stayed.
- Mutation not re-run: the source is unchanged and D-86 is xfail, so the tool never runs it.

**Fix by the verifier (test file, comment only):** the comment above `mk_f1_deleted` still quoted the old card line; it now quotes the new one. No check changed.

**Open, non-blocking:**
- **Spec gap 8:** `product_ledger`, `project_component_item_ledger`, `sales_delivery_items` and `invoice_items.item_id` wait for the owner; no card until then.
- **Spec gap 9:** the spec does not name the quantity or soft-delete columns. The tests read them from the models and are right.
- **Executor, wording only:** `item_manager.notes.md` line 155 still says F1 "keeps `is_active` True". The cases file's revision header does not mention the D-86 change.

Limits from rounds 3 and 4 still apply: "unchanged" for the earlier tests is shown indirectly, and later Then lines of the non-delete xfails last ran in round 2.

---

## Round 4 (2026-10-30) — scoped to revision 5: ITM-D-80 … D-86 and the D-48 change

### Summary
- **The 7 new tests and the D-48 change match their cards**, line by line: every Given row and column, the When, and every numbered Then in order. The two new builders match their card lines (`mk_f1_deleted`: `is_deleted=True` only; `mk_mc1_deleted`: `is_deleted=True`, `is_active=False`). D-85 sets all three quantity columns of the model (`expected_quantity`, `actual_quantity`, `variance_quantity`).
- **All 19 `case-missing` variants of round 3 now fail, each on the right card** (table below). None fails anywhere else except where another card also legitimately catches it.
- **One gap remains, and it comes from my own round 3 finding 5.** My factory variants filtered `is_deleted` only, and I worded the finding as "a deleted factory". R9 (a) and (g) say the factory's own state is not looked at, and that includes `is_active`. D-86 sets `is_active False` on the machine but not on the factory, so `a_factory_active` and `g_factory_active` survive. `b_machine_active` is caught.
- **Verdict stays NEEDS WORK under the same standard as rounds 1 and 3:** a written rule with a variant no test notices. The fix is one column, so the next round needs only a re-run of those variants.

### Finding
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | R9 (a), (g) "the factory's own state is not looked at" | D-86 Given 2 is "F1, but `is_deleted True`": `is_active` stays True, so a fix that joins factories on `is_active` passes every test and lets an item with stock be deleted. | `a_factory_active`, `g_factory_active` survive. A scratch D-86 with `is_active False` on F1 passes on the reference and fails on both (`prop/test_prop4.py`). | **case designer**: D-86 Given 2 "F1, but `is_deleted True`, `is_active False`". **Executor**: add `is_active=False` in `mk_f1_deleted`. |

No test-side finding. No test was edited: the test follows its card, so the change starts at the card.

### Rulings asked for
- **`r_savepoint`: equivalent.** The variant checks the blockers, tries the write inside a savepoint, lets the FK error roll that back, then raises the correct refusal. Afterwards I1 is persistent and clean, the session is active, nothing is written, and the error is identical. R10a's wording "before any write" is broken only inside a savepoint that leaves no trace; the only difference is a failed statement in the database log. `r_savepoint_all`, the same idea on every path (write, then refuse and undo), also passes all 86 tests, for the same reason. No test should chase this, and no statement recorder is called for.
- **`r_broken_tx` and `r_rollback` failing D-48 with `TypeError`: acceptable.** Both now fail at Then 6 in `reread` → `_id_of`, with `TypeError: 'NoneType' object is not subscriptable`.
  - Cause: both fixes lose the transaction, which removes the Given rows, so I1 becomes transient with no identity (probe: `identity None`, `transient True`; on the reference `persistent True`). That is exactly what R10a forbids, so the failure is for the right reason.
  - It cannot be a false alarm: a fix that keeps the transaction keeps I1 persistent, and `_id_of` then works. The reference, `r_savepoint` and all 86 tests show this.
  - It cannot be a pass: no later code path gets round it.
  - Note: Then 4 and Then 5 do not catch these two. After `r_broken_tx` the session is inactive, yet `db.flush()` with nothing to flush returns `None`. Then 6 is the line that catches them, and it does so reliably. In round 3 they failed at old Then 4, the same `reread` line.
  - Optional, no verdict impact: the message is cryptic. `_id_of` could raise "row is no longer in the session". I did not change it; the helper is shared by all 228 tests and nothing is wrong with the result.

### Round 3 survivors, re-run on revision 5 (`--runxfail`, 86 `delete_item` tests; reference: 86 passed)
| Variant | Fails |
|---|---|
| `mix_a_row_factory`, `mix_b_row_machine`, `mix_g_row_factory`, `mix_h_line_batch` | D-80 T3, only |
| `mix_c_line_order`, `mix_c_order_stage`, `mix_d_line_order`, `mix_e_line_order`, `mix_f_line_order` | D-81 T3, only |
| `mix_c_stage_lookup` | D-82 call, only |
| `o_ws_only` | D-83 T2, only |
| `ret_po_exempt`, `ret_so_exempt` | D-84 T3, only |
| `h_in_out_only`, `h_qty_zero_skips` | D-85 T1, only |
| `a_factory_live`, `b_machine_live`, `g_factory_live` | D-86 T2, only |
| `r_dirty` | D-48 T4, only |
| `r_savepoint` | none: equivalent (ruling above) |

Added this round, each caught unless stated:
| Variant | Fails |
|---|---|
| `actual_quantity` 0 / `variance_quantity` 0 skipped | D-85 T1 (each) |
| waste lines ignored / byproduct lines ignored | D-85 T2 (each) |
| machine `is_active` filtered | D-86 T2 |
| dirty stock row left with the unknown user | D-48 T5, only |
| return line changed before the refusal: purchase / sales | D-84 T5 / T6 |
| machine stock / products changed before the refusal | D-86 T5 / T6 (and the older stock cards) |
| refusal with one arg for another workspace's item | D-83 T3 |
| that item written / its stock written | D-83 T4 / T5 (and D-04, D-05 for the item) |
| factory `is_active` filtered, (a) and (g) | **none: finding 1** |
| `r_savepoint_all` | none: equivalent |

The whole set was re-run, not only the survivors: 133 variants, 129 caught, and every round 3 result outside these tables is unchanged except for D-48's renumbered lines and the new cards also catching their rows. `stage_item_ws` now fails D-55 and D-82.

### Then lines the new xfails never reach
The 5 new xfails and D-48 are included: the 23 BUG-948 xfails of D-48 … D-86 have **104 Then lines after Then 1**. All pass on the reference and each was made to fail on its own line (`audit3.txt`). This includes D-48's new Then 4 and 5 and renumbered Then 6 … 10. The Then lines of D-82 and D-83, which run today, were also each made to fail.

### Reproduced claims
- Notes' Result line matches: 122 passed, 106 xfailed, 96%, only 195–204 missed. BUG-948 has 43 strict xfails. Cases header counts match (228 · 122 · 106).
- All 106 xfails fail on the card's line. D-80, D-81, D-84, D-85, D-86: `DID NOT RAISE ValueError` at Then 1. D-48: `IntegrityError` at Then 1.
- Traceability is clean for all 228: one test per card, markers, `# Then N` numbers. `ruff check` passes. The 7 new tests are all under `# [claude]`, and nothing is mocked.
- Stable: 5 plain runs (2 with planner settings) and 2 `--runxfail` runs. No flaky test.
- The notes' wrong-fix table matches my runs.

### Mutation
**Not re-run.** The source is unchanged. D-48 is xfail, so the tool never runs it. D-82 and D-83 are added pass tests, and an added test can only kill more, so no earlier kill can be lost. Survivors #13 and #14 stay bug-path (BUG-941): D-83 asserts one arg and "not the in-use message", which an emptied message still satisfies.

### Notes for other files
- `P28` and local-model notes: not relevant. All 7 tests are Claude-written, and each `as exc` is read by a later line. Local-written tests in this round: 0.

### Open
- Finding 1 above.
- Spec gap 8: four history tables wait for the owner; no card.
- Spec gap 9: the spec does not name the quantity or soft-delete columns. The tests read them from the models, and they are right. Fill-gaps only if wanted.
- "Unchanged" for the rest of the file rests on the same indirect evidence as round 3, now also for revision 5's claim that no other existing test changed: docstrings, markers, Then numbers, outcomes and the 6 exemplars all hold.

### Commands run (round 4)
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --cov=app.managers.item_manager --cov-branch --cov-report=term-missing -rX
  app\managers\item_manager.py      96      3     36      0    96%   195-204
  122 passed, 106 xfailed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider -rX    (twice)
  122 passed, 106 xfailed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --runxfail
  106 failed, 122 passed

PGOPTIONS="-c enable_seqscan=off" | "-c enable_indexscan=off -c enable_bitmapscan=off"
  122 passed, 106 xfailed   (each)

git diff --stat app/managers/item_manager.py     (empty)
```
Scratch, under `<scratchpad>/itmv3/`: `variants.txt`, `audit3.txt` (round 4), `variants.round3.txt`, `audit3.round3.txt`, `prop/test_prop4.py`.

Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

---

## Round 3 (2026-10-30) — scoped to ITM-D-48 … D-79

Scope: the 32 new tests of cases revision 4, read line by line against their cards and `delete_item` R9 (a)–(h), R9a, R9b, R10, R10a. The earlier 189 tests were re-run, not re-read.

### Summary
- **The 32 new tests can be trusted as written.** Each Given row, When call and numbered Then line matches its card, in order, and the new builders match Conventions. All 32 are `# [claude]`; none was written by the local model. No test was edited in this round.
- **Why the verdict is NEEDS WORK:** rules that have no card. 19 hand variants break a written rule of R9, R9a or R10a and no test notices. They fall into 6 gaps, listed under Findings, all for the case designer. A scratch test for each gap passes on the reference and fails on its variants, so about 6 or 7 new cards close them.
- **One statement in the cases file is wrong.** The Reviewer summary says the mixed shapes need no card because "D-49 … D-54 already fail for any workspace check on the row, its order or its parents". That holds for a check against the *item's* workspace. It does not hold for a check between two rows (line against order, row against factory, order against stage), because those cards put both rows in W2. 10 such variants survive.
- **What the tool can and cannot show:** `delete_item` has no blocking code yet, so `mutate.py` has nothing of R9 to mutate. The 17 / 17 says nothing about R9; the hand variants carry that weight. They ran on my own reference, written from the spec, because the earlier plugins no longer exist (see "Limits of this round").

### Findings
| # | Kind | Rule | What is wrong | Evidence (variants that survive) | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | R9 intro: "no `workspace_id` is compared on the row, its order or batch, its line, or the factory, machine or stage row it points at"; spec Notes, the two mixed shapes | No card has a row of W2 on a parent of W1, or a W1 order on a W2 stage. A fix that joins parents on matching `workspace_id` passes every test and lets an item in use be deleted. | `mix_a_row_factory`, `mix_b_row_machine`, `mix_c_line_order`, `mix_c_order_stage`, `mix_c_stage_lookup`, `mix_d_line_order`, `mix_e_line_order`, `mix_f_line_order`, `mix_g_row_factory`, `mix_h_line_batch` | **case designer** (also correct the Reviewer summary sentence) |
| 2 | case-missing | R9 "Checked after R1–R3 (a missing / other-workspace / already-deleted item gets those errors)" | No card deletes an **other-workspace item that is in use**. D-36 covers the already-deleted side only. A fix that checks blockers before the workspace check sends another workspace's blocker ids to the caller. | `o_ws_only` | **case designer** (today that card fails on the BUG-941 message, so it is xfail BUG-941, or a pass card that only asserts the refusal is not raised) |
| 3 | case-missing | R9a "The order line a return points at still counts under R9 (c) / (d) in its own right" | D-59 and D-60 are on orders that do not block. No card has a return on an order that does. A fix that exempts returned lines passes. | `ret_po_exempt`, `ret_so_exempt` | **case designer** |
| 4 | case-missing | R9 (h) "in any `item_role`"; "Quantities on the line are not looked at" | Only `input` and `output` lines are built, all with empty quantities. | `h_in_out_only` (waste / byproduct ignored), `h_qty_zero_skips` (a line with quantity 0 ignored) | **case designer** |
| 5 | case-missing | R9 (a), (g) "the factory's own state is not looked at"; (b) "the machine's own state is not looked at" | No card has stock on a deleted factory or machine. The (a) and (b) part predates this revision; rounds 1–2 did not try it. | `g_factory_live`, `a_factory_live`, `b_machine_live` | **case designer** |
| 6 | case-missing (low) | R9 "nothing written"; R10a "The transaction stays usable" | With `autoflush=False`, a fix that sets `is_active` / `updated_by` on the object and then refuses leaves a dirty item in the session. `reread` calls `expire_all()`, which throws that change away before reading, so D-48 and every other card pass. With the unknown user, the next flush in that session would fail. The D-48 card says its checks prove the transaction stays usable; they do not cover this. | `r_dirty` | **case designer** (extra Then lines on D-48 before the re-read: `I1 not in db.dirty`, then `db.flush()`) |

No fidelity finding. `Fix by executor`: only implementing the new cards. Nothing here needs an owner decision: each gap is a rule already written in the spec. The one thing to settle is the Expect of finding 2.

Scratch tests that close the gaps, 7 passing on the reference (`itmv3/prop/test_prop.py`, not in the repo):
| Scratch test | Fails on |
|---|---|
| W2 rows on W1 parents, W1 order on a W2 stage, all nine blockers listed in order | the 9 `mix_*` variants other than `mix_c_stage_lookup` |
| W1 purchase order on a W2 stage "Complete" does not block | `mix_c_stage_lookup` |
| other-workspace item in use gets "not found" | `o_ws_only` |
| reopened orders with pending returns block | `ret_po_exempt`, `ret_so_exempt` |
| waste and byproduct lines with quantity 0 block | `h_in_out_only`, `h_qty_zero_skips` |
| stock on a deleted factory and machine blocks | `g_factory_live`, `a_factory_live`, `b_machine_live` |
| no dirty item left after the refusal, and a flush works | `r_dirty` |

### Hand variants (each on the reference, `--runxfail`, all 79 `delete_item` tests)
"T" = the card's Then line; "call" = the When of a pass card. Unchanged reference: **79 passed**.

**(g) finished-goods stock**
| Variant | Failed by |
|---|---|
| not looked at | D-66, D-67, D-68, D-69, D-70 T1, D-75 T3 |
| only `qty > 0` | D-67 T1 |
| `is_deleted` ignored | D-77 call |
| `qty 0` blocks | D-76 call |
| only `is_active` rows | D-68 T1 |
| only rows for sale | D-66 … D-69 T1, D-70 T2, D-75 T3 |
| only rows not for sale | D-70 T2 |
| one entry per factory | D-70 T2 |
| item id / factory id as the blocker id | D-66, D-69 T3, D-67, D-68, D-70 T2, D-75 T3 (each) |

**(h) production batches**
| Variant | Failed by |
|---|---|
| not looked at | D-71 … D-74 T1, D-75 T3 |
| `draft` only | D-72, D-73 T1, D-75 T3 |
| `in_progress` only | D-71, D-74 T1, D-75 T3 |
| `completed` blocks / `cancelled` blocks | D-78 call / D-79 call |
| `input` lines only | D-72 T1 |
| a quantity required | D-71 … D-74 T1, D-75 T3 |
| line id instead of batch id | D-71, D-73, D-75 T3, D-72, D-74 T2 |
| a batch listed once per line | D-74 T2 |

**W2 cards: a filter on the item's workspace, one level at a time**
| Variant | Failed by |
|---|---|
| (a) on the stock row / the factory | D-49 T1, D-56 T3 (each) |
| (b) on the row / the machine | D-50 T1 (each) |
| (c) on the line / the order / the stage | D-51 T1 (each) |
| (d) on the line / the order / the status | D-52 T1 (each) |
| (e) on the line / the order / the type | D-53 T1 (each) |
| (f) on the line / the order | D-54 T1, D-56 T3 (each) |
| (g) on the row / the factory | D-69 T1 (each) |
| (h) on the line / the batch / the production line | D-73 T1 (each) |
| "Complete" looked up in the item's workspace | D-55 call, only |
| W1 stock listed first | D-56 T3, only |
| every filter at once | D-49 … D-54, D-69, D-73 T1, D-56 T3 |

**R9b sort and form**
| Variant | Failed by |
|---|---|
| alphabetical types | D-56, D-75 T3 |
| `product_stock` before `transfer_order` / `production_batch` before `product_stock` | D-75 T3 (each) |
| `transfer_order` before `work_order` | D-56 T3 |
| ids descending | D-47 T2, D-56 T3, D-70 T2, D-75 T3 |
| sorted by id only | D-45, D-56, D-75 T3 |
| first blocker only | D-45, D-56, D-75 T3, D-47, D-70 T2 |
| other message | 26 cards, T2 |
| empty list / one arg / extra key | 27 cards, T2 or T3 |
| a third arg | D-40 T2, only |

**R9a: each table made to block, then each row written by the delete**
| Variant | Failed by |
|---|---|
| inventory ledger / machine ledger blocks | D-57 / D-58 call |
| purchase return / sales return blocks | D-59 / D-60 call |
| template line by `item_id` / by `replaced_item_id` blocks | D-61 / D-62 call |
| formula line / formula stage blocks | D-63 / D-64 call |
| project component item blocks | D-65 call |
| R9a rows updated by the delete | D-57 … D-65 T3 |
| R9a rows removed by the delete | D-57 … D-63, D-65 T3 |
| return header changed | D-59, D-60 T4 |
| order line changed | D-55 T4, D-59, D-60 T5, D-29 T4, D-28, D-30 T3 |
| purchase order changed | D-55 T3, D-29 T3 |
| replacing item changed | D-62 T4 |
| products row changed | D-76, D-77 T3 |
| batch changed / batch line removed | D-78, D-79 T3 / T4 |

**R10, R10a and check order**
| Variant | Failed by |
|---|---|
| unknown user skips the blocker check | D-48 T1 (IntegrityError), only |
| write first, FK error escapes | D-48 T1, only |
| "user not found" error instead of the refusal | D-48 T2, only |
| empty blocker list | D-48 T3, only |
| FK error caught, refusal raised on the failed transaction | D-48 T4, only |
| `session.rollback()`, then the refusal | D-48 T4, only |
| every unknown user refused, in use or not | D-11 T1, D-48 T2 |
| refusal for an item not in use, unknown user | D-11 T1, only |
| blockers before "already deleted" | D-36 T2, only |
| blockers before the workspace check and "already deleted" | D-36 T2, only (see finding 2) |
| write inside a savepoint, rolled back, then the refusal | none: **equivalent**, no write stays, the session is usable, same error |

### The Then lines the xfails never reach
- 18 new xfails have **80 Then lines after Then 1**. None runs today. All 80 pass on the reference.
- **Each of the 80 was made to fail on its own line** by some variant. Bad writes before the refusal did this: `is_active` (T4), stamp, `updated_at`, tag counter, stock of the lowest / highest id, order lines, batch, batch line of the lowest / highest id, an inserted tag and removed links (`written`). `audit3.txt` has the table.
- The pass cards' Then lines were also each made to fail (table above).
- D-48 Then 4 `updated_by is None` was checked with a stamp of a real user, since `MISSING` cannot be stored.

### Reproduced claims
- Notes' Result line matches: 120 passed, 101 xfailed, 96%, only 195–204 missed.
- **All 101 xfails fail on the card's "Fails today on" line.** Of the 18 new: 17 with `DID NOT RAISE ValueError`, D-48 with `IntegrityError` on `items`, all at Then 1.
- **D-48 teardown:** with `-W error` it stays xfailed. Afterwards the test database has 0 rows in the 10 tables checked and no connection idle in a transaction.
- **Executor's stand-in:** `sim_fix_948.py` gives D-05, D-09 failed and 77 passed. Its four wrong fixes fail what the notes say: D-49 … D-54, D-56, D-69, D-73 / D-56, D-75 / D-55 / all 38 BUG-948 cards (each plus D-05, D-09).
- No flaky test: 5 plain runs and 5 `--runxfail` runs, 2 of each with planner settings (seqscan off; index and bitmap off), plus 117 variant runs on the unchanged test file.

### Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 13, 14 | 307 | the "does not belong to workspace" message emptied | bug-path (BUG-941) | That message is the bug. D-04 asserts only `ValueError`, as its card says, and D-05 fails on that line today. Same as round 1's #84, #85. | — (resolves with BUG-941) |

Score: 17 / (19 − 2 bug-path) = **100%**.

### Traceability
cases 221 · tests 221 · unmatched: none · marker mismatches: none. Each docstring equals its card's ID and title. `# Then N` numbers match the card in all 221. D-48 … D-79: 18 strict xfail naming BUG-948, 14 pass, all under `# [claude] <ID>`. Per Rules line of the 32: identical to the card. BUG-948 now 38 cards, total 101 = 83 + 18; 120 = 106 + 14. `ruff check` passes. Mocks: none in the 32.

Local-written tests: 0 of the 32, so no new `## Local-coder patterns` entry. Findings in local-written tests / local-written new tests: 0 / 0; in others: 0 / 32 for test-side findings.

### Limits of this round
- **"Unchanged" for the earlier 189 tests is shown indirectly, not byte for byte.** `tests/unit/` is untracked and no copy from before revision 4 exists, in git, in file history or in the scratchpad. The evidence:
  - the 32 new tests are one block at the end of the file, the same text as the executor's `new_tests.py`;
  - the 6 exemplars printed in `item_manager.helpers.md` (dated 2026-10-18) are still verbatim;
  - round 1's fixes are all still in place (D-23, D-34, D-43, FS-06, FS-07, U-35, U-36);
  - the 189 keep their docstrings, markers and `# Then N` numbering, 106 pass, and the 83 xfails fail on their cards' lines.
- **The round-2 tools are gone.** `scratchpad\itmv\plug\` holds only an empty `__pycache__`; `ref_itm.py`, `var_itm.py`, `audit.py` and `xfloc.py` no longer exist. So the 324-plant self-test and the whole-module reference were not re-run. Later Then lines of the 79 `delete_item` tests ran on my new reference. Those of the other xfails (create, update, get, assign) last ran in round 2.
- **Not exercised, on purpose:** the return statuses `completed` / `voided`, and other ledger transaction types and formula roles (R9a). The cases file says so, and only a contrived fix would be caught by such cards. The four history tables of Spec gap 8 stay undecided, with no card.

### Commands run (round 3)
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/item_manager.py tests/unit/managers/test_item_manager.py --lines 290-323 --timeout 300 --json <scratchpad>/itmv3/mut.json
  Mutants: 19 · killed 17 · timeout 0 · survived 2 (raw 89%)    SURVIVED #13 #14 (L307)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --cov=app.managers.item_manager --cov-branch --cov-report=term-missing -rX
  app\managers\item_manager.py      96      3     36      0    96%   195-204
  120 passed, 101 xfailed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --runxfail -rf
  101 failed, 120 passed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider -rX    (twice)
  120 passed, 101 xfailed

PGOPTIONS="-c enable_seqscan=off" | "-c enable_indexscan=off -c enable_bitmapscan=off"   (1 plain + 1 --runxfail each)
  120 passed, 101 xfailed / 101 failed, 120 passed

git diff --stat app/managers/item_manager.py     (empty)
```
Scratch, all under `<scratchpad>/itmv3/`: `plug/ref948.py` (reference and variants), `drive.py`, `variants.txt` (every variant, card and Then line), `audit3.py`, `audit3.txt`, `prop/test_prop.py`, `prop_drive.py`.

Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

---

The sections below are rounds 1 and 2 (2026-10-18), kept as written.

## Summary
- I read all 187 tests against their cards, line by line: every Given row and its columns, the When call and each argument, every numbered Then line (check, type, value, `# Then N` placement). Nothing was sampled. As a second, independent check, a script rebuilt the expected body of each of the 178 vocabulary cards (165 local, 9 exemplars, 4 escalated) from the card text and the helper sheet and compared it with the test, statement by statement. The reading and the script agree. The script was tested on **324 planted mistakes in 31 kinds** (value and row swaps, dropped or extra lines, weakened checks, snapshots, markers, `begin_nested`, a `try`, Then numbering): it reported **324 of 324**.
- **Local-model tests (165): 1 functional finding — 164 of 165 (99.4%) are right as delivered.** ITM-D-43 builds an extra row, `mk_stage("IN_PROGRESS")`, that the card does not list. That row does not change the outcome under today's code or under the reference fix, but the Given is not the card's. **Fixed.** Cosmetic findings are in 9 / 165 tests (listed below), plus 20 names the tool cut at 70 characters.
- **Claude-written tests (22: 9 `Author: claude` + 4 escalated + 9 exemplars): 0 functional findings.** Cosmetic: 6 names shortened by hand, 4 cut by the tool, and C-40 drops an unused `result =`.
- **"As delivered" was checked against the delivered copy.** Step D changed only three local tests (the unused `as exc` in L-08, U-05, D-04) plus imports, so Step D was cosmetic. The 164 / 165 figure is the model's own output.
- **All 83 xfail tests fail under `--runxfail` where their cards say.** 80 fail on the card's Then line; G-06, G-07 and G-08 fail in the When with `TypeError` (no `include_deleted`), as their cards say. 69 xfail tests (61 local) have **165 Then lines after the failing line** that no normal run reaches. They were run once against a scratch reference of the intended behaviour (BUG-017, BUG-034, BUG-934 … BUG-948 fixed in memory, plus the intended SKU unique index created inside each test's transaction): **187 of 187 pass**. Each of 20 deliberately wrong references was caught, many only on a later Then line.
- **Refuse-while-in-use (R9 / R9b).** 20 hand variants of the reference's blocker list were run: each condition (a)–(f) switched off, each "does not block" state made to block, `replaced_item_id` ignored, DRAFT made free, other items' rows counted, and the blocker check moved before "already deleted". **All 20 are caught.** So are 6 variants of the list's form: first blocker only, line ids instead of order ids, wrong order, duplicates, one-arg error, written before refusing.
- **Mutation.** 16 survivors. 6 are dead code (`search_items` and the P9 `hasattr` branch), 2 equivalent, and 6 bug-path (BUG-941, BUG-942, BUG-944). **2 are `case-missing`:** no card checks the default `limit` of `list_items_filtered` (100) or `find_similar_items` (5). Commit-spy variants: a commit in each writer (create, update, delete, assign; also before the tag step and before the decrements) is caught by C-40 / U-45 / D-12 / A-13. As in earlier modules, a commit inside a reader is not caught (optional note).
- **Stable:** 6 plain whole-file runs (4 before, 2 after the fixes), 2 coverage runs, and 3 planner settings (sequential / index / bitmap) each with a plain and a `--runxfail` run. None was red and none XPASSed.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Wrong setup — extra Given row (local) — FUNCTIONAL | ITM-D-43 Given | The card's Given is I1, F1, WT1, WO (`status "IN_PROGRESS"`) and WOL. The test also inserts a `statuses` row `"IN_PROGRESS"`, and the arguments request `mk_stage`. A work order's state is the column `status`, not a stage row. The extra row is harmless today and with the reference fix (the e-variants are still caught), but "no other row exists unless the card's Given lists it." | `mk_stage("IN_PROGRESS")` before `wo = mk_wo(...)` | **fixed by the verifier**: line and argument removed; re-run below |
| 2 | Missing case — default limit (survivor #36) | `list_items_filtered` R1 ("defaults `skip=0`, `limit=100`") | No card calls `list_items_filtered` without `limit` on more than 100 live items. Mutant `limit: int = 101` survives (run alone and with xfails visible: 104 passed / 83 xfailed, identical). The `skip` default is covered (mutant #35 killed). | `mut2.log` #36; `var_mut36.txt` | **case designer** |
| 3 | Missing case — default limit (survivor #37) | `find_similar_items` Inputs (`limit` default `5`), R1 | No card has 6 or more similar items with the default limit. Mutant `limit: int = 6` survives. | `mut2.log` #37; `var_mut37.txt` | **case designer** |
| 4 | "but" column set after the builder (local) — COSMETIC | ITM-D-23, ITM-D-34 | Card: "WO line of I2, but `replaced_item_id I1.id`" / "WO line of I1, but `is_deleted True`". The test built the line, then set the attribute and called `db.flush()`. The resulting row is identical. D-34 also named the WO line `pol`. | `wol.replaced_item_id = i1.id` / `pol.is_deleted = True` | fixed by the verifier (keyword on `mk_line`, variable `wol`) |
| 5 | Plain "item" built from a recipe (local) — COSMETIC | ITM-FS-06, ITM-FS-07 | Card: "item, `name …`, `name_normalized …`". Test: `mk_item("I1", name=…, name_normalized=…)`. I1 differs from the plain item only in those two columns, which are both overridden, so the row is identical. | `mk_item("I1", name="AB", …)` | fixed by the verifier (`mk_item(name=…, name_normalized=…)`) |
| 6 | Parenthetical written as a keyword (local) — COSMETIC | ITM-U-35, ITM-U-36 | Card: "T1. (`usage_count 0`.)". Text in parentheses is an explanation. The test wrote `usage_count=0`, which equals the default. | `mk_tag("T1", usage_count=0)` | fixed by the verifier (`mk_tag("T1")`) |
| 7 | Unused `as exc` (local) — COSMETIC | ITM-L-08, U-05, D-04 (as delivered) | Already removed in Step D (P28). No check was lost. | delivered copy lines 736, 1552, 2744 | none (done) |
| 8 | Naming — COSMETIC | 20 local, 3 exemplar, 1 Claude test names cut at 70 characters; 6 Claude names shortened by hand (C-30, C-32, C-40, U-45, D-12, D-13); one re-read named `row_i2` (U-46, as the sheet says) | Every docstring carries the full ID and title. | — | optional — tool |
| 9 | Unused `result =` dropped (claude) — COSMETIC | ITM-C-40 When | The card writes `result = M.create_item(…)`, but no Then line reads `result`. | — | none |

No other finding. These were checked in all 165 local tests by reading, and by the rebuild script (✓):
- **Given rows** ✓: no row missing, extra (except finding 1) or reordered. Every "but" column is present with its value: `usage_count`, `sku`, `description`, `item_type`, `name_normalized "stale"`, `updated_by U2.id` / `updated_at T0`, `unit`, `is_active False` (G-07), `voided True`, `order_completed True`, `is_deleted True` on stock (D-26) and on the work order (D-33), `completed_at T0`, `inventory_type InventoryTypeEnum.DAMAGED`, `qty 0 / -2 / 3 / 5 / 400`, `req_qty 10`, `defective_qty 2`, `line_number 2`. Code Given lines (`l1_id`, `l1_at`, `l2_id`, `created_before`) run in place.
- **Swaps between rows of one kind** ✓, in every card that builds two or more rows of a kind:
  - items I1 / I2 / IX / I9 (D-23 line of **I2** replacing I1; D-37 / D-38 stock and line of **I2**; U-46 acting on **I2**; U-51 renaming **I2**);
  - tags T1 / T2 / K3 / TD / T9 (U-33, U-34, U-38, U-40, U-43, A-08 / A-09 id order);
  - links (U-34 L1 to T1, U-38 / U-40 L2 to TD);
  - stock rows SK1 / SK2 (D-47) and order lines POL1 / POL2 (D-46);
  - users U1 / U2 (`assigned_by == U1.id` in U-34 / U-38; `created_by == U1.id` in U-02 / D-02; U2 acting everywhere).
- **Text values** ✓ (compared as Python source):
  - names: `"  Steel  Rod 22 m "`, `"steel  ROD"`, `"   "`, `"\t"`, `"  "`, `"!!!"`, `"BOLT-m8"`, `"New  Name-2"`, `"  Lock Nut "`, `"  Steel Rod 22m "`, `"steel rod 22 M"`;
  - units: `" Kg "`;
  - SKUs: `" B-M8 "`, `" b-m8 "`, `"b-m8"`, `""`.
- **When call** ✓: no argument changed, dropped or added. Positional calls stay positional (G-02, UN-01, UN-02, L-07). `include_deleted=True` is passed unwrapped (G-06 … G-08). Explicit `None` (U-18, U-19, U-32) and `ItemUpdate()` (U-26, U-30) are kept.
- **Then lines** ✓: no line skipped, no assertion under the wrong `# Then N`, none weaker than the card, none extra.
  - `args[0]` / `args[1]` are used on every in-use card and `str(exc.value)` everywhere else.
  - `len(exc.value.args) == 2` (D-40) and every blocker list are compared with `==`, order included.
  - `is True` / `is False` / `is None` are kept.
  - "every row of links_of" becomes `all(...)` per value; filtered counts become one `count_rows` with the card's filters.
- **Snapshots** ✓: every `before…` is taken after the last Given line and before the call, and only where the card has `unchanged` / `nothing written`.
- **Error shapes and mocks** ✓: no `try`. `pytest.raises` appears only on `raises:` cards, with the card's type. `begin_nested` is used exactly for `IntegrityError` / `DataError`. `as exc` appears only where a later `raises:` line reads `exc.value`. Nothing is patched in any local test.

I read the 22 Claude-written tests the same way:
- **C-29 / C-30 / C-31** insert directly with exactly the card's keywords (`sku="b-m8 "` with its trailing space; `is_active=False` only in C-31).
- **C-32** patches only `ItemManager._check_sku_exists` (`create=True`, Spec gap 3), with `begin_nested` inside `pytest.raises(ValueError)`.
- **C-40, U-45, D-12, A-13** take the savepoint directly before the call. Each runs the "before" checks, then `sp.rollback()`, then the "after" checks, then `assert_not_called()` on a `Mock(wraps=db.commit)` spy.
- **D-13** makes its follow-up calls in the card's order.
- **The 4 escalated cards** (FS-11 with `begin_nested`; D-17 with MC1 built from F1; D-33 with `mk_wt1()` and `is_deleted=True` on the work order; D-47 with two `mk_stock` rows) match their cards exactly. All four cards are right, as the notes say.

### Fixes made by the verifier (test file only)
In `test_item_manager.py`:
- **D-43:** removed `mk_stage("IN_PROGRESS")` and its `mk_stage` argument.
- **D-23:** now `mk_line(of=i2, order=wo, replaced_item_id=i1.id)` (the attribute line and the `db.flush()` are dropped).
- **D-34:** now `wol = mk_line(of=i1, order=wo, is_deleted=True)`, with `wol` in the snapshot and assert.
- **FS-06 / FS-07:** now `mk_item(name=…, name_normalized=…)`.
- **U-35 / U-36:** now `mk_tag("T1")`.

After the fixes:
- the rebuild script reports **0 differences** in 178 bodies;
- `ruff check` passes;
- the results are unchanged: 104 passed, 83 xfailed, 96%; `--runxfail` 83 failed, each on the card's line; 187 / 187 against the reference;
- the D-23 / D-34 / D-43 blocker variants are still caught;
- the mutation tool, re-run alone, gives the same 75 killed / 16 survived.

Nothing under `app/`, the spec, the cases file or the notes was edited.

### xfail tests against a reference fix (scratch only)
`itmv/plug/ref_itm.py` replaces six manager methods in memory with the intended rules and adds `_check_sku_exists`:
- BUG-936 / BUG-017 / BUG-942 / BUG-946 / BUG-947: `ItemCreate` / `ItemUpdate` trim and reject blank names and units, reject `null` for name / unit / type, store a blank SKU as `None`, and drop `is_active`.
- BUG-944 / BUG-943: tags are checked in list order before anything is written.
- BUG-946: SKU check, plus the partial unique index `items (workspace_id, lower(btrim(sku))) WHERE is_active AND sku <> ''` created in each test's transaction; a violation becomes the manager's `ValueError`.
- BUG-934 / BUG-935 / BUG-939: a tag save only removes and adds the difference and leaves links to deleted tags alone; a no-op is not stamped.
- BUG-938 / BUG-941: deleted or other-workspace items answer "not found".
- BUG-937: `include_deleted`.
- BUG-945: every linked tag is decremented.
- BUG-948: the R9 blocker list sorted per R9b.
- BUG-034: score compared as `real`.

Nothing in the repo is edited.

| Reference | Result with `--runxfail` (failing Then line) |
|---|---|
| all bugs fixed | **187 passed**: every xfail test passes in full, and no pass test pins a bug |
| only the first blocker raised | D-45 **Then 3**, D-47 Then 2 |
| line ids instead of order ids | D-39 **Then 3**, D-42, D-43, D-44, D-46 Then 2, D-45 Then 3 |
| blockers in the wrong order | D-45 **Then 3**, D-47 Then 2 |
| an order listed once per line | D-46 Then 2 |
| the item written, then the refusal raised | **20 tests**: D-14 … D-24, D-39 … D-47, on the "re-read I1" line (Then 3 / 4) |
| refusal with one argument only | D-39 Then 3, D-40 … D-44, D-46, D-47 Then 2, D-45 Then 3 |
| SKU checked after the insert | C-24, C-25 **Then 3** (count) |
| tags checked after the item is created | C-35, C-36, C-37 **Then 3** (count) |
| valid tags linked before a bad one is refused | A-07 **Then 3** |
| a no-op update still stamped | U-26 Then 2, U-27, U-28, U-29 **Then 3** |
| a staying tag re-linked (BUG-934 open) | U-34 **Then 3**, U-35 Then 2, U-28 Then 3, U-40 in the call |
| links to deleted tags erased (BUG-935 open) | U-38, U-41 **Then 2** (and 5 tag-save pass / xfail cards) |
| a deleted tag already on the item refused when re-sent | U-40, A-11 in the call |
| deleted tags skipped on delete (BUG-945 open) | D-09 **Then 2** |
| `include_deleted` ignores the workspace | G-07, G-04 Then 1 |
| `null` name / unit / type accepted | U-20, U-21, U-22 Then 1 |
| `is_active` kept in `ItemUpdate` | U-23 **Then 3**, U-24 Then 1 |
| no unique index / race raises a raw `IntegrityError` | C-29, C-30, C-32 Then 1 / C-32 Then 1 |
| names and units not trimmed | C-09, C-17, U-17 Then 2, U-12 **Then 3** |

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 11, 31, 32, 33, 34 | 179–204 | `search_items` (condition, defaults, returns) | dead | `search_items` is "Not specified — dead code, to be removed" (spec; dead-code checklist). | — |
| 26 | 112 | `hasattr(...) and tag_ids is not None` → `or` | dead | `hasattr` is always true for `ItemUpdate` (P9, a dead branch on the checklist); with `or`, `tag_ids` is still `None` exactly when it was. Re-run as `mut26`, with xfails visible: identical. | — |
| 57 | 116 | `exclude_unset=True` → `False` | equivalent | `exclude_none=True` stays and every `ItemUpdate` field defaults to `None`, so an unsent field is dropped either way. `mut57`: identical, xfails included. | — |
| 74 | 116 | `exclude={'tag_ids'}` → `{''}` | equivalent | `tag_ids` then reaches `item_dao.update`, which sets only attributes the model has (`hasattr`); `Item` has no `tag_ids`. `mut74`: identical. | — |
| 58 | 116 | `exclude_none=True` → `False` | bug-path (BUG-942) | An explicit `null` is then written. **U-18, U-19 XPASS** (strict, BUG-942); nothing else changes. It becomes part of the fix. | — (resolves with BUG-942) |
| 72, 73, 84, 85 | 108, 307 | the "does not belong to workspace" message emptied | bug-path (BUG-941) | That message is the bug. The pass cards U-05 / D-04 assert only `ValueError`, as their cards say, and U-06 / D-05 fail on that line today. | — (resolves with BUG-941) |
| 53 | 349 | `not tag or tag.workspace_id != ws` → `and` | bug-path (BUG-944) | An unknown tag id then crashes, and another workspace's tag is linked. Only BUG-944 cards send such ids (C-35, C-36, U-42, A-02 … A-05, A-07, A-08; all xfail). `mut53` with xfails visible: identical. After the fix, C-36 / A-05 Then 3–5 check that nothing is linked (shown by the reference). | — (resolves with BUG-944) |
| 36 | 217 | `list_items_filtered` default `limit` 100 → 101 | **case-missing** | Spec R1 states the defaults; no card leaves `limit` out with more than 100 rows. | **case designer** |
| 37 | 257 | `find_similar_items` default `limit` 5 → 6 | **case-missing** | The spec's Inputs give default `5`; no card has 6 or more matches with the default limit. | **case designer** |

Score: 75 killed / (91 − 2 equivalent − 6 dead − 6 bug-path) = 75 / 77 = **97%**.

**Beyond the tool.** Hand variants of today's code (`itmv/plug/var_itm.py`: the module source with text replacements, exec'd in memory and installed on the class) were run against the whole file. A strict-xfail XPASS counts as a failure.

| Variant | Failed by |
|---|---|
| unchanged source (`none`) | 104 passed, 83 xfailed |
| create **commits** | C-40 |
| update **commits** / commits before the tag step | U-45 / U-45 |
| delete **commits** / commits before the decrements | D-12 / D-12 |
| `_assign_tags_to_item` **commits** | C-40, U-45, A-13 |
| create commits only when no tags are sent | **none** (C-40 sends a tag; open note 2) |
| `get_item` / `find_similar_items` / `get_tags_for_item` commit | **none** (readers; open note 2) |
| `list_items_filtered` commits | L-08 (the commit ends its savepoint) |
| create without `created_by` | C-01, C-38 |
| update without `updated_by` | U-01, U-44 (+ U-26 … U-29 XPASS) |
| `name_normalized` not recomputed on rename | U-01, U-09, U-11, U-51 |
| delete without decrements | D-08, D-12 |
| assign without the "already linked" skip | A-10, A-11, A-12 |
| similarity not rounded / query not normalised before compare | FS-03 / FS-01 |
| fields written after the tags; decrements before the item update | none (equivalent: same final state; on the D-11 error the test's savepoint rolls the decrements back) |

**Refuse while in use (R9 / R9b), on the reference fix** (`ITMREF=fix+<variant>`, `--runxfail`):

| Variant of the blocker list | Failed by |
|---|---|
| (a) factory stock not looked at | D-14, D-15, D-16, D-40, D-47 Then 1, D-45 Then 3 |
| (a) only `qty > 0` blocks (negative ignored) | D-16 |
| (a) soft-deleted stock blocks | D-26 |
| (a) / (c) rows of another item block | D-37, D-38 |
| (b) machine stock not looked at | D-17, D-41 |
| (b) `req_qty` / `defective_qty` block | D-27 |
| (c) purchase lines not looked at | D-18, D-19, D-20, D-42, D-46 |
| (c) voided order blocks / stage `Complete` blocks | D-29 / D-28 |
| (d) sales lines not looked at / completed order blocks | D-39 / D-30 |
| (e) work lines not looked at | D-21, D-22, D-23, D-43 |
| (e) `replaced_item_id` ignored | D-23 |
| (e) DRAFT does not block | D-21 |
| (e) COMPLETED / VOIDED block | D-31, D-32 |
| (e) soft-deleted work order blocks / removed line blocks | D-33 / D-34 |
| (f) transfer lines not looked at / completed order blocks | D-24, D-44, D-45 Then 3 / D-35 |
| blocker check before "already deleted" | D-36 Then 2 |

Every blocking reason and every "does not block" state has at least one card that notices it. Single points to keep in mind when a card is edited (each is the only test that notices its variant):
- **D-16** (negative stock), **D-26**, **D-27**, **D-28**, **D-29**, **D-30**, **D-33**, **D-34**, **D-35**, **D-36**, **D-46** (one entry per order);
- **D-23** (`replaced_item_id`), **D-21** (DRAFT), **A-07** (no partial links), **FS-01**, **FS-03**.

## Spec coverage
Every rule of every specified callable has at least one card and one test. The only spec statements without a card are the two parameter defaults (findings 2, 3) and the open Spec gaps 4–6 of the cases file (see open questions).
- Rules whose only cards are xfail (none runs in a normal run today; all ran against the reference):
  - `create_item` R3 (blank part), R4, R7 (refusal part), R9;
  - `update_item` R2, R3, R6, R6a, R7, R8, R9, R12 (staying-link part), R13, R15, R18 (refusal / blank part);
  - `get_item` R3, R4;
  - `delete_item` R2, R7, R9, R9b;
  - `_assign_tags_to_item` R2, R3, R4;
  - `find_similar_items` R3 (the 0.35 case, BUG-034).
- Deferred, as the cases file says: BUG-940 (service), BUG-931 (item tag DAO), the 422 of schema errors.

## Traceability
cases 187 · tests 187 · unmatched: none. Each case ID appears in exactly one test name, and all 187 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`". Marker mismatches: none.
- **Markers.** 104 `Expect: pass` cards have no marker. 83 `xfail BUG-NNN` cards have `xfail(strict=True)` whose reason names exactly the card's bug.
- **By bug:** BUG-934 2 · 935 3 · 936 11 · 937 4 · 938 3 · 939 4 · 941 2 · 942 5 · 943 4 · 944 9 · 945 1 · 946 10 · 947 2 · 948 20 · BUG-017 2 · BUG-034 1 = 83, as the cases file states. All are in `docs/testing/bugs.md` (highest BUG-949).
- **Authorship**, from the file and `item_manager.local-run.json`:
  - 165 tests under `# [local-coder] <ID>`;
  - 13 under `# [claude] <ID>`: the 9 `Author: claude` cards and the 4 escalated ones, marked "(escalated by the local model)";
  - 9 exemplars without a comment.
  - No `Author: claude` card is outside `[claude]`.
- **Test bodies.** `# Then N` comments are present, in order, and equal in number to the card's Then lines in all 187. No fixture is requested and left unused (after fix 1), and none is used without being requested.
- **Mocks:** `patch.object` only in C-32 (race, as Conventions allow). The commit spies (`monkeypatch` of `db.commit` with `Mock(wraps=…)`) appear only in C-40, U-45, D-12, A-13. No `try`, no broad `pytest.raises`.
- **xfail location** (`--runxfail`, `itmv/xfloc.py`): 83 failed, each where its card says. 80 fail on the card's Then line; G-06 / G-07 / G-08 fail in the When with `TypeError … 'include_deleted'` ("Then 1 (the call raises TypeError …)").

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/item_manager.py tests/unit/managers/test_item_manager.py --json <scratchpad>/itmv/mut.json
  Mutants: 91 · killed 75 · timeout 0 · survived 16 · score 82%   (raw; run alone; re-run alone after the fixes → mut2.json, identical)
  SURVIVED #11 #26 #31 #32 #33 #34 #36 #37 #53 #57 #58 #72 #73 #74 #84 #85

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --cov=app.managers.item_manager --cov-branch --cov-report=term-missing -rX
  app\managers\item_manager.py      96      3     36      0    96%   195-204
  104 passed, 83 xfailed, 15 warnings      (before and after the fixes)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider --runxfail -rf
  83 failed, 104 passed                    (before and after the fixes)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_item_manager.py -q -p no:cacheprovider -rX     (4 times before, 2 after the fixes)
  104 passed, 83 xfailed                   (no XPASS)

PGOPTIONS="<seq | index | bitmap settings>" … (1 plain + 1 --runxfail each)
  104 passed, 83 xfailed / 83 failed, 104 passed   (each)
```
These match the notes' Result line (104 passed · 83 xfailed · branch coverage 96%, the 3 missed lines dead). There is no flaky test.

Extra checks, scratchpad only (`<scratchpad>/itmv/`; nothing in the repo written except this report, the test fixes above, and row 13 of `docs/testing/local-coder-improvements.md`):
```
listing.py / listing.txt   card-next-to-test listing of all 187 tests, used for the read
audit.py      cards ↔ tests ↔ markers ↔ bugs.md ↔ docstrings ↔ `# Then N` ↔ arguments ↔ delivered copy; rebuild of 178
              vocabulary cards → before the fixes 8 differences in 7 local tests (findings 1, 4, 5, 6); after: 0
selftest.py   324 planted mistakes, 31 kinds → 324 reported
xfloc.py      failing line of each --runxfail failure mapped to its `# Then N`
PYTHONPATH=<scratchpad>/itmv/plug ITMREF=fix[+<bad>] … -p ref_itm --runxfail      → reference and blocker tables above
PYTHONPATH=<scratchpad>/itmv/plug ITMVAR=<variant> … -p var_itm -rfX             → hand-variant table, mutants re-run with xfails
```

## Fix list
1. **Case designer — `list_items_filtered` default limit** (kills #36). Add a pass card: 101 live items of W1 (a loop, `Author: claude`); `result = M.list_items_filtered(db, workspace_id=W1.id)`; Then `len(result) == 100`. Rule: `list_items_filtered` R1 (defaults).
2. **Case designer — `find_similar_items` default limit** (kills #37). Add a pass card: 6 live items whose `name_normalized` equals `"bolt m8"` (all exact matches); `result = M.find_similar_items(db, workspace_id=W1.id, name="Bolt M8")`; Then `len(result) == 5`. Rule: `find_similar_items` R1 / Inputs (`limit` default 5).
3. **Executor**, after 1–2: implement the two cards, re-run, and send back for re-verification. Only the mutation table and the counts should change.
4. *Done by the verifier* — findings 1, 4, 5, 6 (test file only; re-run above).

Optional (no verdict impact):
- **(a)** A commit inside a reader (`get_item`, `find_similar_items`, `get_tags_for_item(s)`) is noticed by no test. Their Side effects are "none"; the same open note as the factory and section managers.
- **(b)** C-40 spies only a create **with** tags; a commit taken only on the no-tag path goes unnoticed.

Open questions, for the case designer / owner. These touch the order / stock workflow, so they are flagged, not decided:
- **Spec gap 4:** which error wins when an item in use is deleted with an unknown `user_id`.
- **Spec gap 5:** whether a stock or order row whose `workspace_id` differs from the item's still blocks the delete.
- **Spec gap 6:** the "does not block" tables of R9a (ledger, returns, templates, formulas, project components) have no card.
- **Spec gap 3:** the race card C-32 patches a not-yet-existing `_check_sku_exists` (revise with the BUG-946 fix).

No money question arises (nothing in this manager touches money).

## Local-coder patterns
1 functional mistake in 165 tests (ITM-D-43); 164 of 165 are what their cards say, as delivered.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| An extra Given row: a domain word in the card (`status "IN_PROGRESS"`) also built as a row of another kind (`mk_stage`) | 1 | ITM-D-43 | **functional** (harmless here) | Tool: count builder calls per kind and compare with the card's Given lines (one statement per row is already a sheet rule). Sheet: "a work order's `status` is a column; only lines that say `stage "X"` build a stage." |
| A "but" column set by attribute assignment + `db.flush()` after the builder, instead of a keyword | 2 | ITM-D-23 (`replaced_item_id`), D-34 (`is_deleted`) | cosmetic (same row) | Tool: reject `x.<col> = …` on a Given row; the sheet's "each column after 'but' is one more keyword" already says it. |
| A plain "item" built from a recipe with both name columns overridden | 2 | ITM-FS-06, FS-07 | cosmetic (same row) | Tool: when the Given line starts with "item," reject a positional recipe name (the sheet already says "nothing positional"). |
| Text in parentheses turned into a keyword equal to the default | 2 | ITM-U-35, U-36 (`usage_count=0`) | cosmetic | Tool: ignore text inside parentheses when matching builder keywords against the card (P11), so such a keyword is reported as extra. |
| A variable named after another row kind | 1 | ITM-D-34 (`pol` for a WO line) | cosmetic | Nothing needed beyond the row above. |
| Unused `as exc` on a `raises:` card without a further `raises:` line | 3 | ITM-L-08, U-05, D-04 | cosmetic (P28, removed in Step D) | Already known (P28). |
| Test name cut at 70 characters | 20 | — | cosmetic — tool | Tool limit; the docstring carries the full title. |

Observations for `docs/testing/local-coder-improvements.md`:
- **Then lines after an xfail's failing line are checked by nothing in the pipeline:** 142 lines in 61 local tests (165 in 69 overall). All were right: the scratch reference ran them, and 20 wrong references plus 20 blocker-list variants were each caught.
- **What worked:**
  - all 20 BUG-948 blocker cards, with the order builders and `mk_line` (one builder, the order picks the table);
  - every `args[0]` / `args[1]` check;
  - the 4 `IntegrityError` / `DataError` cards with `begin_nested`;
  - every whitespace literal and every `f"…{IX.id}…"` message;
  - `link_of` re-reads (U-34, U-38, U-40) and the `all(...)` form of "every row of links_of".
- **The 4 hand-backs were all model slips on builders the sheet shows** (FS-11 savepoint, D-17 MC1, D-33 `mk_wt1`, D-47 `mk_stock`), not card problems.
