# Verification — `app/managers/machine_manager.py`

> **Verdict:** PASS (round 3, 2026-10-31) — the 9 new tests are faithful and every remaining gap is closed. No test edited.
> Tests: 304 passed · 174 xfailed (reproduced ✅) · coverage 99% branch (only dead line 307 missed)
> Mutation: 195 / 195 = 100%, from round 2; not re-run, because no existing test, card or source line changed
> Source commit: e48a092 · Cases revision: 5 (478 cases; spec APPROVED)
> Rounds 1 and 2 are below, kept as written.

## Round 3 (2026-10-31) — scoped to D-91 … D-98, E-45

- **Read:** the 9 new tests against their cards and R4, R4a, R2a (G15): each Given row, When call and numbered Then line matches, in order. All `# [claude]`. A diff against round 2 shows only these 9 added: no card, test or helper changed. Traceability is clean for all 478, and the rebuild reports nothing new.
- **Reference:** R2a now also requires `is_deleted = False`. 478 of 478 pass, so every Then line after a failure point runs.
- **Variants, each failing the right card:**

| Round 2 survivor | Now fails |
|---|---|
| `g_nocond_stock`, `g_nocond_to`, `g_nocond_wo`, `g_nocond_line` | D-91, D-92, D-93, D-94 call |
| `g_item_foreign` | D-95 T1 |
| `g_order_factory_foreign`, `g_order_type_foreign` | D-96 T4 |
| `g_transfer_end_foreign` | D-97 T1 |
| `g_ii_own_and_foreign` | D-98 T4 |
| `e_r2a_live`, now accepting a soft-deleted order | E-45 T1 |

- **xfails:** all 174 fail where and why their cards say. D-95 … D-98 and E-45 fail at Then 1 with `DID NOT RAISE`, as written. D-91 … D-94 pass today.
- **Then lines:** the 5 new xfails add 31 later lines, 497 in all. Each of the 31 was made to fail on its own line by a variant. Forced in all: 473 of 497. The other 24 are the ones listed in rounds 1 and 2.
- **Runs:** 3 without `--runxfail` gave 304 passed, 174 xfailed, including coverage. 2 with it gave 174 failed, 304 passed. `ruff check` passes. `git diff --stat app/managers/machine_manager.py` is empty.
- **Accepted, not open:** the 12 schema-only Then lines, D-80 Then 5, 6, and the commit notes (a commit in `get_machine`, in `search_machines`, or in create only without a section). No verdict impact. No owner question is open. G14 and G15 are recorded as the coordinator's relay of the owner's answers; the tests were checked against them, not the answers themselves.
- **Limits:** mutation was not re-run, on the coordinator's instruction, and 9 added tests cannot lower a kill count. The 469 earlier tests were re-run, not re-read. The reference is one fix, mine.

Scratch: `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mcmv3\`. Only this report was written in the repo. No commit. No model server.

---

> **Verdict:** NEEDS WORK (round 2, 2026-10-31) — the case designer has 3 small gaps to close, and one order-workflow question is open for the owner. The 39 changed and new tests are faithful to their cards (no test-side finding, no test edited). Details in "Round 2" just below.
> Tests: 300 passed · 169 xfailed (reproduced ✅) · coverage 99% branch (153 statements, 74 branches, 1 partial; only dead line 307 missed)
> Mutation: 211 mutants · 195 killed · 16 survived → score 100% (195 / 195, after excluding 8 equivalent, 3 dead, 5 bug-path)
> Fidelity of the 39 in scope: 0 unfaithful. The other 430 tests are byte-identical to round 1.
> Hand variants on the updated reference: 276 · 262 caught · 14 survived (9 `case-missing`, 1 open question, 1 equivalent, 3 commit notes)
> Source commit: e48a092 · Cases revision: 4 (469 cases; spec APPROVED)
> Round 1 (2026-10-30): NEEDS WORK. Its report is below, kept as written; its header lines start at "The sections below".

## Round 2 (2026-10-31) — scoped to cases revision 4

Scope: the 39 cards the coordinator named, read line by line against their cards and against spec R4, R4a, R2a, R3a, R9, R28e (G3, G13, G14): D-55 … D-63, D-78 … D-90, E-07, E-08, E-10, E-11, E-16, E-17, E-27, E-28, E-39, E-41 … E-44, U-138, U-139, S-114, S-115. The other 430 tests were re-run, not re-read.

### Summary
- **The 39 tests can be trusted as written.** Each Given row, When call and numbered Then line matches its card, in order. A diff against the round 1 file shows exactly the 18 changed cards' tests changed, 21 added, and the one new helper `mk_ix`, which matches Conventions. All are `# [claude]`.
- **Round 1's findings 1–9 are closed.** The variants behind the 13 gap recipes each fail the card meant for them, and the two mutants are killed by S-114 and S-115 (table below).
- **The false-kill doubt is cleared.** A full mutation run gives 195 killed, 16 survived. Each survivor is one of round 1's, and #210, #211 are the only status changes. No variant run shows a setup error.
- **Why the verdict is still NEEDS WORK:** the corrected R4 brought new rules, and 9 variants that break them pass every test. They fall into 3 groups, all for the case designer. Scratch tests show each closes with a small card.
- **One owner question** (order workflow) is open: R2a and a soft-deleted order. No money question arises.

