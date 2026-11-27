# Verification — `app/dao/attachment_link.py`

> **Current verdict: PASS** (round 2, 2026-11-03, revision 1). See "Round 2" at the end. The rest of this block is round 1.
>
> **Verdict:** NEEDS WORK — only the case designer has work. No test is wrong.
> Tests: 63 passed · 7 xfail, 4 strict, 3 non-strict (reproduced ✅) · coverage 96% branch (24 statements; the one miss is the dead `get_by_entity`)
> Mutation: 33 mutants · 27 killed · 6 survived → score 100% (after excluding 0 equivalent, 6 dead, 0 bug-path)
> Fidelity: **0 of 70 unfaithful** (70 / 70 right)
> Hand variants: 61 · 46 caught by a pass card · 15 others: rule gaps in Findings, the rest under "Considered and not listed"
> Source commit: e48a092 · Cases revision: none; spec APPROVED

## Summary
- **The tests can be trusted as written.** I read all 70 against their cards; all match, and the script agrees.
- **Why NEEDS WORK:** the case designer has work. Hand variants show 4 rule gaps; the largest is the count's exact compare of `entity_type`, which has only the capitals card.
- **Weak card ALK-GA-30** (the brief calls it ATT-GA-30; no ATT-GA-30 exists): not a gap. See Rulings.

Written by Claude (all 70 under `# [claude]`). Findings in local-written tests / local-written tests: 0 / 0. In others: 0 test-side / 70. No `attachment_link.local-run.json` exists, so there is no `## Local-coder patterns` section.

## Findings
| # | Kind | Rule | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `count_linked_attachments_for_entity` R3 ("matching as `get_attachments_for_entity` R1": exact compare) | CN-06 tests capitals only. The count is its own query, not a filter shared with the list, so the list's GA-05 to GA-08 do not cover it. | `cn_txt_like`, `cn_txt_contains`, `cn_txt_startswith`, `cn_txt_endswith`, `cn_txt_strip`, `cn_txt_trimcol` pass all 70. Recipe R-1. | **case designer** |
| 2 | case-missing | `count_linked_attachments_for_entity` R3, `get_links_for_attachment` R2 (another workspace) | Every isolation card asks for W1 with the other row in W2, the later id. A `<=` on the link's `workspace_id` leaks the earlier workspace's rows. | `cn_ws_le`, `gl_ws_le` pass all 70. `>=` is caught. Recipe R-2. | **case designer** |
| 3 | case-missing | `get_links_for_attachment` R4 [BUG-1433] (`id` ascending) | GL-07 gives the links entity ids 1, 2, 3, rising with `id`, so ordering by `entity_id` is not told apart (skill step 1b, sort keys). GL-08 then passes too, because the tail `.id` is there. | `gl_ord_entity` (`entity_id, id`) passes all 70, with `--runxfail` too. Recipe R-3. | **case designer** |
| 4 | case-missing | `get_links_for_attachment` Side effects: none | GL-10 has no `"FOR UPDATE" not in sql.upper()` line, unlike GA-32. | `gl_w_forupdate` passes all 70. Recipe R-4. | **case designer** |

No fidelity finding.

### Scratch cards that close the gaps
In `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\prop\prop_attachment_link.py`, not in the repo, run by `propdrive.py` in a temporary copy of the backend. Each passes on today's code (the xfail ones xfail or xpass, as non-strict allows) and on my reference with `--runxfail`. Each named variant fails its recipe.

