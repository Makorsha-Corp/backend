# Verification — `app/dao/machine.py`

> **Verdict:** PASS (round 3, cases revision 1 — see "Round 3 — revision 1" directly below; rounds 2 and 1 follow as history)
> Tests: 194 passed · 51 xfailed (reproduced ✅) · coverage 96% branch (67 statements, 2 missed: line 58 dead code, line 179 behind BUG-886; 22 branches, 2 partial: 35->37, 50->52 dead parameter)
> Mutation: 91 mutants · 67 killed · 24 survived → score 100% (after excluding 3 equivalent, 6 dead, 15 bug-path) — the three mutants of `restore` (lines 84, 85, 90) are now killed
> Source commit: e48a092 · Cases revision: 1 (READY, 245 cases; spec APPROVED, Q8 and Q9 provisional)

## Round 3 — revision 1
**Result: PASS.** 29 new tests (18 local-model, 11 Claude) were read line by line against their cards: no functional finding. The 216 older tests are unchanged apart from four docstring `Rules:` lines. `restore` is live code now and every mutant in it is killed.

### Summary
- All 29 new tests were read against their cards — every Given row and column, the When call, every numbered Then line. Nothing was sampled. Every one is faithful.
- **New local-model tests (18): functional findings in 0 / 18 tests · cosmetic findings in 12 / 18 tests** (MCH-GF-31, GS-31, RS-02, RS-03, RS-07, RS-09, RS-11, RS-14, RS-15, RS-17, RS-18, RS-22). Ten are names cut by the tool at 70 characters; counting only what the model itself wrote (argument order, variable names, one blank line): 6 / 18 (GS-31, RS-02, RS-03, RS-11, RS-14, RS-22).
- **New Claude-written tests (11): functional findings in 0 / 11 tests · cosmetic findings in 2 / 11 tests** (MCH-GS-30, RS-21: name does not carry the whole title).
- The points the executor flagged were each checked, and each holds:
  - **Swapped values where a card names two rows of a kind** (MCH-RS-02, RS-04, RS-13, RS-14, RS-15): none. RS-02 `factory_id=f2.id` / `created_at=T1` in the Given and `f2.id` / `w1.id` / `u1.id` / `T1` in Then 2, 4, 5; RS-04 `updated_by=u2.id` in the Given and in Then 2; RS-13 `w2.id` / `f9.id` in both; RS-14 `T0` / `u1.id` in Then 5; RS-15 `factory_id=f2.id` on M3 only.
  - **Then 4 of MCH-RS-17 and RS-18, never executed.** Both lines are the card's text exactly. They were executed once against a scratch reference fix of BUG-890 / BUG-891 (a pytest plugin in the scratchpad; nothing in the repo touched): both tests pass, and a fix that hides the machine only from the unfiltered search is failed by RS-17 on Then 4, a fix that leaves `get_by_section` unfixed by RS-18 on Then 4.
  - **A `restore` that writes when it should not.** Confirmed with hand-made variants of `restore` (the mutation tool has no such operator): an UPDATE issued although nothing changes is caught by MCH-RS-09 alone (Then 2); restoring every deleted machine of the factory by RS-14 alone (Then 3); touching the live machines of the factory by RS-15 and RS-22. These are single points, by card design, and all four tests are faithful.
- 51 xfail tests fail under `--runxfail`, each on the line its card names. Three normal runs gave the same outcome; no XPASS of the six non-strict BUG-343 tests.
- Limit of this verdict: Q8 (MCH-RS-04, RS-05, RS-06, Then 4 of RS-20) and Q9 (MCH-RS-22) are still provisional answers; if either changes, those cards change with it.

### Findings
None functional. Cosmetic only — none blocks PASS, all optional:

| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Style (local) — COSMETIC | MCH-RS-02, RS-03, RS-11 | Fixture arguments not in the order the other tests use (workspaces, users, factories, sections, builders). All listed fixtures are used; none is missing. | `(db, u1, f2, w1, mk_machine)`, `(db, u1, w1, f1, mk_machine)`, `(db, w1, s1, f1, mk_machine, mk_assignment)` | optional — executor (or let the tool sort the list) |
| 2 | Naming (local) — COSMETIC | MCH-RS-14 (`row_m1`, `row_m2`), MCH-RS-22 (`row2`) | Variable names other than the helper sheet's `row`. Each is assigned from the right `reread(db, …)` and used in the right assertions; the distinct names keep the two re-read rows apart. | `row_m2 = reread(db, m2)`, `row2 = reread(db, m2)` | optional — executor |
| 3 | Style (local) — COSMETIC | MCH-GS-31, line 4267 | A blank line between the last Given row and the `before_ad` snapshot, so the snapshot looks like part of the When block. It is taken at the right place (after the last Given row, before the call). | `ad = mk_assignment(of=md, to=s1)` / blank / `before_ad = snap(db, ad)` | optional — executor |
| 4 | Naming (local) — COSMETIC | MCH-GF-31, GS-31, RS-02, RS-07, RS-09, RS-11, RS-15, RS-17, RS-18, RS-22 (10 tests) | Test name cut at 70 characters (always at a word boundary; GF-31 and GS-31 end in `_s`, the "'s" of "factory's"). RS-17 and RS-18 have the same words after the ID. The docstring carries the full ID and title in all 245 tests. Made by the tool, not by the model. | `test_mch_rs_17__…_stays_hidden_from` / `test_mch_rs_18__…_stays_hidden_from` | optional — tool (`tests/unit/_tools/local_coder.py`) |
| 5 | Naming (claude) — COSMETIC | MCH-GS-30, RS-21 | The name stops before the end of the title ("… still assigned [to the same section]", "… is listed again [where it was]"), while the other nine hand-written names are complete. | `test_mch_gs_30__…_is_returned_again_still_assigned` | optional — executor |

