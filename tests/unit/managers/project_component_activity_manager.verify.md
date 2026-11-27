# Verification — `app/managers/project_component_activity_manager.py`

> **Verdict:** PASS (round 1, 2026-11-04)
> Tests: 45 passed · 7 xfailed (reproduced ✅) · coverage 100% branch (23 statements, 2 branches)
> Mutation: 9 mutants · 9 killed · 0 survived → score 100% (9 / 9; none excluded)
> Fidelity: **0 of 52 unfaithful**
> Hand variants on my reference: 45 · 43 caught · 2 survived (both equivalent)
> Source commit: e48a092 · Cases revision: 0 (52 cases; spec APPROVED)

## Summary
- **The tests can be trusted.** I read all 52 tests against their cards. Each Given is built (all standing rows exist in every test, in Conventions order), each When is the card's call, and each numbered Then line is asserted with the card's exact value, in order.
- **The evidence goes beyond reading.** Mutation killed all 9 mutants, each by a real test failure. My own reference fix passes 52 of 52 with `--runxfail`, and 43 of 45 hand variants on it are caught, each by the card meant for that rule. The 2 survivors cannot change behavior.
- **All 7 strict xfails fail where their cards say.** None fails on a setup or import error.
- **Nothing to route.** I found no new bug, so BUG-1740…1749 are unused. No money or order-workflow question arises.

All 52 tests were written by Claude (`# [claude]`). No `project_component_activity_manager.local-run.json` exists, so there is no `## Local-coder patterns` section. Findings in local-written tests / local-written tests: 0 / 0. In the others: 0 / 52.

## Findings
None.

The test file does not import the class `ProjectComponentActivityManager`, though the Conventions name it. No card uses the class, so this is not a finding. The notes record why (ruff F401).

## Surviving mutants
None. All 9 were killed, so no class is used.

- Each kill's last line reads `1 failed`, with no setup error, and the number of tests passed before it fits the expected card. For example, #5 (`limit` default 100 → 101) stops after 36 passes, at PCAM-LI-17.
- `mutate.py` does not mutate keyword arguments of calls (`skip=skip`, `limit=limit`, `workspace_id=…`), and this file has only 9 mutation sites. The hand variants below cover the rest.

## Hand variants
`pcamv.py` is a pytest plugin (`-p pcamv`, scratch folder on `PYTHONPATH`). It replaces both methods on the class in-process. Nothing under `app/` is touched. `PCAMREF=fix` is my own reference: `log_event` checks the component in the workspace first and raises the 404, and `list_events` reads a page's performers in one `IN` query. `PCAMVAR=<name>` is the reference with one fault, and an unknown name raises, so no variant is a silent no-op. Every run used `--runxfail` and had no setup error. "T" is the Then line that failed.

| Method | Variants | Caught | Survivors |
|---|---|---|---|
| `log_event` | 21 | 20 | `le_ws_from_component` |
| `list_events` | 24 | 23 | `li_ws_from_component` |

**The four rules the cards claim, as asked:**