### Findings
| # | Kind | Rule | What is wrong | Evidence (survives every test) | Fix by |
|---|---|---|---|---|---|
| R2-1 | case-missing (order workflow) | `delete_machine` R4 "A foreign row that meets no condition (a purchase order at `Complete`, say) does not block" | Only the purchase order has a card (D-66). A fix that treats any foreign stock row, transfer, order or line as in use refuses a machine that is free, and it passes. | `g_nocond_stock` (qty 0), `g_nocond_to` (completed), `g_nocond_wo` (`COMPLETED`), `g_nocond_line` (consumed) | **case designer** |
| R2-2 | case-missing (low) | R4 "**Of another workspace** means: the `machine_items` row, the purchase order or the transfer order has another `workspace_id`; for a work order, the order has…" | D-64, D-85 cover a W1 row on a W2 stage. No card has a W1 row on another W2 parent, so a fix that classifies by the parent passes and hides a row of this workspace behind the generic entry. | `g_item_foreign`, `g_order_factory_foreign`, `g_order_type_foreign`, `g_transfer_end_foreign` | **case designer** |
| R2-3 | case-missing (low) | R4 (c) (ii) with R4a | D-79 has an own order through (c) (i) with a foreign line. No card has an own order through its **own line** plus a foreign line. A fix that drops the own entry passes. R4a states the (i) side only; the (ii) side follows from R4. | `g_ii_own_and_foreign` | **case designer** |
| R2-4 | card note (low) | D-80 Then 5, Then 6 | They check that no id or text of W2 appears. Then 2–4 already fix `args` exactly, so these two cannot fail on their own. The test matches its card. D-78 … D-80 and Then 4 of the others carry the rule. | variants; see "Then lines" | **case designer**, optional |

Still open from round 1: finding 11 (12 schema-only Then lines, optional) and the commit notes (a commit in `get_machine`, in `search_machines`, or in create only without a section, is noticed by no test). Round 1's finding 10 (`mutate.py`) is fixed by the coordinator's change; the reading below supports that.

No fidelity finding.

### Questions for the owner
Order workflow, flagged and not decided:

- **R2a and a soft-deleted work order.** R2a says "Id and workspace only: the order's state and its `machine_id` are not looked at". E-44 proves that for `COMPLETED` and another machine. Whether a **soft-deleted** order of the workspace counts as a state (accepted) or as naming no work order (404) is not stated, and HR-4 hides soft-deleted rows by default. Variant `e_r2a_live` (refuse it) survives, because no card builds one. My reference accepts it, which is a literal reading and not a decision. The only caller passes its own order, so the case is rare. Either answer takes one card.

G14 is recorded in the spec as the coordinator's relay of the owner's answer; I checked the tests against it, not the answer itself.

### Round 1 gaps: does each recipe now fail the right card?
| Round 1 finding | Variant / mutant | Now fails | Expected card |
|---|---|---|---|
| 1 | `c_anysource` | D-81 call | D-81 ✅ |
| 2 | `d_srcend_fact`, `d_srcend_mach` | D-82 T1, D-83 T1 | D-82, D-83 ✅ |
| 3 | `d_stage_complete` | D-84 T1 | D-84 ✅ |
| 4 | `d_stage_ws` | D-85 T1 | D-85 ✅ |
| 5 | `s_desc_b`, `s_desc_d` | D-86 T4, D-87 T4 | D-86, D-87 ✅ |
| 6 | `a_item_live`, `c_line_item_live`, `c_fact_active` | D-88 T1, D-89 T1, D-90 T1 | D-88, D-89, D-90 ✅ |
| 7 | `m_oldfactory` | U-138 T2 | U-138 ✅ |
| 8 | `m_prodline` | U-139 T3 | U-139 ✅ |
| 9 | #210, #211 | S-114, S-115 (each the only failure) | S-114, S-115 ✅ |
| open question | `m_from_machine` | U-138 T6 | U-138 ✅ (G14) |

The 13 round 1 scratch tests still pass on the updated reference, and each of these variants fails exactly the one card shown.

### Hand variants (on the updated reference, `--runxfail`)
The reference now gives the generic entry, BUG-1000 and the order's own `from_value`. Each variant's edit is asserted to apply. `mcmv2\variants.json` has the failing card and Then line of each.

| Group | Variants | Caught | Survivors |
|---|---|---|---|
| BUG-968, round 1 set, ported | 108 | 107 | `r_savepoint`, equivalent as in round 1 |
| Generic entry (R4, R4a) | 24 | 15 | 9: findings R2-1, R2-2, R2-3 |
| BUG-975 | 51 | 51 | none |
| BUG-974 | 6 | 6 | none |
| BUG-1000 (R2a, R9) | 13 | 12 | `e_r2a_live`, the owner question |
| Targeted at later Then lines | 67 | 67 | none |
| Commit spies | 7 | 4 | as in round 1 |