Checked for and **not** found in the 29 new tests:
- a missing, extra or reordered Given row; a wrong or missing column (`factory_id`, `workspace_id`, `is_running`, `is_active`, `updated_by`, `created_at`, `model_number`, `manufacturer`, `note`, `deleted`); `deleted=True` missing where the card says "deleted" or present where it does not (MCH-RS-09, RS-10, RS-15 M4, RS-17 M1, RS-22 M2 are live as designed);
- a wrong `of=` / `to=` (MCH-GS-31: M1 → S2, MD → S1; RS-08: only M2 is assigned); a wrong event column (MCH-RS-06: `created_at=T0`, `metadata_json=None`, `event_type="deactivated"`);
- a changed When call (all 22 `restore` calls are `dao.restore(db, db_obj=<the card's machine>)`; MCH-RS-13 passes M9, RS-16 … RS-19 pass MD);
- a skipped Then line, an assertion under the wrong `# Then N`, or one weaker than the card: every "after the call" list line is the card's expression (`sorted(ids(...))` only where the card writes it; `ids(...) ==` in order for `search_advanced`); every `count:` line is the card's bare number; `updated_at` is asserted only as `is None` / `is not None`, on the side the card says;
- write cards: every re-read goes through `reread(db, …)` (expires first; the session has `autoflush=False`, so a missing flush shows — see the `rs_no_flush` variant below); every "unchanged" / "nothing written" snapshot is taken after the last Given row and before the call (GF-31, GS-31, RS-06, RS-07, RS-09, RS-14, RS-15, RS-22; hand-written: GF-30, GS-30, SA-128, SA-129 after the step "FD made live again", RS-16 after the stamp on FD, RS-19 AFTER between Then 2 and Then 3, RS-20 / RS-21 BEFORE ahead of `dao.soft_delete`);
- swallowed failures or extra mocks: no `try`, no `pytest.raises`, nothing patched in any of the 29; MCH-RS-12 wraps `db.commit` with the Conventions spy and nothing else. `fd_made_live_again` is the Conventions step word for word (`is_deleted False`, `deleted_at None`, `deleted_by None`, flush) and is used by hand-written tests only;
- MCH-SA-130 (handed back by the tool, written by hand): `search="\tbolt\n"` is the escaped literal (a real tab and newline), not a raw string; strict xfail BUG-892; fails on Then 1 with `[]`.

**The 216 older tests.** Compared function by function (decorators, signature, body, the comment lines above) with the round-2 state kept in the scratchpad (`tm_fixed.py`): exactly four differ, each by its docstring `Rules:` line only — MCH-GF-13 (`R3a` → `R3b`), GF-14 (`R3a, R1` → `R3b, R1`), GS-13 (→ `get_by_section` R3b), GS-14 (`R3a, R1` → `R3b, R1`) — and each now equals its card. Scaffold: one helper added (`fd_made_live_again`), the comment on the `patch` import extended; nothing else. Against `test_machine.rev1.asdelivered.py` (235 tests, taken right after the local run): 0 of its tests differ from the file, the 18 new local ones included; the ten tests only in the file are the hand-written GF-30, GS-30, RS-12, RS-16, RS-19, RS-20, RS-21, SA-128, SA-129, SA-130.

### Surviving mutants
The site list is the same 91 as in round 1 (same lines and columns). Three results changed, all in `restore`: line 84 `False` → `True`, line 85 `True` → `False`, line 90 `return db_obj` → `return None` — SURVIVED (class `dead`) in round 1, **KILLED** now. The 24 survivors:

| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 24, 25 | 55 | default `skip` `0` → `1`, `limit` `100` → `101` | dead | Signature of `get_active_by_workspace`; spec "Not specified": dead code, to be removed (Q4, reviewer-confirmed). | — |
| 5 | 58 | `return (…)` → `return None` | dead | Body of `get_active_by_workspace` (Q4). | — |
| 81, 82, 86 | 62, 63 | `==` → `!=` (twice), `False` → `True` | dead | Same method (Q4). | — |
| 30 | 104 | default `sort_by` `"name"` → `""` | equivalent | Line 188 is `sort_field_map.get(sort_by, Machine.name)`: `""` is not a key, so the column is still `Machine.name`. | — |
| 31 | 105 | default `sort_dir` `"asc"` → `""` | equivalent | Line 189 only tests `sort_dir == "desc"`; `""` and `"asc"` both sort ascending. | — |
| 52 | 185 | map key `"name"` → `""` | equivalent | `sort_by="name"` then misses the map and falls back to the `.get` default, the same column. | — |
| 87, 88, 79, 80, 83, 89, 91, 90, 84, 85, 75, 76, 78, 77, 67 | 149, 150, 153, 154, 154, 162, 163, 163, 168, 169, 173, 174, 174, 180, 181 | as in the round-1 table below | bug-path | Inside `if latest_event_type is not None:`; line 163 raises today (BUG-886), only the 22 xfail tests enter the block and they are excluded from the run. | — (resolves with BUG-886) |

Score: 67 killed / (91 − 3 equivalent − 6 dead − 15 bug-path) = 67 / 67 = 100%. No `test-weakness`, `case-missing` or `spec-gap` survivor. The `dead` class no longer contains anything of `restore`.

**`restore`, beyond the tool.** The tool has three mutants in lines 80–90 (it does not delete statements and does not mutate `None`), so lines 86–89 were checked with hand-made variants, loaded as a scratch pytest plugin and run against the 194 passing tests:

| Variant of `restore` | Rule | Failed by |
|---|---|---|
| `deleted_at` not cleared (line 86 removed) | R1 | MCH-RS-01, RS-13, RS-16, RS-20 |
| `deleted_by` not cleared (line 87 removed) | R1 | MCH-RS-01, RS-13, RS-16, RS-20 |
| no flush (line 89 removed) | R1, R5 | 19 of the 20 passing RS tests (all but RS-09, where nothing is to be flushed) |
| `db.add` removed (line 88) | — | none — **equivalent**: `db_obj` is already persistent in the session, `add` changes nothing |
| commits | R5 | MCH-RS-12 |
| an UPDATE even when nothing changes | R4 | MCH-RS-09 |
| stamps `updated_by` | R2a | MCH-RS-04, RS-05, RS-09 |
| clears `updated_by` | R2a | MCH-RS-04, RS-20 |
| sets `is_running = False` | R2 | MCH-RS-02, RS-20 |
| writes an activity event | R2a | MCH-RS-06 |
| restores every deleted machine of the factory | R6 | MCH-RS-14 |
| restores every deleted machine of the workspace | R6 | MCH-RS-14, RS-15 |
| issues an UPDATE on the live machines of the factory | R6 | MCH-RS-15, RS-22 |
| skips machines of another workspace | R6 | MCH-RS-13 |
| refuses a machine whose factory is soft-deleted | R7 | MCH-RS-16, RS-19 |
| makes the factory live too | R7 | MCH-RS-16 |
| deletes the section assignment | R3 | MCH-RS-07, RS-11, RS-19, RS-21 |
| refuses when a live machine has the name | R9 | MCH-RS-22 |
| does nothing unless `is_deleted` | R4 | MCH-RS-10 |
| returns another object | R5 | all 20 |

