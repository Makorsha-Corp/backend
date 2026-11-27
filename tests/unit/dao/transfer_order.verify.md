# Verification — `app/dao/transfer_order.py`

> **Current verdict (Round 2, 2026-11-14, cases Revision 3):** PASS — 210 passed · 57 xfailed (reproduced ✅, 3 runs) · coverage 99% branch · all 7 routed survivors now killed; remaining survivors are the 4 dead `get_by_workspace` mutants → score 100% (158 / 158 after excluding 4 dead). See "Round 2" at the end.
>
> **Verdict (Round 1, cases Revision 2):** NEEDS WORK
> Tests: 196 passed · 55 xfailed (reproduced ✅; all 55 fail on their card's line under `--runxfail`) · coverage 99% branch (115 statements, 20 branches; missed 197–202 = dead `get_by_workspace`)
> Mutation: 162 mutants · 151 killed · 11 survived → score 96% (151 / 158, after excluding 0 equivalent, 4 dead, 0 bug-path)
> Source commit: e48a092 (file unchanged in the working tree) · Cases revision: 2

## Summary
The tests are faithful to the cards. Every one of the 251 cases has exactly one test, every marker matches its card, and every xfail fails on the Then line its card names. Three runs gave the same result, and the runs match the notes. Nothing is mocked except the convention clocks. The only weakness is in the hub search (`_apply_transfer_order_hub_filters` R8/R9). Each name kind is searched by one position only: factory names by a prefix, machine and component names by a suffix. Three location ends are never searched by name at all: a damaged source, a storage destination on its own, and a project source. Seven search mutants survive because of this. They go to the case designer. No new code bug was found. The numbering, the stage rule / tick filter, the factory filter, tie-break, workspace and no-lock variants are all covered, or tagged with their BUG IDs.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `_apply_transfer_order_hub_filters` R8/R9, L131 | No card finds an order by an inner or trailing part of a **factory** name. Every factory search is a prefix (`bravo`, `alpha`, `yankee`, `beta_`), so a prefix-only match passes. | mutant #23 L131 `'%' -> ''` (leading) survived | case designer |
| 2 | case-missing | R8/R9, L135 | No card finds an order by a leading or inner part of a **machine** name. Every machine search is a suffix (`kilo`, `lima`, `oscar`). | mutant #26 L135 `'%' -> ''` (trailing) survived | case designer |
| 3 | case-missing | R8/R9, L139 | No card finds an order by a leading or inner part of a **component** name (`echo`, `sierra` are suffixes). | mutant #28 L139 `'%' -> ''` (trailing) survived | case designer |
| 4 | case-missing | R9, L163–166 | No card searches the component name at a **project source**. HF-36 and HF-40 only use project destinations. | mutants #31 L164 `Eq -> NotEq`, #41 L164 `'project' -> ''` survived | case designer |
| 5 | case-missing | R9, L147–150 | No card searches the factory name at a **damaged source**. HF-31 uses a storage source and HF-32 a damaged destination. | mutant #44 L148 `'damaged' -> ''` survived | case designer |
| 6 | case-missing | R9, L151–154 | No card searches the factory name at a **storage destination** on its own. HF-44 has F1 at both ends, so the source clause alone keeps it. | mutant #45 L152 `'storage' -> ''` survived | case designer |
| 7 | case-missing (advisory, bug-path) | `get_pending_highlights_for_hub` R2a, `_apply_transfer_order_hub_filters` R4 [BUG-2659/2660] | "Planned" needs a line **of `workspace_id`**. No card has a defined route whose only line belongs to another workspace (invalid data under HR-16, as in HF-38…40). That order must be Draft, both in the highlights and for the Draft / Planned ticks. Mutation cannot see this, because today the line is not read at all. | hand variant "Planned and stage filter": spec R2a / R4 wording vs. OQ39 / OQ40 cards | case designer (strict xfail BUG-2659 / BUG-2660) |
| 8 | case-missing (advisory) | HR-10 no-lock lines | `"FOR UPDATE" not in sql` is checked for `list_for_hub`, the touching / inbound lists, `get_by_id_and_workspace`, `get_next_number` and both item lists. It is not checked for `count_for_hub`, `list_recent_for_hub`, `count_machine_involved_for_hub`, `get_pending_highlights_for_hub` or `aggregate_hub_stats`. These are low risk, because the code has no lock to mutate. | hand variant "locks" | case designer |

Fidelity read of all 251 cards against their tests found nothing: no missing or weakened assertion, no changed value, no wrong Given, no swallowed failure, no extra mock and no dishonest xfail. `pytest.raises` names `TypeError` / `IntegrityError`, as the cards say. The only patches are clock(L, U) and utconly(U). HF-47 and HF-50 use `in idset(result)`, exactly as their cards say; the strict counterparts are HF-46 and HF-49.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 3 | L202 | `return …` → `return None` | dead | `get_by_workspace`, spec Not specified (Q3); no caller (confirmed: only `TransferOrderManager.list_transfer_orders`, and nothing calls that; `TransferOrderService.list_transfer_orders` goes to `list_transfer_orders_page`) | — |
| 14 | L195 | `skip=0` → `1` | dead | same method | — |
| 15 | L195 | `limit=100` → `101` | dead | same method | — |
| 22 | L200 | `Eq -> NotEq` | dead | same method | — |
| 23 | L131 | leading `'%'` → `''` (factory name) | case-missing | Finding 1 | case designer |
| 26 | L135 | trailing `'%'` → `''` (machine name) | case-missing | Finding 2 | case designer |
| 28 | L139 | trailing `'%'` → `''` (component name) | case-missing | Finding 3 | case designer |
| 31 | L164 | `source_location_type == "project"` → `!=` | case-missing | Finding 4 | case designer |
| 41 | L164 | `'project'` → `''` | case-missing | Finding 4 | case designer |
| 44 | L148 | source `'damaged'` → `''` | case-missing | Finding 5 | case designer |
| 45 | L152 | destination `'storage'` → `''` | case-missing | Finding 6 | case designer |

Per range: L1–85 20/20 killed · L86–176 39/46 · L177–333 54/58 (4 dead) · L334–463 38/38.

## Traceability
Cases 251 · test functions 229 (33 `pytest.param` ids) · every case ID is under exactly one `# [claude]` header or param id · no test without a case ID · unmatched: none. Markers: 47 strict xfail (`X2650`, `X2651`, `X2653`, `X2654`, `X2655`, `X2656`, `X2657`, `X2658`, `X2659`, `X2660`) and 8 non-strict (`X2656N`, `X2657N`). Each matches its card's Expect line, and its reason names the card's BUG ID. Pass cards carry no marker. Every BUG ID used (2650, 2651, 2653…2660) is in `docs/testing/bugs.md`. Mismatches: none.

## Hand variants
| Variant | Covered by | Result |
|---|---|---|
| "Planned" and the stage filter | OQ39-01…13, OQ40-01…19 | covered; the foreign-workspace line is missing (Finding 7) |
| open scope (`exclude_complete`) | HF-21/22/53/54, CH-04, MI-05, PH-02, AS-01…04, OQ40-14 | covered |
| numbering per workspace / past 999 / local-clock year / prefix case / text vs numeric | NN-12…15, 27, 28 · NN-07…09 · NN-23…26 · NN-30, 31 · NN-08…10, 32, 33 | covered (bug cards strict) |
| `%` / `_` / `\` and search on deleted parties | HF-46…51 · HF-41…43 | covered; name position gaps (Findings 1–6) |
| tie-breaks | LH-02, RC-07/08, PH-10/11, TL-08, IB-10, IO-08, IT-08 plus statement alarms | covered |
| locks `"FOR UPDATE" not in sql` | LH-11, TL-10, IB-12, GI-07, NN-22, IO-11, IT-10 | partly (Finding 8) |
| W0 / W2 scoping | HF-01…03, 38…40, FF-12/13, AS-05, TL-03, IB-06, GI-02…04, NN-12…14, IO-03/04, IT-04…06, II-02/03, OQ40-04/17/19 | covered |
| money (voided rows, received vs refunded, payable + receivable, expense pipeline) | — | not applicable: no money in this DAO |

## Commands run
```
COVERAGE_FILE=C:/Users/User/AppData/Local/Temp/makorsh-pipeline/bigdaov/to/.coverage
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.transfer_order --cov-branch --cov-report=term-missing
  app\dao\transfer_order.py  115  2  20  0  99%  197-202
  196 passed, 55 xfailed, 15 warnings in 29.80s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts="" --runxfail -rf
  55 failed, 196 passed, 15 warnings in 14.39s
PYTHONPATH=<scratch> … --runxfail -p vfails_to   (own plugin + checker: every one of the 55 fails at the card's "Fails today on" Then line; NN-27/28 raise IntegrityError 23505 in the When, as their cards say)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts=""   (×2)
  196 passed, 55 xfailed, 15 warnings in 14.34s
  196 passed, 55 xfailed, 15 warnings in 14.20s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/transfer_order.py tests/unit/dao/test_transfer_order.py --lines <1-85 | 86-176 | 177-333 | 334-463> --json <scratch>/mut_<range>.json   (4 parallel runs)
  20 · 20 killed  |  46 · 39 killed  |  58 · 54 killed  |  38 · 38 killed
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\to\` (`trace2.py`, `vfails_to.py`, `vfails.json`, `mut_*.json/log`).

## Round 2 — 2026-11-14
Narrow re-check after cases **Revision 3** (verify findings 1–8, all `case-missing`) and the executor's patch (test file 18:28:34, notes 18:29:01). `app/dao/transfer_order.py` unchanged (`git diff` empty; source commit e48a092).

**Current verdict: PASS.** Every routed survivor is killed by its new card, the 16 new tests are faithful to their cards, the runs reproduce the notes, and the only survivors left are the 4 dead `get_by_workspace` mutants.

### What was checked
- **Traceability (whole file):** 267 cards · 242 `# [claude]` blocks · every card under exactly one block or `pytest.param` id · no duplicates, no test without a card. Markers: every pass card unmarked; new OQ39-14 `@X2659`, OQ40-20 `@X2660` (both strict, reason names the BUG ID). Non-strict `X2656N` / `X2657N` unchanged and as carded (my script's "strictness" lines for RC-07…IT-09 are a regex artefact of the multi-line `_x(...)` definitions; read by hand: correct).
- **Fidelity of the new / changed tests** (read against each card): HF-55 … HF-63 (Givens: FB "Bravo Yard", MB "Lathe Lima", CB "Beam Echo" at the carded ends and types; B as carded; terms `avo ya`, `yard`, `lathe`, `the li`, `beam`, `am ec`, `echo`, `bravo`; Then `ids(result) == [A.id]` exact). CH-06, RC-11, MI-08, AS-09 (Then 1 exact result, Then 2 `rec.written == []`, Then 3 `all("FOR UPDATE" not in st for st in rec.selects)`), PH-14 (4 Then lines incl. `len(selects) >= 1`, as carded). OQ39-14 (5 Then lines, `_foreign_line` = `TransferOrderItem(W2, A, line 1, I2, 2.00)` as carded), OQ40-20 (A at `SP` + foreign line, B planned stored S1, tick `[S1.id]`, Then `ids == [A.id]`). No missing / weakened assertion, no extra mock, no swallowed failure. No existing card changed.
- **xfail honesty** (`--runxfail`, own plugin `vfails_to`): 57 failed, 210 passed. OQ39-14 fails at **Then 2** `assert 0 == 1` (card: Then 2, `awaiting_setup_count == 0`); OQ40-20 fails at **Then 1** (today B is returned instead of A; card: Then 1, only B kept). ✅

### Routed survivors (round 1) — now
| # | Line | Mutation | Round 2 | Killed by (in-process re-check, own plugin `mutone`, all pass tests) |
|---|---|---|---|---|
| 23 | L131 | factory name leading `'%'` → `''` | KILLED | HF-55, HF-56 |
| 26 | L135 | machine name trailing `'%'` → `''` | KILLED | HF-57, HF-58 |
| 28 | L139 | component name trailing `'%'` → `''` | KILLED | HF-59, HF-60 |
| 31 | L164 | `source_location_type == "project"` → `!=` | KILLED | HF-61 |
| 41 | L164 | `'project'` → `''` | KILLED | HF-61 |
| 44 | L148 | source `'damaged'` → `''` | KILLED | HF-62 |
| 45 | L152 | destination `'storage'` → `''` | KILLED | HF-63 |

Each mutant was killed by exactly the card(s) listed and by no other test, so each new card does the job it was added for. Findings 7 (foreign-workspace line → Draft) and 8 (no-lock on the five hub reads) are closed by OQ39-14 / OQ40-20 and CH-06 / RC-11 / MI-08 / PH-14 / AS-09; neither has a mutant to kill (bug-path / no lock in the code).

Mutation over the hub-search block, L128–166: **25 mutants · 25 killed · 0 survived (100%)**. With round 1's other ranges unchanged (only tests were added), the module stands at 162 mutants · 158 killed · 4 survived (all dead, L195–202) → **100%** (158 / 158).

### New findings
None. Nothing routed.

### Commands run (round 2)
```
COVERAGE_FILE=C:/Users/User/AppData/Local/Temp/makorsh-pipeline/bigdaov/to/r2/.coverage
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.transfer_order --cov-branch --cov-report=term-missing
  app\dao\transfer_order.py  115  2  20  0  99%  197-202
  210 passed, 57 xfailed, 17 warnings in 31.23s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts=""   (×2)
  210 passed, 57 xfailed, 17 warnings in 14.26s
  210 passed, 57 xfailed, 17 warnings in 12.91s
PYTHONPATH=<scratch> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts="" --runxfail -p vfails_to
  57 failed, 210 passed, 17 warnings in 13.19s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/transfer_order.py tests/unit/dao/test_transfer_order.py --lines 128-166 --json <scratch>/r2/mut_128-166.json
  Mutants: 25 · killed 25 · timeout 0 · survived 0 · score 100%
MUT='<line>:0:<old>:<new>' PYTHONPATH=<scratch>/r2 .venv/Scripts/python.exe -m pytest tests/unit/dao/test_transfer_order.py -q -p no:cacheprovider -o addopts="" -m "not xfail" -p mutone -rf   (×7, one per routed survivor; failing tests listed above)
```
Scratch: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\bigdaov\to\r2\` (`mut_128-166.json/log`, `mutone.py`, `.coverage`).