**Generic entry, caught:**
| Variant | Failed by |
|---|---|
| foreign rows listed by id (the withdrawn G3) | D-55 … D-63, D-78, D-79, D-80 T4 |
| no generic entry | D-55 … D-59, D-61 … D-63, D-78 T1; D-60, D-79, D-80 T4 |
| generic entry first / foreign wins / dropped when own rows exist | D-60, D-79, D-80 T4 (each) |
| one per foreign row | D-55, D-57, D-60, D-61, D-78, D-80 T4 |
| with an id / with a count / other type name | the 12 cards above, T4 (each) |
| line's workspace ignored | D-62, D-79 T4 |
| foreign line drops the own entry / adds no generic entry | D-79 T4, only (each) |
| a stage of W2 makes a W1 row foreign | D-64, D-65, D-66 (purchase order); D-85 T4 (transfer) |
| foreign `Complete` purchase order blocks | D-66 call, only |

**BUG-1000, caught:** off E-11, E-28, E-41, E-42 T1, E-43 T2 · any workspace E-41 T1, only · truthy check E-11, E-28 T1 · code T2 and message T3 on E-11, E-28, E-41, E-42, E-43 · after the same-status check E-43 T2, only · before R2 E-05 T2, only · written first T5, event first T4 on the same five · open orders only, or this machine only: E-44 call, only (each) · `work_order_id` dropped from the metadata E-10, E-27, E-44.

### Scratch tests that close the new gaps
8 tests in `mcmv2\prop\test_machine_manager_prop.py`, not in the repo; each passes on the reference and fails only on the variants shown.

| Scratch test | Fails on |
|---|---|
| foreign stock with qty 0 does not block | `g_nocond_stock` |
| foreign completed transfer does not block | `g_nocond_to` |
| foreign `COMPLETED` order does not block | `g_nocond_wo` |
| foreign consumed line on an open order does not block | `g_nocond_line` |
| W1 stock of a W2 item is listed normally | `g_item_foreign` |
| W1 order with a W2 factory and type is listed normally | `g_order_factory_foreign`, `g_order_type_foreign` |
| W1 transfer to a W2 factory is listed normally | `g_transfer_end_foreign` |
| own line plus foreign line: own entry, then the generic one | `g_ii_own_and_foreign` |

### The Then lines the xfails never reach
- 169 xfails have **466 Then lines after the failing line**. None runs today. **All 466 run and pass on the reference: 469 of 469 passed.**
- **442 of the 466 were made to fail on their own line** by some variant.
- **24 cannot fail on their own:** the 22 of round 1, plus D-80 Then 5, 6 (R2-4).

### Reproduced claims
- The notes' Result line matches: 300 passed, 169 xfailed, 99%, only line 307 missed.
- **All 169 xfails fail where and why the card says**, mapped to their `# Then N`. 163 fail on the card's Then line; 6 fail in the When, as their cards say (U-75, U-134, G-06, G-09, S-12, S-39). None is a setup error. The 29 xfails in scope: 26 `DID NOT RAISE` at Then 1; E-08 at Then 3 and E-43 at Then 2 on the message and the 400 their cards name; U-138 at Then 2 on the factory. E-11 and E-28 are pass cards of round 1 that became strict xfail BUG-1000.
- **No flaky test.** 7 runs without `--runxfail` gave 300 passed, 169 xfailed (3 plain, coverage, `-W error`, seqscan off, index and bitmap off). 3 with `--runxfail` gave 169 failed, 300 passed (plain, today-plugin, seqscan off). The non-strict cards stayed xfailed.

### Surviving mutants
Unchanged from round 1's table and classes, without #210, #211, which S-114, S-115 now kill.

| # | Line | Class |
|---|---|---|
| 41, 128, 135, 162, 208 | 146, 160, 283, 287, 299 | bug-path (BUG-954, BUG-962, BUG-958, BUG-973, BUG-973) |
| 48, 49, 113, 127, 159, 161, 190, 207 | 224, 225, 318, 160, 280, 281, 280, 292 | equivalent |
| 103, 138, 139 | 306–307 | dead |

Score: 195 / (211 − 8 − 3 − 5) = **100%**. The numbers are round 1's; the mutants and source are the same, so the re-runs with xfails visible were not repeated, except #210, #211.

### The mutation run
- **The first attempt was cut off** at mutant 22 of 211 and left no JSON. It is not used.
- **The run reported here** covers the same 211 mutants, matched by line, column and change, in five resumable line ranges, `rc=0` for each: 1-146, 147-230, 231-300, 301-400, 401-481. Totals are the sum of the five.
- None of my own runs was live during it. I cannot speak for other agents. The fixed `mutate.py` re-runs error-only results and `factories.py` no longer collides.
- Against round 1's second run: 209 mutants have the same status, 2 changed (#210, #211, as intended). #207, the false kill of round 1, survives again.

