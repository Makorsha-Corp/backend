# Verification — `app/managers/machine_section_assignment_manager.py`

> **Verdict:** PASS
> Tests: 47 passed · 4 xfail-marked (3 strict, 1 non-strict; printed as `3 xfailed, 1 xpassed`) (reproduced ✅) · coverage 98% branch (28 statements, 0 missed; 12 branches, 1 partial `62->60`, unreachable)
> Mutation: 19 mutants · 19 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: none stated (READY, 51 cases; spec APPROVED 2026-10-16)

## Summary
These tests can be trusted. I read all 51 tests against their cards line by line, with no sampling: every Given row and its keywords, the When call and each argument, and every numbered Then line with each check it lists. As a second, independent check, a script rebuilt the expected body of each of the 46 vocabulary cards from the card text and the helper sheet. Those are the 38 local tests, the 6 exemplars and the 2 handed back (SET-26, CLR-02). It compared each body statement by statement, including the `# Then N` comments and the argument set, and found **0 differences**. The same script reported **40 of 40** planted mistakes. Among them were the refused `unchanged(AD)`-for-`unchanged(MD)` swap in CLR-02, SF/SG, F1/FD, S1/S2 and M2/M3 swaps, a dropped `loaded = …` line, a dropped `sorted()`, and a snapshot taken after the call.

