# Verification — `app/services/access_control_service.py`

> **Verdict:** PASS (round 2, 2026-11-06; round 1 was NEEDS WORK, see below)
> Tests: 35 passed · 26 xfailed (reproduced ✅) · coverage 100% branch (48 statements, 8 branches)
> Mutation: 22 mutants · 22 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Hand variants: 45 (19 on today's code, 26 on a reference fix of BUG-1875 / BUG-2255) · 41 killed · 4 survived (all `case-missing`, 2 findings)
> Source commit: e48a092 · Cases revision: 4

## Summary
The tests are faithful to the cards: traceability is clean, every xfail fails on its card's Then line, three plain runs give the same result, and every `mutate.py` mutant is killed. The tests also hold up well against hand-made faulty fixes for BUG-1875: an owner check that is too loose is caught (owner of another workspace, inactive or suspended or invited owner, `Owner` or `owner `, `owner_user_id` alone, any active member). So is a check that is too strict, one placed after the write or the lookup, one missing on update or delete, a wrong error type or message, and BUG-2255 filtering after paging. Three wrong fixes still pass all 61 cards, so the case designer must add cards before the fix lands. First, the owner check is made inside the `try` of `update_control` / `delete_control`, so a refusal rolls back the caller's pending changes. Second, `user_id` gets a default of `None` that skips the check. The spec rules out both (gap 2 and gap 3).

## Findings
| # | Kind | Case / line | What is wrong | Evidence | Fix by |
|---|---|---|---|---|---|
| 1 | case-missing | `update_control` R1, `delete_control` R1 (spec gap 3: "raised before the `try` … no rollback") | ACS-C-23 checks that a refusal does not commit or roll back and leaves a pending row in place, but only for `create_control`. U-10 … U-12 and D-07 … D-09 check `not db.dirty` / `not db.deleted` and "nothing written", and a rollback satisfies those too. | Hand variants `check-inside-try-update` and `check-inside-try-delete` (owner check as the first line inside the `try`, so the refusal runs `db.rollback()`): 61 passed with `--runxfail`. | **case designer**: add the C-23 shape for update and delete (spies; pending P; `cm.call_count == 0`, `rb.call_count == 0`, `db.get(AccessControl, P_ID) is P`), strict xfail BUG-1875 |
| 2 | case-missing | ACS-C-24 (spec Facts gap 2: `user_id` is a **required** keyword-only parameter; "an optional caller id would let a forgotten argument skip the owner check") | C-24 checks only `.kind == Parameter.KEYWORD_ONLY`, not that the parameter is required. The pass cards always pass `user_id` (through `call_uid`), so a fix that gives `user_id=None` a default and skips the check is not caught. | Hand variants `user_id-optional-skips-check` (create) and `user_id-optional-skips-check-update`: 61 passed with `--runxfail`. | **case designer**: add to C-24, for each writer, `sigs[...]["user_id"].default is Parameter.empty` (or a card calling without `user_id` that expects `TypeError`) |

No fidelity findings: every Then line of every card is asserted as written. The order of `with` blocks and spies matches Conventions. No mocks go beyond the named failure patches. No `try`/`except` sits around assertions.

## Surviving mutants
None (22 of 22 killed; each kill is a real `1 failed`, not an error).

## Hand variants
Run with my own runner `hv.py` on a copy of the backend (`wpsvcv\A\hv_acs\`). For a variant on today's code: plain run with `-m "not xfail"`. For a variant on a reference fix: my own BUG-1875 / BUG-2255 fix (`v_acs.py` `FIXED`), run with `--runxfail`. The reference fix itself gives **61 passed**.

| Variant | Run | Result | Killed by |
|---|---|---|---|
| no rollback in create / update / delete `except` | plain | KILLED ×3 | C-03, C-04 / U-07 / D-05 |
| stray `commit` / `rollback` in `get_controls` | plain | KILLED ×2 | L-11, L-12 / L-01 … |
| stray `commit` / `rollback` in `get_by_id` | plain | KILLED ×2 | G-06 / G-01, G-06 |
| commit or rollback on update / delete not-found path | plain | KILLED ×4 | U-04 / D-02 |
| flush instead of commit (create / update / delete) | plain | KILLED ×3 | C-01 … / U-01 … / D-01, D-05 |
| no re-read (create / update) | plain | KILLED ×2 | C-05 / U-08 (only the failing-refresh cards see it, see note) |
| lookup without workspace (update / delete / get_by_id) | plain | KILLED ×3 | U-04, U-05 / D-02, D-03 / G-02, G-03 |
| BASE fixed | runxfail | 61 passed | — |
| owner of any workspace counts | runxfail | KILLED | C-19, C-20, U-12, D-09 |
| status ignored (inactive owner) | runxfail | KILLED | C-15 … C-18 |
| role compared case- and space-insensitive | runxfail | KILLED | C-13, C-14 |
| status compared case-insensitive | runxfail | KILLED | C-18 |
| `owner_user_id` also grants | runxfail | KILLED | C-21 |
| `owner_user_id` only | runxfail | KILLED | C-01 … (too strict for UO), C-21 |
| any active member allowed | runxfail | KILLED | C-07 … |
| too strict: refuse everyone / require `owner_user_id` too | runxfail | KILLED ×2 | C-01, U-01, D-01 … |
| check inside `try` (create) / after write (create) | runxfail | KILLED ×2 | C-23 |
| check after lookup or after write (update / delete) | runxfail | KILLED ×4 | U-11 / D-08 |
| check missing on update / delete | runxfail | KILLED ×2 | U-10 … U-12 / D-07 … D-09 |
| 404 / 400 / sibling message instead of 403 DENY | runxfail | KILLED ×3 | every refusal card |
| `user_id` positional-or-keyword | runxfail | KILLED | C-24 |
| BUG-2255 fixed by filtering after paging | runxfail | KILLED | L-03 |
| **check inside `try` (update / delete)** | runxfail | **SURVIVED ×2** | — Finding 1 |
| **`user_id=None` default skips the check (create / update)** | runxfail | **SURVIVED ×2** | — Finding 2 |

Note (no action): C-01 Then 3 and U-01 Then 2 ("returned re-read") alone do not notice a missing `db.refresh` under the `db` fixture: there the commit releases a savepoint and leaves the attributes loaded. The re-read is pinned by C-05 / U-08 (failing refresh) instead, so nothing is uncovered.

## Traceability
cases 61 · tests 61 · unmatched: none · marker mismatches: none. 26 strict xfail. Each reason names its BUG (BUG-1875 ×24, BUG-2255 ×2), and both IDs are in `bugs.md` (open). Checked with `wpsvcv\A\trace.py` (AST).

## Commands run
```
COVERAGE_FILE=wpsvcv/.cov.access_control_service.1 .venv/Scripts/python.exe -m pytest tests/unit/services/test_access_control_service.py -q -p no:cacheprovider -o addopts= --cov=app.services.access_control_service --cov-branch --cov-report=term-missing
  app\services\access_control_service.py 48 0 8 0 100%   ·   35 passed, 26 xfailed
PYTHONPATH=wpsvcv/A .venv/Scripts/python.exe -m pytest tests/unit/services/test_access_control_service.py -q -p no:cacheprovider -o addopts= -p thenwhere --runxfail -rf
  26 failed, 35 passed. Every failure is on its card's line: C-07 … C-23, U-10 … U-12, D-07 … D-09 Then 1 TypeError (unexpected keyword 'user_id'); C-24 Then 1 KeyError 'user_id'; L-02 Then 2 ({AP, AF} vs {AF}); L-03 Then 1 (2 == 1)
plain runs 2 and 3: 35 passed, 26 xfailed (both); ruff check: clean
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/services/access_control_service.py tests/unit/services/test_access_control_service.py --json wpsvcv/mut_access_control_service.json
  Mutants: 22 · killed 22 · timeout 0 · survived 0 · score 100%
.venv/Scripts/python.exe wpsvcv/A/hv.py wpsvcv/A/v_acs.py wpsvcv/A/hv_acs   (results: wpsvcv/A/hv_acs.txt, hv_acs2.txt)
```
(`wpsvcv` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wpsvcv`)

## For the future notes
- permissions (`docs/future/permissions.md`): the "Gap (access_control DAO spec FU-1 (c), (d))" line still calls the role-and-type filter an unlogged gap. It is now BUG-2255. Also worth recording there: for BUG-1875, "workspace owner" means an active `owner` membership, not `workspaces.owner_user_id` (ACS-C-21 pins this).

## Round 2 — 2026-11-06
Cases revision 5 · tests 63 (35 passed / 28 xfail).

**What changed** (diffed against the round-1 copy of the test file): new ACS-U-13 and ACS-D-10 (the C-23 shape for update and delete, from Finding 1). ACS-C-24 gained Then 4–6, `user_id` has no default on each writer (Finding 2). The header now says revision 5. No other test changed.

**Traceability:** 63 cards, 63 tests, 28 strict xfails, no mismatches (`wpsvcv\A\trace.py`).

**Fidelity:** U-13, D-10 and C-24 were read against their cards. Every Then line is asserted as written, in order. The `pytest.raises` block sits inside the spies, as the cards say. P is added after the commit point, and the snapshot of A is taken at the commit point. No findings.

**Runs** (private `COVERAGE_FILE` under `wpsvcv\A\r2\`):
```
plain ×3: 35 passed, 28 xfailed (5.92s, 6.54s, 6.32s): stable
--cov --cov-branch: app\services\access_control_service.py 48 0 8 0 100%; 35 passed, 28 xfailed
--runxfail -rf: 28 failed, 35 passed
  C-24 Then 1 KeyError: 'user_id' · U-13 Then 1 TypeError (no user_id) · D-10 Then 1 TypeError: each on its card's Fails-today line
```

**Round-1 survivors, re-run** (`wpsvcv\A\hv.py` on the reference fix, `--runxfail`, fresh copy `hv_acs_r2`; the reference fix alone gives 63 passed):
| Variant | Result | Killed by |
|---|---|---|
| check-inside-try-update | KILLED | ACS-U-13 |
| check-inside-try-delete | KILLED | ACS-D-10 |
| user_id-optional-skips-check (create) | KILLED | ACS-C-24 |
| user_id-optional-skips-check-update | KILLED | ACS-C-24 |
| check-inside-try-create (control) | KILLED | ACS-C-23 |

No `mutate.py` run: round 1 had 22 of 22 killed, and no source line changed.

**Current verdict:** PASS — both round-1 findings are closed by cards that kill their variants; the tests are faithful and stable.