19 of 19 non-equivalent variants are caught. Every rule R1–R9 is pinned by at least one passing test; R7a by the two xfail tests (checked with the reference fix, above).

### Traceability
cases 245 · tests 245 · unmatched: none (each case ID is in exactly one test name; all 245 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`", the four changed Rules lines included) · marker mismatches: none.
- 194 `Expect: pass` cards → no marker. 45 strict xfail cards → `xfail(strict=True)` whose reason names exactly the card's BUG id (new: MCH-RS-17 BUG-890, RS-18 BUG-891, SA-130 BUG-892). 6 non-strict BUG-343 cards → `xfail(strict=False)`, unchanged.
- BUG ids used: BUG-343, 886, 887, 888, 889, 890, 891, 892 — all in `docs/testing/bugs.md`.
- Authorship, confirmed from the file and `machine.local-run.json` (218 entries, 217 accepted, function names equal): 217 tests under a `# [local-coder] <ID>` comment. Of the 29 new ones, **18 local** — MCH-GF-31, GS-31, RS-02, RS-03, RS-04, RS-05, RS-06, RS-07, RS-08, RS-09, RS-10, RS-11, RS-13, RS-14, RS-15, RS-17, RS-18, RS-22 (GF-31 on the second attempt, the others on the first) — and **11 Claude** — the exemplar RS-01; RS-12, RS-16, RS-19, RS-20, RS-21, GF-30, GS-30, SA-128, SA-129 (`Author: claude` cards); SA-130 (report: escalated after 3 attempts).
- `# Then N` comments: present, in order and equal in number to the card's Then lines in all 245. No unused or unknown argument, no fixture used without being requested.
- xfail location (`--runxfail`): 51 failed, each where its card says — the 22 BUG-886 tests in the When call (`… 'astext'`), MCH-RS-17 and RS-18 on Then 3, GF-12 Then 2, GS-12 Then 3, GS-15 and SA-33 Then 2, all others (SA-130 included) on Then 1.

### Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider --cov=app.dao.machine --cov-branch --cov-report=term-missing -rX
  app\dao\machine.py   67   2   22   2   96%   35->37, 50->52, 58, 179
  194 passed, 51 xfailed in 20.21s        (no XPASS)

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider --runxfail -rf
  51 failed, 194 passed in 9.95s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider -rX      (twice more)
  194 passed, 51 xfailed in 9.52s
  194 passed, 51 xfailed in 9.76s          (no XPASS in either)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/machine.py tests/unit/dao/test_machine.py --json <scratchpad>/r3_mut.json
  Mutants: 91 · killed 67 · timeout 0 · survived 24 · score 74%      (raw, before classification; run alone, no pytest beside it)
```
Matches the notes' Result line (194 passed · 51 xfailed, coverage 96%, 2 statements missed, 2 partial branches). Lines 84–90 are covered now. In the `--runxfail` run MCH-GF-26 and GS-27 returned `['Zulu', 'apple', 'Banana']`; the six non-strict tests failed in that run and were xfailed in all three normal runs.

Extra checks, scratchpad only (nothing in the repo written):
```
r3_trace.py   cards ↔ tests ↔ markers ↔ docstrings ↔ `# Then N` ↔ arguments ↔ local-run report → 0 problems
r3_old.py     every test function of the round-2 file and of the two delivered copies against the file → 4 docstring lines
(inline)      failing line of each of the 51 --runxfail failures mapped to its `# Then N` → 51 OK
PYTHONPATH=<scratchpad>/vplug REF3=<variant> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider -p ref3 --runxfail -k "rs_17 or rs_18"
  fix890 (reference fix of BUG-890 / BUG-891):  2 passed
  hidden only from the unfiltered search: RS-17 fails on Then 4 · only from the filtered search, or not from the search: RS-17 on Then 3
  get_by_factory not fixed: RS-18 on Then 3 · get_by_section not fixed: RS-18 on Then 4
PYTHONPATH=<scratchpad>/vplug REF3=rs_<variant> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider -p ref3 -m "not xfail"
  20 variants of restore → the table under "Surviving mutants"
```

### Local-coder patterns (this round)
No functional mistake in 18 tests. All 18 were accepted as designed and all 18 are what their cards say.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| A value swapped between two rows of a kind the card names (factory, user, time, workspace) — the blind spot the executor named | 0 of 5 cards at risk | MCH-RS-02, RS-04, RS-13, RS-14, RS-15 | — (looked for, not found) | Still unguarded: only the read found it absent. Tool: the rebuild-and-compare of builder calls proposed in round 1 (function, every keyword and value) covers it; the "row name must occur" check added since then does not, because both names occur. |
| Test name cut at 70 characters | 10 | MCH-RS-17 / RS-18 (same words after the ID), GF-31, GS-31 (end in `_s`) | cosmetic — tool, not model | Tool: raise the limit or cut on the title's last full phrase. Already listed. |
| Fixture arguments in order of first use instead of the exemplars' order | 3 | MCH-RS-02, RS-03, RS-11 | cosmetic | Tool: sort the argument list on acceptance. Already listed (round 1: 11). |
| Variable names other than the sheet's when two rows are re-read | 2 | MCH-RS-14, RS-22 | cosmetic | Nothing needed; RS-15 reuses `row` for three rows and is harder to read than RS-14. A sheet line "re-read of a second row: `row_<name>`" would make them uniform. |
| A blank line between the Given rows and the snapshot | 1 | MCH-GS-31 | cosmetic | Nothing needed. |

Observations for `docs/testing/local-coder-improvements.md`:
- **Then lines after the failing line of an xfail test are checked by nothing** (MCH-RS-17, RS-18 Then 4; in revision 0 the 22 BUG-886 tests). Both were right here. The tool knows `fails_in_then` and the number of Then lines, so it can list "never executed: <ID> Then N…" in its report for the verifier; a throw-away reference fix as a scratch plugin (20 lines here) is enough to run them once at stage 5.
- **MCH-SA-130 (P19).** The report shows the card as escalated after three attempts; the hand-written test in the file is the card exactly, with the escaped literal. The tool's own behaviour was not probed again in this round — the executor's analysis in the notes stands as reported, not as verified here.
- **The single retry (MCH-GF-31, `f1` used only in the When call)** is the known pattern; the accepted test requests `f1` and is faithful.
- **What worked:** `deleted=True` as one keyword (16 of 16 local "deleted" rows right, never expanded by hand, never added to a live row); the one-sentence When line for `restore` in the sheet (16 of 16 local calls right at the first attempt, with the hand-written RS-01 not even printed in the sheet); "after the call" list lines written as ready expressions in the cards (RS-11, RS-17, RS-18, RS-22 copied without change).
- **Single-point checks to keep in mind when a card is edited:** MCH-RS-09 is the only test that notices an UPDATE with nothing to change, RS-14 the only one that notices a restore of the whole factory, RS-06 the only one for an activity event, RS-10 the only one for a state check, RS-12 (hand-written) the only one for a commit.

**Still open (none blocks PASS):**
- Optional, executor: cosmetic findings 1, 2, 3, 5 of this round and 2, 3, 5 of round 1.
- Optional, tool: the name cut (finding 4), sorting the argument list, the rebuild-and-compare check, the never-executed-Then list, and P19 (`"\tbolt\n"` rejected by the text check).
- Not a test matter: Q8 and Q9 are provisional; the "hidden, not cascaded" reading is open with the reviewer; the markers of BUG-886 (22 tests), BUG-343 (6), BUG-890 / 891 / 892 (now also RS-17, RS-18, SA-130) come off by hand when those bugs are fixed.

---

*Everything below is history: first round 2 (PASS on 216 tests, cases revision 0), then the round-1 report. Their header lines were:*

> **Verdict:** PASS (round 2; round 1 was NEEDS WORK — see "Round 2" directly below, the rest of this file is the round-1 report kept as history)
> Tests: 168 passed · 48 xfailed (reproduced ✅) · coverage 88% branch (67 statements, 9 missed: lines 58, 84-90 dead code, 179 behind BUG-886; 22 branches, 2 partial: 35->37, 50->52 dead parameter)
> Mutation: 91 mutants · 64 killed · 27 survived → score 100% (after excluding 3 equivalent, 9 dead, 15 bug-path)
> Source commit: e48a092 · Cases revision: none stated (READY on pilot defaults, 216 cases; spec still IN REVIEW)

## Round 2 — re-verification after fix round 1
**Result: PASS.** The one required finding (MCH-SA-32) is fixed and nothing else changed. Open items are optional only.

**1. MCH-SA-32 re-read against its card — faithful.**
| Card | Test (line 2277 ff.) |
|---|---|
| Given 1. M1 = machine, `name "Lathe"` | `m1 = mk_machine(name="Lathe")` |
| Given 2. assignment of M1 to S1 | `mk_assignment(of=m1, to=s1)` ← was `to=s3` |
| Given 3. M2 = machine, `name "Press"`, but `factory_id F2.id` | `m2 = mk_machine(name="Press", factory_id=f2.id)` |
| Given 4. assignment of M2 to S3 | `mk_assignment(of=m2, to=s3)` |
| When `dao.search_advanced(db, workspace_id=W1.id, factory_id=F2.id, factory_section_id=S3.id)` | identical, lower-case names |
| Then 1. `ids(result) == [M2.id]` | `assert ids(result) == [m2.id]` under `# Then 1` |

Arguments are now `(db, w1, f2, s1, s3, mk_machine, mk_assignment)` — every fixture used is requested, in the standard order. Finding 1 of round 1 is closed.

**2. Nothing else changed.**
- Against my round-1 state (the side-by-side listing of all 216 test bodies, decorators and signatures saved in round 1, regenerated now and diffed): exactly two lines differ, both in MCH-SA-32 (the signature and the `to=` row).
- Against the delivered copy `test_machine.asdelivered.py`: of the 199 `# [local-coder]` test functions, 194 are byte-identical; INH-01 … INH-04 differ by the one removed blank line (Step D) and SA-32 by the fix. The scaffold differs only by the Step D items (four `# noqa: F401` removed, `from unittest.mock import patch` added); the remaining differences are the hand-written `Author: claude` tests and helpers that the delivered copy did not contain yet, and the two moved blocks.
- The rebuild script (expected body from each of the 204 vocabulary cards vs. the test) now reports **0 differences** (round 1: 1). Docstrings: 216 / 216 equal to card title and rules. Traceability re-checked: 216 cases, 216 tests, no marker mismatch.
- The cosmetic findings 2–5 are unchanged, as decided (argument order in 11 local tests, variable names in 5, names cut in 53 local + 2 exemplars). They do not affect what is checked and do not block PASS.

**3. Runs.**
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider --cov=app.dao.machine --cov-branch --cov-report=term-missing
  app\dao\machine.py   67   9   22   2   88%   35->37, 50->52, 58, 84-90, 179
  168 passed, 48 xfailed in 17.52s
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider --runxfail -rf
  48 failed, 168 passed in 8.13s        (all 48 on the line their card names; script xfl.py: 48 OK)
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider -rX      (12 more times)
  168 passed, 48 xfailed                 (12 of 12; no XPASS)
```
Same as round 1 and as the notes' Result line.

**The reported `168 passed, 47 xfailed, 1 xpassed` run.** I could not reproduce it: 0 XPASS in the 13 normal runs of this round (and 0 in the 3 of round 1), so I cannot name the test from my own evidence. What can be said:
- **Certain:** it was one of the six non-strict BUG-343 tests (MCH-GF-20, GF-26, GF-27, GS-21, GS-27, GS-28). A strict xfail that passes is reported by pytest as **failed**, and that run had no failure — so only a `strict=False` test can have produced "1 xpassed".
- **Likely, not observed:** MCH-GF-26. It is the only one of the six whose returned order I have seen change between runs (`['Zulu', 'Banana', 'apple']` in round 1's `--runxfail` run, `['Zulu', 'apple', 'Banana']` in this round's, `['Banana', 'Zulu', 'apple']` in the executor's notes); its expected `["apple", "Banana", "Zulu"]` is one more permutation of the same three rows. The other five returned the same (insertion) order in every run I have. A run with `-rX` prints the name if it happens again.
- **Consistent with the design: yes.** The spec's "Notes for the test designer" prescribe a non-strict xfail for `get_by_factory` R6 / `get_by_section` R7 because "today's order is whatever the database returns"; the six cards say "(non-strict)" and "may happen to give this order"; the notes' maintainer section says they "may XPASS at random". The assertion is the full intended order and is not weakened. An XPASS of a non-strict test does not fail the run (exit code 0).
- **Under the skill** ("any change in outcome is a flaky test (finding)"): taken literally it is a change in outcome, so it is recorded here rather than hidden. I do **not** raise it as a finding to be fixed, for two reasons: no outcome changed in any of my 16 normal runs, and no stage can remove the variation without either weakening the card's assertion (which the skill forbids suggesting) or fixing BUG-343 — the instability *is* the bug these six cards document. It resolves when BUG-343 is fixed (the markers then come off by hand, as the notes say). This is a judgment call: if the literal reading is preferred, the only change to this report is one extra row "Flaky by design (claude) — the six non-strict BUG-343 tests, seen on one of them — fix by: — (resolves with BUG-343)"; nothing else in the verdict depends on it.

**4. Mutation — full run not repeated; targeted run done.**
The fix changes one Given row of one passing test and no source line, so the mutant set is unchanged (91) and only kills that depended on MCH-SA-32 could move. MCH-SA-32 exercises the factory and section filters; its old (wrong) setup happened to be a second copy of MCH-SA-30's cross-wired shape, so in theory a kill could have been lost. I re-ran the tool on exactly those lines instead of arguing it:
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/machine.py tests/unit/dao/test_machine.py --lines 110-124 --json <scratchpad>/r2v_mut_110-124.json
  Mutants: 13 · killed 13 · timeout 0 · survived 0 · score 100%
```
All 13 mutants of lines 110–124 (workspace / soft-delete base filter, `factory_id`, `factory_section_id` join and filter, `is_running`) are still killed, as in round 1. The other 78 mutants are in code MCH-SA-32 does not distinguish (search text, `has_*` filters, sorting, paging, the other three methods, dead code, the BUG-886 block), so the round-1 result stands: 91 mutants · 64 killed · 27 survived → 100% after excluding 3 equivalent, 9 dead, 15 bug-path. The "Surviving mutants" table below is unchanged.

**Still open (none blocks PASS):**
- Optional, executor: cosmetic findings 2, 3, 5 (argument order, variable names, two cut exemplar names).
- Optional, tool (`tests/unit/_tools/local_coder.py`): the name cut (finding 4), and the acceptance check that would have caught MCH-SA-32 (every row name of a card's Given must occur in the test body; or the full rebuild-and-compare) — see "Local-coder patterns".
- Not a test matter: the spec is still IN REVIEW on pilot defaults; the 22 BUG-886 tests and the six BUG-343 tests need their markers removed by hand when those bugs are fixed.

---

*Everything below is the round-1 report, unchanged apart from the verdict line above. Its finding 1 is closed by round 2.*

## Summary
One test must be repaired; everything else can be trusted. All 216 tests were read against their cards line by line — every Given row and column value, the When call and each keyword argument, every numbered Then line. Nothing was sampled. As a second, independent check a script rebuilt the expected body from each of the 204 cards written in the Conventions vocabulary (199 local + 5 exemplars: builder calls in card order with every keyword and value, the When call, the `raises` wrapping, snapshots taken before the call, one assertion block per `# Then N`) and compared it with the test. Read and script agree: **1 difference in 204 bodies**.

- **Local-model tests (199): functional findings in 1 / 199 tests (MCH-SA-32) · cosmetic findings in 61 / 199 tests** — 53 names cut by the tool at 70 characters, 11 argument lists in a non-standard order, 5 tests with variable names other than the helper sheet's (8 tests have two of these). Counting only what the model itself wrote (argument order, variable names): 16 / 199.
- **Claude-written tests (17): functional findings in 0 / 17 tests · cosmetic findings in 2 / 17 tests** (two exemplar names cut at 70 characters).
- The one functional finding is a wrong `to=` on an assignment row (MCH-SA-32 builds "assignment of M1 to S3", the card says S1). The test still passes and, as it happens, is not easier to satisfy than the card's scenario — but it is not the scenario the card designed. Fix by the executor; no card, spec or source change.
- All 48 xfail tests fail under `--runxfail` on the line their card names. Three runs gave the same outcome (no flaky test; the six non-strict BUG-343 tests never passed).
- Every surviving mutant is in dead code (9), behind BUG-886 (15), or equivalent (3).
- The 22 BUG-886 tests fail inside the When call, so no normal run has ever executed their Given rows or expected lists. Besides the read, they were executed once against a scratch reference implementation of spec R12–R12e (a pytest plugin in the scratchpad; nothing in the repo touched): **22 / 22 pass**, and each of nine deliberately broken variants (tie → lowest id, latest by id, oldest, fall back to an older status, any event matches, no workspace filter on events, any event type, duplicate rows, no paging) is failed by at least one of them. Their rows and expected lists are consistent with the spec.

Limit of this verdict: the spec is IN REVIEW on pilot defaults. If the reviewer changes P1–P3, Q1–Q7, the cards listed in the cases file under "Pilot answers" change with them.

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | Wrong setup (local) — **FUNCTIONAL** | MCH-SA-32, `test_machine.py` line 2278 | Given row 2 of the card is "assignment of M1 to S1"; the test assigns M1 to **S3**. The card's scenario is "M1 in F1/S1, M2 in F2/S3, ask for F2 + S3 → only M2" (M1 fails both filters). The test's scenario is "M1 of F1 also points at S3" (M1 fails the factory filter only) — the cross-wired shape that belongs to MCH-SA-30. `s1` is neither requested nor used. The When call and Then 1 are right, and the test passes, so no run, the tool's keyword check (`to=` and `s3` are both words of the card) or the fixture check could see it. Effect on detection: not weaker than the card for any breakage found (a filter that matched factory OR section would even be caught only by this variant), but the designed case is not what is tested. | `mk_assignment(of=m1, to=s3)` vs. card `2. assignment of M1 to S1.`; signature `(db, w1, f2, s3, mk_machine, mk_assignment)` | executor — `to=s1`, add `s1` to the arguments |
| 2 | Style (local) — COSMETIC | MCH-SD-02, SD-07, SD-09, GS-12, GS-15, GS-16, SA-18, SA-25, SA-29, SA-33, INH-18 (11 tests) | Fixture arguments not in the order every other test uses (workspaces, users, factories, sections, builders). SD-02 `(db, u2, f2, u1, w1, …)` is left over from its three attempts (fixtures appended after each "used but not requested" rejection); the others follow the order of first use in the card. All listed fixtures are used; nothing is missing. | `def test_mch_sd_02__…(db, u2, f2, u1, w1, mk_machine)`, `def test_mch_inh_18__…(db, w1, fd, w2, f9, mk_machine)` | optional — executor (or let the tool sort the list) |
| 3 | Naming (local) — COSMETIC | MCH-SD-04, INH-08, INH-09 (`row_a1`, `row_m1`); MCH-SD-12, SA-21 (`before_written`) | Variable names other than the helper sheet's `row` / `before`. Each is assigned from the right call (`reread(db, a1)`, `written(db)`) at the right place and used in the right assertion; in SD-04 the two names even keep the two re-read rows apart. | `row_a1 = reread(db, a1)`, `before_written = written(db)` | optional — executor |
| 4 | Naming (local) — COSMETIC | 53 tests: MCH-GF-03, GF-04, GF-29, GS-04, GS-07, GS-11, GS-14, GS-15, GS-16, SD-02, SD-06, SA-01, SA-04, SA-05, SA-06, SA-07, SA-13, SA-14, SA-17, SA-18, SA-21, SA-26, SA-32, SA-34, SA-51, SA-61 … SA-67, SA-70, SA-71, SA-73, SA-80, SA-81, SA-108, SA-109, SA-110, SA-120, SA-123, SA-124, SA-125, INH-01, INH-03, INH-04, INH-07, INH-08, INH-09, INH-11, INH-12, INH-18 | The test name is cut at 70 characters and no longer carries the whole title (always at a word boundary; none inside a word). The docstring carries the full ID and title in all 216 tests, so traceability is intact. Made by the tool's `normalize`, not by the model. | `test_mch_sa_32__the_matching_factory_and_section_pair_of_the_other_factory_returns` | optional — tool (`tests/unit/_tools/local_coder.py`) |
| 5 | Naming (claude) — COSMETIC | MCH-SD-01, MCH-INH-13 (exemplars) | Same cut in two hand-written exemplars (the hand-written MCH-SD-08 keeps its full 95-character name, so the file is not uniform). | `test_mch_sd_01__…_and_the_acting`, `test_mch_inh_13__…_pointing_at_its_old` | optional — executor |

Checked for and **not** found, in all 199 local tests (by reading; items marked ✓ also by the rebuild script):
- a missing, extra or reordered Given row ✓; a wrong or missing column on a machine — `workspace_id`, `factory_id`, `is_running`, `is_active`, `deleted`, `model_number`, `manufacturer`, `note`, `created_at`, `updated_by` ✓ (the `search_advanced` cards were read with the tool's blind spot in mind: no machine row carries a keyword taken from the When call);
- a wrong `of=` on an assignment or event ✓ (the one wrong `to=` is finding 1); a wrong `created_at`, `metadata_json`, `event_type` or `workspace_id` on an event ✓ — including MCH-SA-74 (newer status inserted first), SA-75 / SA-76 / SA-84 (tie rows in card order), SA-80 (`metadata_json=None`), SA-81 (`{"note": "x"}`), SA-82 / SA-83 (`workspace_id=w2.id` on the event, not on the machine);
- whitespace and special characters, compared as Python values ✓: MCH-SA-39 `"   "` (three spaces), SA-40 `" \t\n"`, SA-41 `" bolt "`, SA-42 `"  bolt"` (two leading), SA-43 `"cutter "`, SA-45 `"bolt  cutter"` (two inner), SA-61 … SA-64 `""` and `"   "`, SA-55 / SA-56 / SA-57 `"%"`, `"50%"`, `"500"`, SA-58 / SA-59 `"_"`, `"Lathe_2"`, `"ACME_1"` / `"ACME-1"`, `"acme_1"`, SA-60 `"a\\b"` in both the name and the search;
- a changed, dropped or added When argument ✓ (explicit `None`, `0`, `-1`, `""`, `skip=0` are all kept; MCH-SA-25 passes all seven `None`s);
- a skipped Then line, an assertion under the wrong `# Then N`, or one weaker than the card ✓ — every ordered list is compared with `==` in the card's order; `sorted(...)`, `set(...) <=`, `len` and `in [...]` occur only where the card itself writes them (`get_by_factory` / `get_by_section` paging cards); no bare number outside `count:` lines;
- write cards ✓: every `soft_delete` / `create` / `update` card re-reads through `reread(db, …)` (which expires the session first) and reads each listed column from that row; every "unchanged" / "nothing written" snapshot is taken after the last Given row and before the When call (GF-12, GF-14, GF-25, GS-12, GS-14, GS-16, GS-25, GS-26, SD-10, SD-12, SA-21, SA-121, SA-122, INH-02 … INH-04, INH-10 … INH-12); no snapshot is taken where the card has no such line;
- swallowed failures or extra mocks: `pytest.raises` only on `raises:` cards, with the card's type; `begin_nested` only for `DataError` / `IntegrityError`; no BUG-886 call is wrapped; nothing is patched in any test (the only patch is the scaffold's `utcnow`, the spec's one external; MCH-SD-08 wraps `db.commit` as the Conventions prescribe).

The 17 Claude-written tests (5 exemplars, 12 `Author: claude` cards, plus the scaffold they rest on — standing rows, `mk_machine`, `mk_assignment`, `mk_event`, `mk_101`, `commit_spy`, the reading helpers) were read the same way: no functional finding.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 24 | 55 | default `skip` `0` → `1` | dead | Signature of `get_active_by_workspace`; spec "Not specified": dead code, to be removed (Q4). | — |
| 25 | 55 | default `limit` `100` → `101` | dead | Same method (Q4). | — |
| 5 | 58 | `return (…)` → `return None` | dead | Body of `get_active_by_workspace` (Q4). | — |
| 81 | 62 | `==` → `!=` (`workspace_id`) | dead | Same method (Q4). | — |
| 82 | 63 | `==` → `!=` (`is_deleted`) | dead | Same method (Q4). | — |
| 86 | 63 | `False` → `True` | dead | Same method (Q4). | — |
| 28 | 84 | `False` → `True` | dead | Body of `restore`; spec "Not specified": dead code, to be removed (Q5). | — |
| 29 | 85 | `True` → `False` | dead | `restore` (Q5). | — |
| 7 | 90 | `return db_obj` → `return None` | dead | `restore` (Q5). | — |
| 30 | 104 | default `sort_by` `"name"` → `""` | equivalent | Line 188 is `sort_field_map.get(sort_by, Machine.name)`: `""` is not a key, so the default sort column is still `Machine.name` (spec R13: any other value sorts by name). | — |
| 31 | 105 | default `sort_dir` `"asc"` → `""` | equivalent | Line 189 only tests `sort_dir == "desc"`; `""` and `"asc"` both sort ascending (spec R15). | — |
| 52 | 185 | map key `"name"` → `""` | equivalent | `sort_by="name"` then misses the map and falls back to the `.get` default, which is the same column `Machine.name`; `""` now hits it directly — same column again. | — |
| 87 | 149 | label `"machine_id"` → `""` | bug-path | Inside `if latest_event_type is not None:` (lines 147–182). Every call that enters the block raises `AttributeError` on line 163 today (BUG-886); only the 22 xfail tests MCH-SA-67 … SA-70, SA-72 … SA-89 enter it, and xfail tests are excluded from the run. | — (resolves with BUG-886) |
| 88 | 150 | label `"latest_created_at"` → `""` | bug-path | Same block. | — (resolves with BUG-886) |
| 79 | 153 | `==` → `!=` (event `workspace_id`) | bug-path | Same block; the rule is asserted by MCH-SA-82, SA-83 (xfail). | — (resolves with BUG-886) |
| 80 | 154 | `==` → `!=` (`event_type`) | bug-path | Same block; MCH-SA-77, SA-78, SA-79 (xfail). | — (resolves with BUG-886) |
| 83 | 154 | `"status_updated"` → `""` | bug-path | Same block; MCH-SA-77 … SA-79 (xfail). | — (resolves with BUG-886) |
| 89 | 162 | label `"machine_id"` → `""` | bug-path | Same block. | — (resolves with BUG-886) |
| 91 | 163 | JSON key `"status"` → `""` | bug-path | The line that raises today. | — (resolves with BUG-886) |
| 90 | 163 | label `"status"` → `""` | bug-path | Same line. | — (resolves with BUG-886) |
| 84 | 168 | `==` → `!=` (join on `machine_id`) | bug-path | After line 163; never reached today. | — (resolves with BUG-886) |
| 85 | 169 | `==` → `!=` (join on `created_at`) | bug-path | Never reached; MCH-SA-72 … SA-76 (xfail). | — (resolves with BUG-886) |
| 75 | 173 | `==` → `!=` (event `workspace_id`) | bug-path | Never reached; MCH-SA-82, SA-83 (xfail). | — (resolves with BUG-886) |
| 76 | 174 | `==` → `!=` (`event_type`) | bug-path | Never reached; MCH-SA-77 … SA-79 (xfail). | — (resolves with BUG-886) |
| 78 | 174 | `"status_updated"` → `""` | bug-path | Never reached. | — (resolves with BUG-886) |
| 77 | 180 | `==` → `!=` (join machines ↔ status) | bug-path | Never reached (line 179 is the one uncovered live line). | — (resolves with BUG-886) |
| 67 | 181 | `==` → `!=` (status == enum value) | bug-path | Never reached; MCH-SA-67 … SA-70 (xfail). | — (resolves with BUG-886) |

Score: 64 killed / (91 − 3 equivalent − 9 dead − 15 bug-path) = 64 / 64 = 100%. No `test-weakness`, `case-missing` or `spec-gap` survivor.

## Traceability
cases 216 · tests 216 · unmatched: none (each case ID is in exactly one test name and starts that test's docstring; all 216 docstrings equal "`<ID> — <card title>.` / `Rules: <card rules>`") · marker mismatches: none.
- 168 `Expect: pass` cards → no marker. 42 strict xfail cards → `xfail(strict=True)` whose reason names exactly the card's BUG id. 6 cards "xfail BUG-343 (non-strict)" (MCH-GF-20, GF-26, GF-27, GS-21, GS-27, GS-28, all `Author: claude`) → `xfail(strict=False, reason="BUG-343: …")`, as the cases file's Conventions prescribe.
- BUG ids used: BUG-343, 886, 887, 888, 889, 890, 891, 892 — all have a row in `docs/testing/bugs.md`.
- 199 tests carry a `# [local-coder] <ID>` comment with the ID of the test below it = the 199 cases of `machine.local-run.json`; the 5 exemplars and 12 `Author: claude` cards carry none.
- `# Then N` comments: present, in order, and equal in number to the card's Then lines in every test.
- xfail location (`--runxfail`): 48 failed, each in the Then line its card names — the 22 BUG-886 tests in the When call itself (`AttributeError: … 'astext'`, before `# Then 1`, as the cards say "the call raises"), the other 26 on the asserted line (GF-12 Then 2, GS-12 Then 3, GS-15 and SA-33 Then 2, all others Then 1).

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider --cov=app.dao.machine --cov-branch --cov-report=term-missing
  app\dao\machine.py   67   9   22   2   88%   35->37, 50->52, 58, 84-90, 179
  168 passed, 48 xfailed in 17.81s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider --runxfail -rf
  48 failed, 168 passed in 8.59s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider -rxX      (twice more)
  168 passed, 48 xfailed in 8.41s
  168 passed, 48 xfailed in 8.28s          (0 XPASS in either)

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/machine.py tests/unit/dao/test_machine.py --json <scratchpad>/mut.json
  Mutants: 91 · killed 64 · timeout 0 · survived 27 · score 70%      (raw, before classification; run alone, after the pytest runs)
```
Matches the notes' Result line (168 passed · 48 xfailed, coverage 88%, 9 statements missed, 2 partial branches). MCH-GF-26 returned `['Zulu', 'Banana', 'apple']` in the `--runxfail` run (the notes saw another order): the order of the two unordered lookups really is unstable, which is BUG-343; the test failed in every run.

Extra checks, scratchpad only (nothing in the repo written):
```
sbs.py       side-by-side listing of every card and its test, used for the read; also the traceability checks above → 0 problems
rebuild.py   expected body rebuilt from each of the 204 vocabulary cards and compared with the test → 1 issue (MCH-SA-32, Given row 2)
cos.py       docstrings, unused / unknown arguments, argument order, variable names, name cut → findings 2–5
xfl.py       failing line of each of the 48 --runxfail failures mapped to its `# Then N` → 48 OK
PYTHONPATH=<scratchpad>/vplug REF886=<variant> .venv/Scripts/python.exe -m pytest tests/unit/dao/test_machine.py -q -p no:cacheprovider -p ref886 --runxfail -k "<the 22 BUG-886 tests>"
  reference implementation of R12–R12e:  22 passed
  tie → lowest id: SA-75, SA-76 fail · latest by id: SA-74 · oldest: SA-72 … SA-76, SA-80, SA-81 · fall back to older status: SA-80, SA-81
  any event matches: SA-73, SA-76, SA-80, SA-81 · no workspace filter on events: SA-82, SA-83 · any event type: SA-77, SA-78, SA-79
  duplicate rows on a tie: SA-75, SA-84 · no paging: SA-87
```

## Local-coder patterns
One functional mistake in 199 tests (0.5%); it is of a kind the accepting tool cannot see today and a mechanical check can.

| Pattern | Count | Example case IDs | Kind | What would prevent it |
|---|---|---|---|---|
| A value of one Given row replaced by a value from a neighbouring row / the When call: `to=s3` on the row "assignment of M1 to S1", where row 4 and the When call both say S3 | 1 | MCH-SA-32 | **functional** (wrong setup; passes as designed) | **Tool, either of two checks.** (a) Cheap: every row name a card's Given mentions (`S1`, `F2`, `MD` …) must occur in the test body — the mirror of the existing "fixture used but not requested" check. `s1` never occurs in this test, so it would have been rejected at acceptance. (b) Complete: rebuild the builder calls from the Given rows (function, every keyword and value, order) and compare with the test; the verifier's `rebuild.py` did this for 204 cards with no false alarm. The helper sheet already says "a value of the When call or of another row is not a value of this row" — the wording did not prevent it, so a prompt change alone is not enough. |
| Fixture arguments in the order of first use, or appended after a rejection, instead of the exemplars' order | 11 | MCH-SD-02, MCH-INH-18, MCH-GS-15 | cosmetic | Tool: sort the argument list (workspaces, users, factories, sections, builders) when accepting. Not worth a prompt line. |
| Variable names other than the sheet's (`row_a1` / `row_m1`, `before_written`) | 5 | MCH-SD-04, MCH-INH-08, MCH-SD-12 | cosmetic | Nothing needed; in SD-04 the distinct names are clearer than reusing `row`. If uniformity matters: sheet line "`before` is always the name of the `written(db)` snapshot". |
| Test name cut at 70 characters (always at a word boundary) | 53 | MCH-SA-32, MCH-SA-123, MCH-INH-18 | cosmetic — tool, not model | Tool: raise the limit, or leave as is — the docstring carries the full title. The two cut exemplar names (MCH-SD-01, INH-13) come from the same rule; the hand-written MCH-SD-08 is not cut. |

Observations for `docs/testing/local-coder-improvements.md`:
- **Blind spots named by the executor, measured here.** Wrong `workspace_id=` / `factory_id=` / `is_running=` / `deleted=` on a machine row in `search_advanced` cards: 0 in 124 local cards. Wrong `of=` on an assignment or event, wrong `created_at` / `metadata_json`: 0. Wrong `to=`: 1 (MCH-SA-32). Whitespace-only and special-character strings: 0 wrong in 17 cards. The 22 never-executed BUG-886 tests: 0 wrong rows, 0 wrong expected lists (read, rebuilt by script, and run against a reference implementation). Weaker assertion, wrong expression under a `# Then N`, dropped qualifier, row order, bare numbers: 0. Write cards (re-read, snapshots before the call): 0 wrong in 23 local cards.
- **Where the one mistake sits.** Three consecutive cards share almost the same Given (MCH-SA-30: M2 → S1; SA-31 and SA-32: M1 → S1, M2 → S3) and differ in the When call. The model got SA-30 and SA-31 right and, in SA-32, repeated the When call's section on both assignment rows. Near-duplicate neighbouring cards whose rows differ in one name are the risky shape; the mirror check (a) costs a few lines and covers exactly this.
- **What worked and is worth keeping:** keyword-only builders with the card's own words (`of=`, `to=`), `deleted=True` as one keyword (never expanded by hand in 199 tests), constants for T0 … T3 / NOW / MISSING / the four statuses, Then lines written as ready expressions, "re-read" as `row = reread(db, x)` plus one assert per value, and the exemplars for the three `raises` shapes (all 12 local `raises` tests have the right wrapping and no stray `pytest.raises` around a BUG-886 call).
- **An xfail test that fails inside the call can still be checked.** A throw-away reference implementation of the tagged rule, loaded as a scratch pytest plugin, let all 22 BUG-886 tests run once; nine broken variants showed that each rule R12a–R12e is pinned by at least one test. Worth doing at stage 5 whenever a whole rule group is unreachable today.