| Recipe | Where | Given and When | Then | Expect | Fails on |
|---|---|---|---|---|---|
| R-1 | five new cards ALK-CN-12 … CN-16, `count_linked_attachments_for_entity` R3 | CN-12: A = attachment; link on A; B = attachment, but `file_name "b.png"`; link on B, but `entity_type "purchase-order"`; When `entity_type="purchase_order"`. CN-13: A; link on A; When `entity_type="purchase"`. CN-14: the same, When `entity_type="order"`. CN-15: the same, When `entity_type=" purchase_order"`. CN-16: A; link on A; B as in CN-12; link on B, but `entity_type " purchase_order"`; When `entity_type="purchase_order"`. Each with `workspace_id=W1.id, entity_id=501` | CN-12, CN-16: `result == 1`. CN-13, CN-14, CN-15: `result == 0` | pass | CN-12 `cn_txt_like`; CN-13 `cn_txt_contains`, `cn_txt_startswith`; CN-14 `cn_txt_contains`, `cn_txt_endswith`; CN-15 `cn_txt_strip`; CN-16 `cn_txt_trimcol` |
| R-2 | two new cards ALK-CN-17, ALK-GL-11, R3 / R2 | CN-17: A = attachment; link on A; B = attachment, but `file_name "b.png"`; link on B, but `workspace_id W2.id`; When `count_linked_attachments_for_entity(db, workspace_id=W2.id, entity_type="purchase_order", entity_id=501)`. GL-11: A = attachment; LA = link on A; LZ = link on A, but `workspace_id W2.id`, `entity_id 502`; When `get_links_for_attachment(db, workspace_id=W2.id, attachment_id=A.id)` | CN-17: `result == 1`. GL-11: `ids(result) == [LZ.id]` | pass | CN-17 `cn_ws_le`; GL-11 `gl_ws_le` |
| R-3 | new card ALK-GL-12, R4 [BUG-1433] | A = attachment; L1 = link on A, but `entity_id 9`; L2 = link on A, but `entity_id 5`; L3 = link on A, but `entity_id 7`; When `get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)` | 1. `len(result) == 3`. 2. `ids(result) == [L1.id, L2.id, L3.id]` | xfail BUG-1433 (non-strict); Fails today on: Then 2 when the physical order differs (it passed today in my run, which non-strict allows) | `gl_ord_entity` fails Then 2 |
| R-4 | ALK-GL-10, one more Then line | unchanged | 7. statement: `"FOR UPDATE" not in sql.upper()` (before the `nothing written:` line, which becomes 8) | pass | `gl_w_forupdate` |

## Rulings asked for
- **ALK-GA-30 (brief: ATT-GA-30): no change needed.** I ran the executor's exact order, `uploaded_at DESC, file_name DESC, id` (extra variant `ga_ord_name2`, not in the table): GA-30 passes it, all 70 reached, and GA-28 and GA-29 fail it. A fix that gives that order still turns GA-30 `XPASS(strict)` and the run red, and the notes say to remove the markers of GA-28, 29 and 30 together. GA-28 and GA-29 then become pass cards and fail it. The rule is pinned once the fix lands. Tightening GA-30 would only move the alarm earlier.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L42–64 | 6 mutants in `get_by_entity` (return, two consts, three `==`) | dead | Not specified: dead code to be removed (P3) | — |

**Guard.** My own driver (`drive.py muts`) re-ran every mutant of mutate.py's own list with no `-x`. Every run reached every pass test, with no collection or setup error, and each kill or survival matched mutate.py's.

## Hand variants
My reference fix and the variants are a pytest plugin, `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\plug\attvref.py` (`-p attvref`). It replaces the DAO's methods in-process with the spec's intended behaviour, bug rules included; nothing is written to `app/`. Runs used `--runxfail` on the default plan. Every variant was asserted to be applied, and every run reached all 70 tests. Group = the method's tag.