| Rule | Variant | Caught by |
|---|---|---|
| Workspace check removed | `le_nocheck` (today's code) | LE-13, LE-14 T1 `DID NOT RAISE`; LE-15, 16, 17 T1 on the foreign key |
| | `le_check_any_ws` (component exists, any workspace) | LE-13, LE-14, LE-17 T1 |
| | `le_check_after_add` (row added, then 404) | LE-13, LE-14 T4 (`len(db.new)`), only |
| | `le_check_after_flush` (row flushed, then 404) | LE-13, LE-14 T5 (nothing written); LE-15…17 T1 |
| | `li_nocheck` | LI-05 … LI-11 T1 (LI-10 included) |
| | `li_check_any_ws` | LI-05, LI-06, LI-10, LI-11 T1 |
| | `li_check_after_read` (page read before the check) | LI-05, LI-06 T4 (`len(sql_log) == 1`), LI-10 T1 (`DataError` first) |
| Performers read per entry | `li_perf_per_entry` (today's code) | LI-25 T3 (`7 <= 3`), LI-26 T3 (`6 <= 3`) |
| | `li_perf_per_person` (one read per distinct person) | LI-26 T3 (`4 <= 3`), only |
| | `li_perf_copy` (a new instance per entry) | LI-16 T3 (`is`), only |
| | `li_perf_first`, `li_perf_none` | LI-16 T5, LI-26 T2 · LI-16, LI-24, LI-25, LI-26 |
| Ordering changed | `li_order_asc` | LI-01, 02, 03, 13, 15, 16, 17, 18, 25, 26 |
| | `li_order_id_desc` (id only) | LI-01 T2, LI-02 T1 |
| | `li_order_tie_id_asc` (tie broken by lower id) | LI-02 T1, only |
| Commit dropped / added | `le_noflush` (flush dropped: row never stored) | LE-01 … LE-12, LE-18, 19, 22, 25 |
| | `le_noadd` (row built, never added) | 20 pass cards, each on its first Then |
| | `le_commit` (`log_event` commits) | LE-25 T3 (commit spy), only |
| | `li_commit`, `li_flush` (`list_events` writes) | LI-27 T1/T2 · LI-24 … 26 T3 for `li_commit` |

The manager never commits, so "commit dropped" has no direct form here. I read it as the write not reaching the database (`le_noflush`, `le_noadd`) and checked the other side, a commit added (`le_commit`, `li_commit`).

**Other variants, all caught:** 403 or other detail text (all 12 404 cards, T2 or T3) · FOR UPDATE on the check (LE-04 T4, LI-27 T10) · component touched (LE-04 T2) · two rows (LE-01 T5, LE-03, LE-18, LE-19, LE-25) · performer dropped (LE-01, 02, 20, 21, 22) · `0` read as no performer (LE-21) · metadata dropped (7 cards) · `None` → `{}` (LE-05, LE-06) · `None` → SQL `NULL` (LE-05, LE-06 `stored_meta`) · Decimal turned into text (LE-23) · `event_type` cut to 50 (LE-11) · type and description swapped (7 cards) · skip ignored, limit ignored, skip and limit swapped (LI-03, 04, 12, 18–23) · invalid row not filtered (LI-12, only) · `expire_all` (LI-27 T5) · lists instead of tuples (LI-01 T3) · an iterator instead of a list (11 cards).

**Survivors:**

| Variant | Class | Why |
|---|---|---|
| `le_ws_from_component` | equivalent | Takes the row's workspace from the component. After the check has passed, the two are the same value. |
| `li_ws_from_component` | equivalent | The same, for the page read in `list_events`. |

## xfail tests against the reference
- **52 passed** with `--runxfail` and `PCAMREF=fix`. With the markers on, the 7 strict cards turn `XPASS(strict)` (7 failed, 45 passed), so no pass card pins a bug.
- **Then lines past each failure point:** 19 (LE-13, LE-14 T2–T6; LE-15, 16, 17 T2–T4). LI-25 and LI-26 fail on their last line. All 19 pass on the reference.
- **14 were made to fail on their own line:** T2 and T3 of all five (403 and detail variants), LE-13 and LE-14 T4 (`le_check_after_add`), and T5 (`le_check_after_flush`).
- **5 cannot fail on their own:** LE-13 and LE-14 T6 follow from T5 (no event exists before the call). LE-15, 16 and 17 T4 sit after the card's own savepoint, which rolls back any write.

## Reproduced claims
- The notes' Result line matches: 45 passed, 7 xfailed, 100% branch.
- **Each strict xfail fails where its card says:** LE-13 and LE-14 at T1 `DID NOT RAISE HTTPException` (lines 450, 471). LE-15 and LE-16 at T1 on `project_component_activity_events_project_component_id_fkey`. LE-17 at T1 on `…_workspace_id_fkey`. LI-25 at T3 `assert 7 <= 3` (line 1048). LI-26 at T3 `assert 6 <= 3` (line 1068). None is a setup error.
- **No flaky test.** Four default runs (coverage, plain, `--tb=no`, `-W error`) all gave 45 passed and 7 xfailed. One run with `--runxfail` gave 7 failed and 45 passed.
- **Mocks:** none. The only spy is LE-25's commit spy, as Conventions name. There is no broad `pytest.raises` and no `try` around an action; the one `try` is the cleanup in `sql_recorder`. Every write card re-reads from the database (`reread_event` / `reread_snap` expire first).
- `ruff check` passes. `git diff --stat` on the manager is empty.

## Traceability
cases 52 · tests 52 · Then lines 171 · unmatched: none · duplicates: none · marker mismatches: none. Card order equals file order. Each docstring starts with its card's ID and title, and each test sits under `# [claude] <ID>`. `# Then N` runs 1…N in all 52, matching each card's Then count. 45 `pass` cards have no marker. 7 are `strict=True`, each naming its card's bug: BUG-1192 ×5, BUG-1712 ×2. Both are in `docs/testing/bugs.md`.

## Limits of this round
- **The reference is one fix, mine.** The variants show what these tests catch around it. Another correct fix could expose a card that assumes something mine happens to do. Spec gap 1 (the order of the BUG-1192 check against the database refusals) is one such place, and no card combines two faults.
- **Pass-card Then lines were not each forced to fail.** They rest on reading, mutation and the variants.
- The 403 and detail variants share one helper, so each one hits both methods at once. I counted them once under each method.
- **Runs were not isolated from other agents.** No kill or catch shows a setup error.
- Not exercised: service or HTTP level, a real race, production data.

## Commands run
```
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/project_component_activity_manager.py tests/unit/managers/test_project_component_activity_manager.py --json <scratch>/mutants.json
  Mutants: 9 · killed 9 · timeout 0 · survived 0 · score 100%

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_project_component_activity_manager.py -q -p no:cacheprovider --cov=app.managers.project_component_activity_manager --cov-branch --cov-report=term-missing
  app\managers\project_component_activity_manager.py      23      0      2      0   100%
  45 passed, 7 xfailed, 15 warnings

.venv/Scripts/python.exe -m pytest tests/unit/managers/test_project_component_activity_manager.py -q -p no:cacheprovider --runxfail -rf --tb=line
  7 failed, 45 passed

same file, --tb=no                                   45 passed, 7 xfailed
same file, --tb=no -W error                          45 passed, 7 xfailed

trace.py                                             cards 52 · tests 52 · then-lines 171 · pass 45 · xfail 7 · reports: none
PCAMREF=fix ... -p pcamv --runxfail                  52 passed
PCAMREF=fix ... -p pcamv                             7 failed (XPASS strict), 45 passed
drive.py (45 variants, each with PCAMREF=fix --runxfail)   caught 43 · survived 2 · setup errors 0

.venv/Scripts/python.exe -m ruff check tests/unit/managers/test_project_component_activity_manager.py     All checks passed!
git diff --stat app/managers/project_component_activity_manager.py                                         (empty)
```
COVERAGE_FILE was private: `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr5v\.coverage`. All scratch files are in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr5v\`: `trace.py`, `pcamv.py`, `drive.py`, `variants.json`, `mutants.json`, `mutate.log`. The executor's `mgr5e\pcam_ref.py` was not used.

This report is the only file I wrote in the repo. I edited nothing under `app/`, and did not touch the spec, the cases file, the notes, the test file or `bugs.md`. No commit. No model server.

## Fix list
None. The module is done until BUG-1192 or BUG-1712 is fixed; the notes' "Notes for maintainers" say what to do with the markers then.