### Traceability
cases 469 · tests 469 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Docstrings, Rules and `# Then N` match in all 469. 300 `pass` cards have no marker; 169 xfail cards name the card's bug. BUG-1000 is in `docs/testing/bugs.md`. `ruff check` passes. Rebuild: 1 401 modelled Then lines, no real difference. Its 25 reports are the When's own keywords counted with the Given (U-139's 2 are new, same kind). Selftest: 296 planted, 296 found. Its first run found 295: `IX` was missing from its row list, which masked one plant; corrected.

Local-written tests: 0 of the 39, so no `## Local-coder patterns` entry. Findings in local-written tests / local-written new tests: 0 / 0; in others: 0 / 39 for test-side findings.

### Limits of this round
- **Scope:** the 430 unchanged tests were not re-read; round 1 read them, and they are byte-identical except for line numbers.
- **The reference is mine.** The ported variants were re-pointed at its new code, and `s_w1_first` was dropped, since the generic entry replaces it.
- **The reading used the same condensed listing as round 1**, with no card or test line dropped.
- Pass-card Then lines were not each forced to fail.
- Not exercised: service or HTTP level, a real race, BUG-956. FU-7 (refusing cross-workspace rows when they are created) belongs to other managers.

### Commands run (round 2)
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/machine_manager.py tests/unit/managers/test_machine_manager.py --lines <range> --timeout 300 --json <scratch>/mut_<range>.json
  1-146:   39 · killed 38 · survived 1
  147-230: 33 · killed 29 · survived 4
  231-300: 40 · killed 33 · survived 7
  301-400: 60 · killed 56 · survived 4
  401-481: 39 · killed 39 · survived 0        total 211 · killed 195 · timeout 0 · survived 16

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_manager.py -q -p no:cacheprovider --cov=app.managers.machine_manager --cov-branch --cov-report=term-missing -rX
  app\managers\machine_manager.py     153      1     74      1    99%   307
  300 passed, 169 xfailed, 15 warnings

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_manager.py -q -p no:cacheprovider --runxfail -rf
  169 failed, 300 passed

MCMREF=fix ... -p ref_mcm --runxfail                 469 passed
PGOPTIONS seqscan off | index and bitmap off         300 passed, 169 xfailed (each); --runxfail seqscan off: 169 failed, 300 passed
-W error                                             300 passed, 169 xfailed
git diff --stat app/managers/machine_manager.py      (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mcmv2\`: `plug\`, `prop\test_machine_manager_prop.py`, `variants.json`, `drive.py`, `drive_x.py`, `mutchunks.sh`, `mut.json`, `mut_*.json`, `rebuild.py`, `scope.txt`, `xfloc.txt`, `later.py`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited. No commit. No model server.

### Fix list
1. **Owner:** answer the R2a question.
2. **Case designer:** add cards for R2-1, R2-2, R2-3, about 8, plus one for the answer. R2-4 is optional.
3. **Executor,** after 1–2: implement them and send back for a scoped re-verification.

---

The sections below are round 1 (2026-10-30), kept as written.

> **Verdict:** NEEDS WORK — only the case designer has work: 9 small groups of missing cards. No test is wrong; no test-side finding, no test edited.
> Tests: 297 passed · 151 xfailed (reproduced ✅) · coverage 99% branch (153 statements, 74 branches, 1 partial; only dead line 307 missed)
> Mutation: 211 mutants · 193 killed · 18 survived → score 99% (193 / 195, after excluding 8 equivalent, 3 dead, 5 bug-path; 2 `case-missing` remain)
> Fidelity: **0 of 448 unfaithful as delivered** (448 / 448 right; the local model's figure on the item manager was 164 of 165)
> Hand variants: BUG-968 109 · 98 caught, 11 survived (10 `case-missing`, 1 equivalent) · BUG-975 51 · 48 caught, 3 survived (2 `case-missing`, 1 open question) · BUG-974 6 · 6 caught
> Source commit: e48a092 · Cases revision: 3 (448 cases; spec APPROVED)

## Summary
- **The generated tests can be trusted as written.** I read all 448 tests against their cards: every Given row, When call and numbered Then line, plus the helpers and fixtures once. I did not reuse the executor's generator. No mistake turned up in a single test or repeated across tests: no swapped row, no snapshot of the wrong object, no weakened or vacuous-by-mistake check, no extra mock.
- **The evidence goes beyond reading.** A reference fix written from the spec passed 448 of 448 on its first run. A separate rebuild of the Then lines and Given values reported no real difference, and it finds 292 of 292 planted mistakes. Every one of the 151 xfails fails today for the reason its card gives; none is a setup error.
- **Why NEEDS WORK:** rules with no card. 2 mutants and 12 hand variants break a written rule and no test notices. They fall into 9 groups, all for the case designer. Scratch tests show each is closed by one small card.
- **One owner question** (order workflow) is open; see "Questions for the owner". No money question arises.
- **One tool warning:** `mutate.py` counts a setup error as a kill. It produced one false kill in my first run; see Finding 10.

Written by Claude (all 448 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 448. No `machine_manager.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence (survives every test) | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `delete_machine` R4 (c)(ii) `source_location_id` = the machine | No card has a line sourcing from a **third** machine. D-29 changes the location type, never the id. A fix that drops the id check refuses a machine with nothing to do with the order. | `c_anysource` | **case designer** |
| 2 | case-missing (order workflow, owner's gap 12) | R4 (d) "The other end may be a soft-deleted factory or a soft-deleted machine" | D-70 and D-71 build only machine → deleted end. No card has a deleted end → machine, so half of the owner's rule is unchecked. | `d_srcend_fact`, `d_srcend_mach` | **case designer** |
| 3 | case-missing | R4 (d) reads `completed_at` only | No card has a transfer at stage `Complete` with `completed_at` NULL. D-32 sets `completed_at`. | `d_stage_complete` | **case designer** |
| 4 | case-missing | R4 intro, blocking by id only | The mixed shapes D-61 … D-66 cover stock, lines and purchase orders, not a transfer on a stage of another workspace. | `d_stage_ws` | **case designer** |
| 5 | case-missing | R4a "then `id` ascending" | Only stock (D-36) and work orders (D-37) have two rows of a type. | `s_desc_b`, `s_desc_d` | **case designer** |
| 6 | case-missing (low) | R4 intro "The state of what a blocker points at, other than this machine, is not looked at" | Only a soft-deleted factory or machine is built. No card has an inactive item on stock or a line, or an inactive order factory. | `a_item_live`, `c_line_item_live`, `c_fact_active` | **case designer** |
| 7 | case-missing (order workflow) | `update_machine` R28 "**every** row" | Each order on a card sits in the machine's old factory. A fix that filters on the old factory passes and leaves an order behind. | `m_oldfactory` | **case designer** (the `from_value` of that card waits for the question below) |
| 8 | case-missing (low) | `update_machine` Side effects; FU-10 "not changed here" | No card has a production line on a moved machine. | `m_prodline` | **case designer** |
| 9 | case-missing | `search_machines` R21 "every filter of R1" | S-100 searches by name only, so the model number and manufacturer parts are never reached. | mutants #210, #211 | **case designer** |
| 10 | tool | `tests/unit/_tools/mutate.py` | A run counts as a kill on any non-zero exit, a setup error included. My first run reported #207 killed after 48 passing `update_machine` tests, which cannot reach that line; alone it gives 297 passed. Two variant runs showed the same kind of error, as setup failures on the subscription plan insert of the first test. The likely cause is concurrent pytest processes colliding on the per-process `plan-{n}` names of `tests/unit/factories.py`; I did not prove that. The score above is from a second full run, checked against the first: 192 of the 193 kills land at the same test position in both runs, which a random setup error would not do, and #177 fails at a plausible card (C-24 region) in the second. | `mut.json` vs `mut2.json`, 1 status differs | **tool owner** (count `ERROR` apart from `FAILED`). Any score measured while another run was live, the item manager's included, may hold a false kill. Comparing two runs finds it |
| 11 | card note (low) | C-16, C-17, C-18, C-20, C-22, U-19, U-20, U-29, U-31, U-35, U-36, U-37 Then 2 | These 12 lines check that nothing was written, but the When only builds a schema and `M` is not called. They cannot fail. The tests match their cards, so this is not a test fault. | "Then lines the xfails never reach" | **case designer**, optional |

No fidelity finding. Nothing here decides order workflow: each of findings 1–9 is a rule already written, except the question below.

### Scratch tests that close the gaps
13 tests in `mcmv/prop/test_machine_manager_prop.py`, not in the repo. Each passes on the reference and fails on the variants shown. The two of finding 9 also pass today.

| Scratch test | Fails on |
|---|---|
| a line sourcing from a third machine does not block | `c_anysource` |
| transfer **to** the machine from a deleted factory blocks | `d_srcend_fact` |
| transfer **to** the machine from a deleted machine blocks | `d_srcend_mach` |
| transfer at stage Complete, `completed_at` NULL, blocks | `d_stage_complete` |
| W1 transfer on a W2 stage blocks | `d_stage_ws` |
| two purchase orders / two transfers, ids ascending | `s_desc_b` / `s_desc_d` |
| inactive item on stock and on a line blocks | `a_item_live`, `c_line_item_live` |
| order in an inactive factory blocks | `c_fact_active` |
| an open order not in the machine's old factory moves | `m_oldfactory` |
| a production line keeps its factory | `m_prodline` |
| `include_deleted` search on model number / manufacturer | #210 / #211 |

## Questions for the owner
Order workflow, flagged and not decided:

- **R28e `from_value` for an order that is not in the machine's old factory.** R28 moves every open order. R28e says `from_value` is "`<old factory id>`". For an order whose `factory_id` already differs from the machine's, this could be the **order's own** old factory or the **machine's**. Variant `m_from_machine` (the machine's) survives, because every card has the two equal. My reference uses the order's own, which is one reading and not a decision. The answer sets the Then line of the card in finding 7.

Already flagged in the cases file and unchanged: G3, the item answer applied by Claude to machines. No money question arises.

## Surviving mutants
Each survivor was re-run alone with xfails visible, except the three dead lines, where a strict XPASS counts as a failure.

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 41 | 146 | `name and name != current` → `or` | bug-path (BUG-954) | Re-sends the same name through the check. U-47 XPASSes, nothing else changes. Resolves with the fix. | — |
| 48 | 224 | default `sort_by` `"name"` → `""` | equivalent | The DAO falls back to name for an unknown key; `""` is not `"maintenance_date"`. Re-run identical. | — |
| 49 | 225 | default `sort_dir` `"asc"` → `""` | equivalent | Only exactly `"desc"` is descending. Re-run identical. | — |
| 103, 138, 139 | 306–307 | the `"all"` branch inside `matches_window` | dead | P9, on the dead-code list. | — |
| 113 | 318 | `!= "all"` → `!= ""` | equivalent | With `"all"` the filter runs and the then-live branch keeps every machine; with `""` skipping and filtering both keep all. Re-run identical. | — |
| 127 | 160 | `exclude_unset` `True` → `False` | equivalent | `exclude_none` stays and every field defaults to `None`. Re-run identical. | — |
| 128 | 160 | `exclude_none` `True` → `False` | bug-path (BUG-962) | U-15, U-16, U-17 XPASS. | — |
| 135 | 283 | `10_000` → `10_001` | bug-path (BUG-958) | S-40, S-41 XPASS. S-42 is the 10 000 side. | — |
| 159 | 280 | `"name"` → `""` | equivalent | DAO fallback to name. Re-run identical. | — |
| 161 | 281 | `"asc"` → `""` | equivalent | Not `"desc"`, so ascending. Re-run identical. | — |
| 162 | 287 | `365` → `366` | bug-path (BUG-973) | S-49, S-54 XPASS. | — |
| 190 | 280 | `"maintenance_date"` → `""` | equivalent | The value reaches the DAO, which falls back to name; `sort_dir` is handled on line 281. Re-run identical. | — |
| 207 | 292 | `3650` → `3651` on `dates_map` | equivalent | Past dates in `dates_map` are never read: upcoming checks start at today, and overdue uses the other map. Re-run identical. | — |
| 208 | 299 | `3650` → `3651` on the overdue map | bug-path (BUG-973) | S-52 XPASSes. | — |
| 210, 211 | 247, 248 | `s in …` → `not in` (`include_deleted` search on model number / manufacturer) | **case-missing** | Finding 9. | **case designer** |

Score: 193 / (211 − 8 equivalent − 3 dead − 5 bug-path) = 193 / 195 = **99%**.

## Hand variants
Each was run on the reference with `--runxfail` against the cards of its method. "T" = the Then line that failed; "call" = the When of a pass card. All edits are asserted to apply, so no variant can be a silent no-op. `mcmv/variants.txt` lists 231; `x_g4_code`, `x_g4_msg`, `x_u13_ord` and the corrected `x_971_clear` came from `rerun.sh` and show there in their earlier state or not at all.

**`delete_machine` R4, R4a, R4b (BUG-968): 109 · 98 caught**
| Group | Variants | Caught by |
|---|---|---|
| (a) stock | off, `> 0` only, any qty, `req_qty` / `defective_qty` block, any machine, row and item workspace checks | D-13, D-14, D-15, D-16, D-55, D-60, D-61 |
| (b) purchase order | off, type ignored, voided blocks, Complete blocks | D-17, D-20, D-19, D-18, D-65, D-66 |
| (b) workspace and stage | row filter; stage on the row's or the machine's workspace, inner and outer join | D-56, D-64, D-65, D-66 |
| (c) work order | either path off, each status alone or added, deleted order or line, `uses_inventory`, consumed, source type | D-21 … D-29, D-73 … D-77 |
| (c) workspace shapes | filter on order, line, line against order, order's machine | D-58, D-59, D-62, D-63 |
| (c) soft-deleted and absent | order's factory live, order's machine live, machine required | D-69, D-72, D-77 |
| (c) consumed mixes | (i) exempted by a consumed line; (ii) one consumed line exempts the order | D-73, D-74 |
| (d) transfer | either end off, completed blocks, either type ignored, workspace, deleted destination end | D-30 … D-33, D-57, D-60, D-70, D-71 |
| Sort | alphabetical, id only, first only, swapped types, stock last, W1 first, ids descending for stock and work orders | D-36, D-37, D-38, D-60 |
| Dedupe and ids | one entry per line, line id for order id | D-23, D-34, D-39, D-59, D-62, D-63, D-72, D-73, D-74 |
| Form | message, one or three args, tuple, extra key, string id, `HTTPException`, each type name | 25+ cards T2, T3 or T4 |
| Refusal before write | row written (T5), event written (T6), stock / order / PO / transfer / line changed (T7–T10) | D-13 … D-77; `D-41` alone sees a dirty object (T5), a flushed stamp (T1) |
| Check order | blockers before R1 / R2 / R3 | D-67, D-09, D-11 |
| Inactive factory | refused, or exempt from blocking | D-12, D-68 |
| R4b made to block | maintenance log, event, ledger, template, production line, formula stage, link, running | D-42 … D-47, D-03, D-04, one each |
| Writes on success | stock rows, orders, lines, stamp, link, `is_running` | D-15, D-24 … D-29, D-75, D-76, D-02, D-03, D-04 |

Survivors: findings 1–6 (10 variants) and `r_savepoint`, **equivalent**: written in a savepoint, rolled back, then the same refusal, so no write stays and the session is usable.

**`update_machine` R28–R28f (BUG-975): 51 · 48 caught**
| Group | Variants | Caught by |
|---|---|---|
| R28a exclusions | `COMPLETED`, `VOIDED`, deleted, other machine with a sourcing line, other workspace, each moved | U-102, U-103, U-104, U-105, U-106; U-101 T4–T7 |
| R28 open states | `DRAFT` only, `IN_PROGRESS` only, first order only | U-98, U-99, U-101, U-128, U-131 |
| R28b calls | same factory, no move, before the name / factory / deleted checks, after the section | U-107, U-108, U-111 … U-119 |
| R28e count | none, two per order, first order only, events for closed orders | U-127, U-128, U-101 T8, U-102, U-103 |
| R28e payload | extra key, extra change, swapped, ints, label, field, description, type, performer | U-127 T3–T5, U-129 T4 |
| Stamps | `updated_by` missing or wrong | U-98 T4, U-131 T4 |
| R28c, R28d lines | consumed or unconsumed, storage or machine, each re-pointed | U-122, U-123, U-124, U-125, U-132 |
| R28d approvals | rows removed, reset, order's stamps, `required_approvals` | U-126 T2, T4, U-100 T4 |
| Other columns | assignees, `assigned_to`, title, status, date, machine, ledger | U-136, U-100, U-131, U-132 |
| Commit, machine log | commit; factory dropped from the log | U-67 … U-72, U-78, U-119, U-120; U-66, U-80 … U-82, U-93, U-130 |

Survivors: `m_oldfactory` and `m_prodline` (findings 7, 8), `m_from_machine` (the owner question).

**`create_machine_event` (BUG-974): 6 · 6 caught.** Every call refused E-10, E-11; `not work_order_id` E-11; off E-07, E-08; inactive refused E-09; before R2 E-06; written first E-07, E-08 T5.

**Commit spies: 7, 4 caught.** A commit in create, update, delete and event is caught by C-51, U-121 and U-135, D-54, E-40. Not noticed, no verdict impact, the same open notes as the item manager: a commit in `get_machine`, a commit in `search_machines`, and a commit in create taken only without a section (C-51 sends one).

**Targeted variants: 61, all caught.** Each refusal's code, message, activity event, stamp or order event, used for the table below.

**Only one card notices** (keep in mind when a card is edited): D-14, D-16, D-19, D-20, D-25, D-26, D-28, D-29, D-31, D-32, D-33, D-41, D-56, D-61, D-64, D-68, D-69, D-72, D-73, D-74, D-75, D-76, D-77, D-42 … D-47; U-106, U-107, U-119, U-123, U-124, U-125, U-126, U-132, U-136; E-06, E-09, E-11.

## xfail tests against the reference
`mcmv/plug/ref_mcm.py` is a pytest plugin that swaps the source of `app.managers.machine_manager`, `app.schemas.machine` and `app.dao.machine` in memory through a meta-path finder, built by asserted text edits in `refsrc.py`. Nothing is written to `app/`. It fixes BUG-886 … BUG-892, BUG-909, BUG-950 … BUG-955, BUG-957 … BUG-968, BUG-970 … BUG-975 and creates the BUG-953 partial unique index inside each test's transaction. BUG-956 is integration-only.

**448 passed**, twice with `--runxfail`: every xfail passes in full, and no pass test pins a bug.

### The Then lines the xfails never reach
- 151 xfails have **360 Then lines after the failing line**. None runs today. All 360 pass on the reference.
- **338 of the 360 were made to fail on their own line** by some variant.
- **22 cannot fail on their own** and are not test faults:
  - the 12 schema lines of finding 11;
  - C-37, C-38 T2, C-41 T4, T5, U-51 T4, T5: the card's own `begin_nested` has already rolled the write back;
  - U-119 T8, U-121 T5: a write would have to survive `sp.rollback()`;
  - U-128 T4: follows from T2, T3 unless an event lands on a third order;
  - U-79 T4: T3's `links_of` runs `expire_all`, so a missing expire cannot show there. U-63 and U-64 cover that.

## Reproduced claims
- The notes' Result line matches: 297 passed, 151 xfailed, 99%, only line 307 missed.
- **All 151 xfails fail where and why the card says**, mapped to their `# Then N` and read against each card's parenthesis. 145 fail inside the card's Then. 6 fail in the When, before `# Then 1`, as those cards say ("the call raises …"): U-75, U-134, G-06, G-09, S-12, S-39. None is a setup error.
- **No flaky test.** 7 runs without `--runxfail` gave 297 passed, 151 xfailed (3 plain, coverage, seqscan off, index and bitmap off, `-W error`). 3 with `--runxfail` gave 151 failed, 297 passed (plain, today-plugin, seqscan off). The 6 non-strict cards stayed xfailed.
- Mocks: `app.dao.machine.utcnow` everywhere; `_check_name_exists_in_factory` in C-41, U-51 only; commit spies in C-51, U-135, D-54, E-40. No broad `pytest.raises`, no `try` around an action (the one `try` is `record_sql`'s cleanup), no `if` in a test body.

## Traceability
cases 448 · tests 448 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules. `# Then N` numbers match the card in all 448. 297 `pass` cards have no marker; 151 xfail cards name exactly the card's bug, 145 strict, 6 non-strict (S-88, S-107 … S-111). All 38 BUG IDs in the cards are in `docs/testing/bugs.md`. All 448 sit under `# [claude] <ID>`. `ruff check` passes.

## Limits of this round
- **How the reading was done.** I read a condensed listing of card and test side by side, with no card or test line dropped. Where the When call equals the card's exactly, after lowering row names, it was shown once. That equality was mechanical; the other lines were read.
- **Two of my own tools were wrong at first, and both are corrected.** The first listing reported 5 missing `# Then 1` comments in C-16 … C-22; it had skipped the comment after the docstring, so there was no such fault. The rebuild first gave 25 reports, then 23, all its own normalisation; the 23 that remain are When keywords counted with the Given.
- **The rebuild is an extra check.** It models 1 283 of 1 442 Then lines; the other 159 (mainly `raises:` lines and `sql:` lines) were read only.
- **The reference is one fix, mine.** Variants show what these tests catch around it. Another correct fix could expose a card that assumes something mine happens to do.
- **Pass-card Then lines were not each forced to fail**, unlike the xfails' later lines. They rest on mutation and the variants.
- **The mutation runs were not isolated.** During the first, my reference runs held a `SHARE` lock on `machines` per test, which may have slowed other agents' runs or added to the setup errors of finding 10. During the second I ran only index-free checks, but those were still concurrent pytest processes, and another agent may have been running too. So the score rests on the agreement of the two runs, not on either being clean.
- Not exercised: anything at service or HTTP level, a real race (BUG-960), BUG-956.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/machine_manager.py tests/unit/managers/test_machine_manager.py --timeout 300 --json <scratch>/mut.json
  Mutants: 211 · killed 194 · timeout 0 · survived 17 · score 92%      (with other runs live; #207 is a false kill)
same, --json <scratch>/mut2.json
  Mutants: 211 · killed 193 · timeout 0 · survived 18 · score 91%      (raw; the run used above, compared with the first)
  SURVIVED #41 #48 #49 #103 #113 #127 #128 #135 #138 #139 #159 #161 #162 #190 #207 #208 #210 #211

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_manager.py -q -p no:cacheprovider --cov=app.managers.machine_manager --cov-branch --cov-report=term-missing -rX
  app\managers\machine_manager.py     153      1     74      1    99%   307
  297 passed, 151 xfailed, 15 warnings

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_manager.py -q -p no:cacheprovider --runxfail -rf
  151 failed, 297 passed

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_manager.py -q -p no:cacheprovider --tb=no     (3 times, and with -W error)
  297 passed, 151 xfailed

PGOPTIONS="-c enable_seqscan=off" | "-c enable_indexscan=off -c enable_bitmapscan=off"
  297 passed, 151 xfailed (each); --runxfail with seqscan off: 151 failed, 297 passed

MCMREF=fix ... -p ref_mcm --runxfail      448 passed     (twice)
rebuild.py                                1 283 modelled Then lines, no real difference
rebuild.py --selftest                     292 planted, 292 found, 12 kinds
.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_machine_manager.py     All checks passed!
git diff --stat app/managers/machine_manager.py                                        (empty)
```
Scratch, all under `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\mcmv\`: `plug\ref_mcm.py`, `plug\refsrc.py`, `plug\variants.py`, `plug\variants2.py`, `drive.py`, `drive_x.py`, `y.sh`, `rerun.sh`, `variants.txt`, `variants.json`, `xfloc.py`, `xfloc.txt`, `later.py`, `rebuild.py`, `listing.py`, `compact.py`, `prop\test_machine_manager_prop.py`, `prop_drive.sh`, `mut.json`, `mut2.json`.

Only this report was written in the repo. Nothing under `app/`, the spec, the cases file, the notes or the test file was edited (the test file is byte-identical to the delivered copy). No commit. No model server.

## Fix list
1. **Case designer:** add cards for findings 1–9, about 12 or 13 cards; the scratch tests above are the recipes. Findings 2, 7 touch order workflow; their rules are written, apart from the question above. Finding 11 is optional.
2. **Owner:** answer the R28e `from_value` question.
3. **Executor,** after 1–2: implement the new cards and send back for re-verification.
4. **Tool owner:** finding 10.