| Group | Variants | Pass card | Cards that fail | Others |
|---|---|---|---|---|
| ga | 26 | 24 | ALK-GA-04, ALK-GA-05, ALK-GA-06, ALK-GA-07, ALK-GA-08, ALK-GA-09 … | `ga_ord_id_asc`, `ga_ord_name` |
| gae | 2 | 2 | ALK-GA-02, ALK-GA-16, ALK-GA-17 | — |
| cn | 18 | 10 | ALK-CN-02, ALK-CN-03, ALK-CN-06, ALK-CN-07, ALK-CN-11 | `cn_ws_le`, `cn_txt_like`, `cn_txt_contains`, `cn_txt_startswith`, `cn_txt_endswith`, `cn_txt_strip`, `cn_txt_trimcol`, `cn_failed_counts` |
| cne | 2 | 2 | ALK-CN-04, ALK-CN-08, ALK-CN-09 | — |
| gl | 12 | 8 | ALK-GL-02, ALK-GL-03, ALK-GL-04, ALK-GL-05, ALK-GL-06, ALK-GL-09 … | `gl_ws_le`, `gl_ord_entity`, `gl_ord_desc`, `gl_w_forupdate` |
| cr | 1 | 0 | — | `cr_db_clock` |
| **Total** | **61** | **46** |  | **15** |

### Considered and not listed
| Variants | Why it is not a finding |
|---|---|
| `ga_ord_id_asc`, `ga_ord_name` | **Bug path.** Wrong tie orders; GA-28, GA-29 and GA-30 all fail them. |
| `gl_ord_desc` | **Bug path.** GL-07 and GL-08 fail it. |
| `cn_failed_counts`, `cr_db_clock` | **Bug path.** Today's BUG-1434 and BUG-1431 behaviour; CN-01 Then 2 and CR-02 Then 3 fail, as designed. |

## xfail tests against the reference
With `--runxfail` on the reference: 70 passed. **The alarm works:** with the markers on, every strict card is `XPASS(strict)`.

| Cards | Marker | Fails today on (`--runxfail`, my script mapping the failing line to its `# Then N`) |
|---|---|---|
| ALK-GA-28, GA-29 | non-strict | Then 2 |
| ALK-GA-30 | strict | Then 3 |
| ALK-CN-01 | strict | Then 2 |
| ALK-GL-07 | non-strict | Then 2 (XPASS under `enable_seqscan=off`, as the notes say) |
| ALK-GL-08 | strict | Then 2 |
| ALK-CR-02 | strict | Then 3 |

Each fails on the line its card's "Fails today on" names.

## Reproduced claims
- **Result line of the notes holds:** `63 passed, 7 xfailed` in 3 of 3 default runs, the coverage run among them, and again in the mutation and variant bases. No flaky test.
- **Mocks:** only those the Conventions name (the commit spy). No `try`, no broad `pytest.raises`. `ruff check` passes.

## Traceability
cases 70 · tests 70 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring equals its card's ID, title and Rules (several end with a period the card lacks; cosmetic). `# Then N` numbers match the card. Every BUG ID is in `docs/testing/bugs.md`. All tests sit under `# [claude] <ID>`.