- **Local-model tests (38 delivered): functional findings in 0 / 38, so 38 of 38 (100%) are right as delivered.** Cosmetic findings in 19 / 38: the tool cut their names at 70 characters.
- **Handed back (2, not counted in the 38):** MSM-SET-26 (3 × an extra fourth Then line, "nothing written") and MSM-CLR-02 (wrote `unchanged(AD)` for the card's `unchanged(MD)`, then failed). Claude wrote both; they match their cards (0 findings).
- **Claude-written tests (13 = 6 exemplars + 7 `# [claude]`): functional findings in 0 / 13.** Cosmetic findings in 5 / 13: names cut at 70 characters (exemplars SET-08, SET-15, SET-29, CLR-01; and SET-26).
- **Edits after delivery confirmed.** Against `test_msm.asdelivered.py`, all 44 delivered tests (38 local + 6 exemplars) are identical line for line, in unchanged order. The 7 tests missing from the copy are exactly the 7 `# [claude]` ones. The scaffold differs by the import block (`patch`, `insert`, a dropped `# noqa: F401`, the wrapped manager import), the module docstring sentence about handed-back cards, and one addition: the `bulk_assigned_machines` helper used only by CLR-09, which the notes document.
- **Stability:** 9 whole-file runs with today's code were green: 6 plain, 1 with coverage, and 2 under a forced bitmap / index plan. With the planner forced to a sequential scan the run was also green, `47 passed, 4 xfailed`. No strict xfail and no pass card rests on row order.
- **Mutation:** the tool killed 19 of 19 mutants. I also ran 25 hand variants: 22 turn the normal run red (19 through a pass card, 3 only through a strict xfail flipping to XPASS). The 3 that do not are 2 equivalent and 1 bug-path. Each of the section checks, the expire in `clear_for_section`, a `commit()` in either method, and every machine check (Q1) is noticed.

## Findings
None functional. Cosmetic only (none blocks PASS, all optional):

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Naming (local) — COSMETIC | MSM-SET-02, 04, 07, 09, 10, 16, 17, 19, 20, 22, 28, 31, 32, 33, CLR-03, 04, 08, 10, 12 (19 tests) | The name is the title slug cut at 70 characters. The docstring carries the full ID, title and rules in all 51 tests. The tool made the cut, not the model. | `test_msm_set_19__a_live_section_of_a_soft_deleted_factory_is_refused_like_a_deleted` | optional — tool (`tests/unit/_tools/local_coder.py`) |
| 2 | Naming (exemplar / claude) — COSMETIC | MSM-SET-08, SET-15, SET-29, CLR-01 (exemplars), SET-26 (claude) | The same 70-character cut on hand-written names. SET-34, SET-35, CLR-02, CLR-09, CLR-13 and CLR-14 are complete. | `test_msm_set_26__a_machine_of_another_workspace_is_not_refused_and_the_link_is_stored` | optional — executor |
| 3 | Documentation — COSMETIC | `machine_section_assignment_manager.cases.md`, MSM-CLR-13 "Fails today on" | The card says the updated link A1 "usually comes back last". It does so only under a sequential scan, where `--runxfail` fails on Then 2 (line 1370, `[M1, M2, M3] == [M3, M1, M2]`). Under the default plan (and forced bitmap / index plans) CLR-13 xpassed in every run here (9) and in the notes (10). Same situation as finding 5 of the DAO verify. | section "xfail tests" | optional — case designer |

The `# [local-coder]` / `# [claude]` tags, docstrings, markers and `# Then N` comments are all as required (see Traceability).

### What was checked in the 38 local tests (by reading and by the rebuild script)
- **Given rows: no missing, extra or swapped row; no wrong `of=` / `to=`; no keyword the card does not list.** In particular:
  - SET-19: SG = section of **FD** "Dry Store", AF = **MF**→**SG**, and the When uses **SF**. Neither SF nor SG is used in the other's place.
  - SET-22: AF = MF→**SF**; unchanged(SF) and unchanged(FD).
  - SET-05 and SET-27: A2 = **M2**→S1 (M1 has no link), with unchanged(A2).
  - SET-36: A1 M1→S1, A2 **M2**→S1, A3 **M3**→**S2**.
  - CLR-04, CLR-05: A9 = **M9**→S1. CLR-08: A9 only. CLR-03: M1→**SX**.
  - SET-21: FQ has `is_active=False` and the right name / abbreviation; SQ and MQ are of FQ. SET-23: SI is `is_active=False`.
  - CLR-11: MN "Belt Sander", AN, then `loaded`, then the rename.
- **No snapshot of the wrong row.** The CLR-02 refusal (`unchanged(AD)` for `unchanged(MD)`) has no counterpart in any delivered test. Every `before_x = snap(db, x)` names the row of its Then line: A1, A2, A3, A9, AF, S1, S2, SX, S9, SF, SI, FD, F1, M1, MD. Every snapshot sits after the last Given line and before the call.
- **Given code lines kept verbatim and in place:**
  - `a1_id = a1.id` (SET-02);
  - `loaded = m1.factory_section_id` (SET-31, 32, 33), `loaded1/2/3` (CLR-10), `loaded = mn.factory_section_id` + `mn.name = "Edge Trimmer"` (CLR-11);
  - the tuple line and `db.expunge_all()` of CLR-12, whose When uses `s1_id` / `w1_id` as the card says.
- **When:** no argument changed, dropped or added. This covers:
  - `factory_id=MISSING` (SET-04, 18), `user_id=MISSING` (SET-04, 28), `workspace_id=MISSING` (SET-07), `machine_id=MISSING` (SET-06, 27);
  - `factory_section_id=0` / `-1` / `MISSING` / `None`, `user_id=None` (SET-30);
  - `factory_id=f2.id` with `sx` (SET-16) and with `s3` (SET-25), `f1` with `sf` (SET-20), `fd` with `sf` (SET-19, 22);
  - `workspace_id=w2.id` (SET-14, CLR-05).
- **Then lines:**
  - None is skipped, none is extra, and none sits under the wrong `# Then N`.
  - Every two-value line has two asserts: SET-02 Then 4, SET-09 Then 4, SET-14 Then 2 (three), SET-21 / 24 / 25 Then 2, SET-28 Then 5.
  - No check is weakened. Exact `==` on `[m1.id]`, `[m9.id]`, `[mn.id]` and `[]`; `sorted()` only where the card writes it; detail texts in full; `status_code` exact.
  - The in-memory checks (SET-31 to 33, CLR-10, CLR-11) read the same object before any re-read.
  - `raises:` lines: HTTPException cards use a plain `pytest.raises` (no savepoint). IntegrityError cards (SET-27, 28) have `begin_nested`. The `.orig` type and the constraint name follow on their own Then lines.
- **Swallowed failures, extra mocks:** none. No local test has a `try` or patches anything. `patch` appears only in SET-35 and CLR-14 (the commit spy, `wraps=`).

### The 13 Claude-written tests (read the same way, no functional finding)
- **Exemplars.** SET-01, 08, 13, 15, 29 and CLR-01 equal their cards. The rebuild agrees.
- **SET-26 and CLR-02 (handed back).**
  - SET-26 has exactly 3 Then lines (no "nothing written") and `workspace_id == W1.id` on Then 3.
  - CLR-02 builds AD with no variable, snapshots **MD**, and asserts `sorted(result) == [m1.id, md.id]` and a table count of 0.
- **SET-34.** `db.expire(m1)` sits under Then 2, before its assert.
- **SET-35 and CLR-14.** `sp = db.begin_nested()` directly before the call, inside the `patch.object(db, "commit", wraps=db.commit)` block. The inside-savepoint checks come before `sp.rollback()`, the rest after. `call_count == 0`.
- **CLR-09.** 10 001 machines "Bulk 00001" … "Bulk 10001" (F1, W1, active, not deleted, not running) and their S1 links (`created_by U1`), each set in one insert. The four Then lines are exact (`len(set) == len`, subset of the inserted ids, `== 10001`, 0 left).
- **CLR-13.** A1 = **M3**→S1, A2 = M1→S1, A3 = M2→S1. Then `a1.created_by = u2.id; db.flush()`, `sorted` on Then 1, and the exact order on Then 2.

## xfail tests
| Card | Author | Marker | Fails on (`--runxfail`) | Then lines never executed today | Verdict |
|---|---|---|---|---|---|
| MSM-SET-08 | exemplar | strict BUG-909 | Then 3, line 358: `assert result.id == a1_id` (new id = old + 1) | Then 4 – 5 (lines 360 – 363) | right line, right reason |
| MSM-SET-19 | **local** | strict BUG-910 | Then 1, line 593: `DID NOT RAISE HTTPException` | Then 2 – 6 (lines 597 – 605) | right line, right reason |
| MSM-CLR-09 | claude | strict BUG-907 | Then 3, line 1345: `assert 10000 == 10001` | Then 4 (line 1347) | right line, right reason |
| MSM-CLR-13 | claude | non-strict BUG-906 | default plan: passes (xpass). Forced sequential scan: Then 2, line 1370, `[M1, M2, M3] == [M3, M1, M2]` | — | as the card predicts, only under a seq scan (finding 3) |

**The never-executed lines, checked.**
- **By reading.** SET-19 Then 2 – 6 are 400, the "deleted factory section" text, `written == before`, `snap(af) == before_af` and `len(rows_of(mf)) == 1`, as on the card. SET-08 Then 4 – 5 and CLR-09 Then 4 also match their cards.
- **Against scratch references.** The references are `msmv/plug/ref_msm.py`, which patches the manager and DAO classes in the test process only; `app/` was untouched. Against them, every xfail test passes in full, so every line after its failing line runs and holds:

| Reference (`--runxfail`) | SET-08 | SET-19 | CLR-09 | the 48 others |
|---|---|---|---|---|
| `same` (today re-implemented, control) | fails l. 358 | fails l. 593 | fails l. 1345 | pass (also plain: `47 passed, 3 xfailed, 1 xpassed`) |
| BUG-909 fix (same section → existing link returned) | **passes** | fails | fails | pass |
| BUG-910 fix (section's factory deleted → 400, after the factory check) | fails | **passes** | fails | pass |
| BUG-907 fix (no cap) | fails | fails | **passes** | pass |
| BUG-906 fix (`ORDER BY id`) | fails | fails | fails | pass |
| all four | pass | pass | pass | **51 passed** |
| one fix, markers on | BUG-909 / 910 / 907: `1 failed (XPASS strict), 47 passed, 2 xfailed, 1 xpassed` through exactly that bug's test | | | |

## Stability
| Run | Outcome |
|---|---|
| plain × 6 in a row | `47 passed, 3 xfailed, 1 xpassed` (xpass: CLR-13) |
| with coverage | the same |
| planner forced to bitmap scan / index scan | the same |
| planner forced to sequential scan | `47 passed, 4 xfailed` |
| `--runxfail` (default plan) | `3 failed, 48 passed` (SET-08, SET-19, CLR-09) |
| `--runxfail` (sequential scan) | `4 failed, 47 passed` (+ CLR-13 on Then 2) |

Never red. Does anything that can turn the run red rest on row order?
- **Strict xfails:** none. SET-08 compares one id, SET-19 waits for an exception, and CLR-09 counts and compares sets. All three failed under every plan.
- **Pass cards:**
  - Every exact list compare has at most one element: CLR-03 `[m1.id]`, CLR-04 `[m1.id]`, CLR-05 `[m9.id]`, CLR-11 `[mn.id]`, CLR-06 / 07 / 08 `[]`.
  - Every multi-id compare uses `sorted` (CLR-01, 02, 10, 12, 14).
  - `rows_of(…)[0]` is only used where the machine has exactly one row.
- **CLR-09** depends only on no other S1 / W1 link existing, which holds because the standing rows are per test.
- **CLR-13** is the only order card and is non-strict. Keep it so: no Given fails under every plan. As in the DAO, it is the card that tells "link-id order" from "machine-id order" (see `clr_sorted` below).

## Surviving mutants
None from the tool (19 / 19 killed).
- **What was killed:** negated `if` on lines 26, 30, 35, 40 and 62; `not` dropped (30); `is not` → `is` (26, 62); `!=` → `==` (40); `raise` → `pass` (31, 36, 41); `return None` (46, 64); the detail strings (33 × 2, 38, 43); and `'section_assignment'` → `''` (63).
- **How it was run:** alone, with no pytest beside it.

**Hand variants** (scratch plugin, `-m "not xfail"` as `mutate.py` does; markers on as well where it matters):

| Variant | Rule | Failed by |
|---|---|---|
| 404 check removed (`not section` → falls through to `None.is_deleted`) | R5, R6 | SET-10, 11, 12, 13 |
| 400 "deleted" check removed | R7 | SET-15, SET-16 |
| 400 "other factory" check removed | R8 | SET-17, 18, 20 |
| "other factory" check before "deleted" check | R7 order | SET-16 |
| section looked up by id only (no workspace) | R6 | SET-13 |
| **BUG-910 check deleted** (= today's code) | R9 | strict SET-19 stays xfail. With the fix present, SET-19 XPASS(strict) turns the run red |
| BUG-910 check before the 404 / deleted / factory order (first after 404) | R9 order | SET-20 |
| BUG-910 check between "deleted" and "other factory" | R9 order | SET-20 |
| **expire of loaded machines dropped from `clear_for_section`** | clear R5 | CLR-10, CLR-11 |
| `clear_for_section` expires the whole machine, not only `section_assignment` | clear R5 | **none** (H1, equivalent) |
| **`commit()` added to `set_assignment`** | R13 | SET-31, 32, 33 (the commit expires M1), SET-35 (commit spy) |
| **`commit()` added to `clear_for_section`** | clear R8 | CLR-14 (commit spy) — the only one |
| `set_assignment` expires the machine (refreshes it) | R12 (P2) | SET-31, 32, 33 |
| **machine check: must exist** | R11 (Q1) | SET-27 |
| **machine check: not deleted** | R10 (Q1) | SET-24 |
| **machine check: same workspace** | R10 (Q1) | SET-26 |
| **machine check: own factory == `factory_id`** | R10 (Q1) | SET-25, SET-26 |
| all four machine checks | R10, R11 | SET-24, 25, 26, 27 |
| … also when clearing | R3 | + SET-04, SET-06, SET-07 |
| `factory_id` validated to exist (also when clearing) | R3, R8 | SET-04, SET-18 |
| BUG-909 fix | R4 | strict SET-08 XPASS → red |
| BUG-907 fix | clear R3 | strict CLR-09 XPASS → red |
| BUG-906 fix (DAO `ORDER BY id`) | clear R7 | none here. CLR-13 xpasses as it does today; the strict alarm is the DAO's MSA-GS-22 (Deferred table) |
| `clear_for_section` returns the ids sorted (machine-id order) | clear R7 | none of the pass cards. CLR-13 fails, but it is non-strict, so the run stays green (H2) |
| `clear_for_section` de-duplicates the ids | Returns | none (H3, equivalent) |

**Q1 answer.** Yes: every machine check the manager must *not* make is noticed, each by at least one pass card (SET-24 to SET-27). A check also applied when clearing is noticed by SET-04, 06 and 07.

**Count.** 22 of 25 variants turn the normal run red: 19 through a pass card, and 3 only through a strict xfail flipping to XPASS (the BUG-909, 910 and 907 fixes). The three that do not:

| # | Variant | Class | Why |
|---|---|---|---|
| H1 | full `session.expire(machine)` in `clear_for_section` | equivalent | The DAO's `clear_for_section` calls `db.flush()` before the manager expires anything. A name changed in memory (CLR-11) is therefore already written and reloads as "Edge Trimmer". No pending in-memory value can survive to be discarded, so expiring all attributes or only `section_assignment` reads the same. (Spec gap 3 of the cases file has a similar limit for R6.) |
| H2 | ids returned sorted | bug-path | Order is BUG-906 (R7). Only the non-strict CLR-13 sees it, and its marker goes with the fix. |
| H3 | ids de-duplicated | equivalent | `uq_machine_section_assignment_machine` allows one link per machine, so the ids are already unique. |

A single point worth knowing when a card is edited: CLR-14 is the only test that notices a commit in `clear_for_section`. SET-16 alone notices the deleted / factory order. SET-20 alone pins where the future BUG-910 check must sit.

## Spec coverage
Every rule and error row has at least one card and one test. I checked this against the spec itself, not only against the matrix:
- **`set_assignment`:** R1 – R13 and R9a, Errors rows 1 – 7, Returns, Side effects, and the Inputs lines "`factory_id` ignored / `user_id` unused when clearing" (SET-04) and "`None` stored as `NULL`" (SET-30).
- **`clear_for_section`:** R1 – R8, Returns, Side effects.

**No rule is without a card.** Parts without a card, all declared by the designer, none blocking:
- the unreachable `machine is None` branch (R6; coverage gap `62->60`);
- the "keyword-only parameters" fact (Spec gap 2);
- R6 "loaded and refreshed by the manager", which is not observable as such (Spec gap 3).

## Traceability
cases 51 · tests 51 · unmatched: none. Each case ID is in exactly one test name. All 51 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`". Marker mismatches: none.
- **Markers.** The 47 `Expect: pass` cards have no marker. SET-08 has `xfail(strict=True)` BUG-909, SET-19 strict BUG-910, CLR-09 strict BUG-907, and CLR-13 `strict=False` BUG-906. Each reason names exactly the card's bug.
- **BUG ids used:** BUG-906, 907, 909, 910, all in `docs/testing/bugs.md`.
- **Authorship**, from the file and `local-run.json` (40 sent: 34 accepted first try, 4 after one retry, 2 escalated after 3 attempts):
  - 38 tests under `# [local-coder] <ID>`;
  - 7 under `# [claude] <ID>`: the 5 `Author: claude` cards (SET-34, SET-35, CLR-09, CLR-13, CLR-14) plus SET-26 and CLR-02, each tagged "(handed back by the local model)";
  - 6 exemplars without a comment.
- **`# Then N` comments** are present, in order and equal in number to the card's Then lines in all 51 tests.
- **Arguments.** No unused argument. In all 46 rebuilt tests the argument set equals the fixtures the body uses.
- **`try` / `patch`:** no `try` anywhere; `patch` only in SET-35 and CLR-14.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_section_assignment_manager.py -q -p no:cacheprovider --cov=app.managers.machine_section_assignment_manager --cov-branch --cov-report=term-missing -rxX
  app\managers\machine_section_assignment_manager.py   28   0   12   1   98%   62->60
  47 passed, 3 xfailed, 1 xpassed, 15 warnings in 16.89s          (xpass: CLR-13)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_section_assignment_manager.py -q -p no:cacheprovider --runxfail -rf --tb=short
  3 failed, 48 passed in 7.68s     (SET-08 l. 358, SET-19 l. 593, CLR-09 l. 1345)

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_machine_section_assignment_manager.py -q -p no:cacheprovider -rxX     (six times in a row)
  47 passed, 3 xfailed, 1 xpassed   (each time; xpass CLR-13)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/machine_section_assignment_manager.py tests/unit/managers/test_machine_section_assignment_manager.py --json <scratchpad>/msmv/mut.json
  Mutants: 19 · killed 19 · timeout 0 · survived 0 · score 100%     (run alone)
```
These match the notes' Result line: 51 tests, 47 passed, 4 xfail-marked, printed as `47 passed, 3 xfailed, 1 xpassed`; coverage 98% with `62->60` missed.

Extra checks, all in the scratchpad (`<scratchpad>/msmv/`). Nothing in the repo was written except this report, and `app/` was not touched:
```
audit.py      cards ↔ tests ↔ markers ↔ docstrings ↔ `# Then N` ↔ arguments; expected body rebuilt from the 46
              vocabulary cards (Given rows of all four builders with "but" keywords, code lines, snapshots and
              their place, When call, every check of every Then line, raises shape) → 0 problems
selftest.py   40 planted mistakes in a copy of the test file → audit.py reports 40 of 40
delivered.py  every test against test_msm.asdelivered.py → 44 identical, 7 [claude] added, order kept, scaffold diff
drive.py + plug/ref_msm.py   (PYTHONPATH=plug MSMREF=<variant> … -p ref_msm)
  control `same`, fixes 909 / 910 / 907 / 906 and all four (--runxfail, markers on)  → "xfail tests"
  force_seq / force_bitmap / force_index                                               → "Stability"
  25 hand variants, -m "not xfail" (and markers on where it matters)                   → "Surviving mutants"
```

## Local-coder patterns
There is no functional mistake in the 38 delivered tests. All 38 are what their cards say.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| Snapshot of a row of the same kind as the card's (`unchanged(AD)` for `unchanged(MD)`) | 0 delivered; 1 refused (CLR-02, handed back) | CLR-02 | caught by the tool (failed run, then unused `before_ad`) | Card / sheet line: "`unchanged(X)` snapshots exactly X, even when another row of the Given is about X". The rebuild-and-compare (`msmv/audit.py`) catches it statically, before the test is run. |
| An extra "nothing written" check the card does not have | 0 delivered; 2 refused (SET-26 handed back after 3 tries; CLR-03 accepted on retry) | SET-26, CLR-03 | caught by the tool (Then-count / unused `before`) | Sheet: the existing rule "Only when the card has that Then line" works as a check but not as a prompt. Print it next to the `nothing written` example as "never add it on your own". |
| A builder fixture used but not in the argument list | 2 first attempts | SET-19, SET-23 (`mk_section`) | caught by the tool | Already fixed in the sheet during the run (the argument-list example now names `mk_section`). |
| A card row dropped from the asserts (`created_by == U1.id`) | 1 first attempt | SET-28 | caught by the tool ("card names U1") | The check works. Keep it. |
| A value or row swapped with another of the same kind (SF/SG, F1/FD/F2, S1/S2/S3/SX, M1/M2/M3/MD/M9/MF, W1/W2) | 0 in the 38 delivered | looked for in SET-16, 19, 20, 22, 25, 36, CLR-04, 05, 08 | — | Guarded only by the tool's "named row is used" check and by reading. The rebuild-and-compare found every planted swap (8 kinds) with no false alarm; it could become the runner's acceptance check. |
| Test name cut at 70 characters | 19 | SET-19, SET-28, CLR-12 | cosmetic — tool, not model | Tool: raise the limit or cut at the title's last full word (open since the factory module). |

Observations for `docs/testing/local-coder-improvements.md`:
- **First local xfail with Then lines after the failing line.** In SET-19, Then 2 – 6 never run today. They were confirmed by reading and by a BUG-910 reference fix, against which SET-19 passes in full.
- **The `loaded = …` exemption (runner fix P22) was exercised and works.** The sheet now keeps `loaded = m1.factory_section_id` verbatim. The local model wrote it in all six local tests that have such lines (SET-31, 32, 33, CLR-10 × 3, CLR-11), at the card's place.
- **What worked:**
  - all four builders with "but" keywords (`is_active=False` on FQ and SI);
  - the `raises:` shape for both HTTPException (8 local tests) and IntegrityError (2 local tests);
  - multi-value re-read lines;
  - code lines in the Given (CLR-11 rename, CLR-12 tuple and `expunge_all`).

**Still open (none blocks PASS) — numbered fix list:**
1. Optional, case designer: reword the "Fails today on" of MSM-CLR-13. It fails only when the planner uses a sequential scan; under the default plan the updated link keeps its place and the order equals the intended one. Keep the card non-strict and its body unchanged (finding 3).
2. Optional, tool (`tests/unit/_tools/local_coder.py`): remove the 70-character name cut (finding 1). Consider the rebuild-and-compare as the acceptance check. Add a sheet line saying `unchanged(X)` / `nothing written` are written only for the card's own X / line.
3. Optional, executor: complete the cut names of the exemplars SET-08, SET-15, SET-29, CLR-01 and of SET-26 (finding 2).
4. Not a test matter: when a bug is fixed, its strict test turns the run red, so remove its marker:
   - BUG-909 → SET-08;
   - BUG-910 → SET-19 (the check must come after the "other factory" check, or SET-20 fails);
   - BUG-907 → CLR-09;
   - BUG-906 → remove CLR-13's non-strict marker in the same change.

   After the BUG-908 fix, CLR-01 … CLR-14 go with the dead code.