My own script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\tools\rebuild.py`) compares each test with its card by AST and by text: name, docstring, marker, the When call's arguments, each Given line in order, each Then line's expression, operators and literals. Over the 433 cards of this batch it leaves no unexplained report; each report it gave was read by eye. Eye-read here: the whole file, against every card. Selftest: 1306 of 1334 planted mistakes of 22 kinds reported. The 28 it misses are values inside pending-row code lines and re-read lines that go through a helper; those lines were read by eye in every module.

## Limits of this round
- **The reference and the variants are mine.** They show what these tests catch around them, not every possible break.
- **Runs were not isolated.** Other agents may have been live on the shared test database. Each kill is a plain `N failed`.
- **Variants ran on the default plan only**, not under forced plans; the order cards' plan sensitivity is the executor's notes'.
- **Not exercised:** manager, service or HTTP level; a real race.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/attachment_link.py tests/unit/dao/test_attachment_link.py --timeout 300 --json <scratch>/res/mut_attachment_link.json   (through runmut.sh)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_link.py -q -p no:cacheprovider --cov=app.dao.attachment_link --cov-branch --cov-report=term-missing   (private COVERAGE_FILE)
  63 passed, 7 xfailed; then 2 more default runs and one --runxfail run
drive.py bases | muts | vars <module>; xfline.py; propdrive.py; rebuild.py; rebuild.py --selftest 8
.venv/Scripts/python.exe -m ruff check <the ten test files>     All checks passed!
git diff --stat -- app/dao                                   (empty)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was written in the repo. No commit. Nothing was stopped or killed.

## Fix list
1. **Case designer:** add the recipes above; the Givens and Thens are written out.
2. **Executor,** after 1: implement them and send back for re-verification.

## Round 2 — 2026-11-03 (revision 1, narrow)

> **Verdict:** PASS
> Tests: 70 passed, 7 xfailed, 1 xpassed (reproduced ✅) · coverage 96% branch (the miss is still the dead `get_by_entity`)
> Mutation: not re-run; round 1 stands
> Fidelity: **0 of 78 unfaithful** (the new and changed tests read by eye; all 78 compared by script)
> Source commit: e48a092 · Cases revision: 1; spec APPROVED, unchanged

Every finding of round 1 is closed. No new rule gap. No test or card edited in this round, no commit.

- **New cards:** ALK-CN-12 … CN-17, GL-11, GL-12. **Changed:** ALK-GL-10 (Then 7 added, `nothing written` now Then 8). Each new or changed test was read against its card and matches it, its recipe included.
- ALK-GL-12 XPASSes today, as its non-strict card allows ("can match by accident"); it is the one XPASS of the batch.
- **xfail:** ALK-GL-12: non-strict; passed today in my runs, which its card allows.

### Gap variants against the new cards
Each round 1 gap variant ran on my reference with `--runxfail` on three plans: default; `enable_seqscan=off`; index, bitmap and index-only scans off. "Fails" means the named card failed in all three runs. Every run reached all tests.

| Variant | Card that must fail | Plans where it failed |
|---|---|---|
| `cn_txt_like` | ALK-CN-12 | default, seqoff, idxoff (3 of 3) |
| `cn_txt_contains` | ALK-CN-13, ALK-CN-14 | default, seqoff, idxoff (3 of 3) |
| `cn_txt_startswith` | ALK-CN-13 | default, seqoff, idxoff (3 of 3) |
| `cn_txt_endswith` | ALK-CN-14 | default, seqoff, idxoff (3 of 3) |
| `cn_txt_strip` | ALK-CN-15 | default, seqoff, idxoff (3 of 3) |
| `cn_txt_trimcol` | ALK-CN-16 | default, seqoff, idxoff (3 of 3) |
| `cn_ws_le` | ALK-CN-17 | default, seqoff, idxoff (3 of 3) |
| `gl_ws_le` | ALK-GL-11 | default, seqoff, idxoff (3 of 3) |
| `gl_ord_entity` | ALK-GL-12 | default, seqoff, idxoff (3 of 3) |
| `gl_w_forupdate` | ALK-GL-10 | default, seqoff, idxoff (3 of 3) |

**Reference bases, `--runxfail`:** default: 78 of 78 passed, seqoff: 78 of 78 passed, idxoff: 78 of 78 passed.

### Reproduced
- `70 passed, 7 xfailed, 1 xpassed` in the coverage run. The ten files together gave `411 passed, 50 xfailed, 1 xpassed` in 2 of 2 runs, matching the coordinator's line. No flaky test.
- `ruff check` passes. `rebuild.py` over the ten files reports nothing beyond round 1's known alias noise. `git diff --stat -- app/dao` is empty.

### Commands run
```
rebuild.py <ten modules>; show.py <module> <new and changed ids>     read against the cards
round2.py                                                          gap variants and bases, 3 plans
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_link.py -q -p no:cacheprovider --cov=app.dao.attachment_link --cov-branch   (private COVERAGE_FILE)
.venv/Scripts/python.exe -m pytest <the ten test files> -q -p no:cacheprovider     x2
xfline.py; .venv/Scripts/python.exe -m ruff check <the seven test files>
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attv\`. Only this report was edited in the repo. Nothing was stopped or killed.
