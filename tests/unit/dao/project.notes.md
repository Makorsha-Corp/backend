# Execution notes — `app/dao/project.py`

> Cases: `tests/unit/dao/project.cases.md` (Revision 1, READY, 48 cases) · Tests: `tests/unit/dao/test_project.py` · Source commit: e48a092
> Result: **48 tests for 48 cases — 34 passed · 14 xfail · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (11 statements, 0 branches). Non-strict cards may XPASS without turning the run red: default `34 passed, 14 xfailed`; forced plans 1 and 2 `34 passed, 13 xfailed, 1 xpassed` (PRJ-GF-15).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\C\gen.py`), so values are the card's own text; the header (fixtures, helpers) was written by hand from the Conventions. A separate audit script (`audit.py`, same folder) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal and number present (the one it flags, `"Project {k:03d}"`, sits in the `mk_many` builder), marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched.**
- **Constants:** `dao`, `MISSING`.
- **Standing rows:** `w1`, `w2`, `f1`, `f2`, `fi`, `fd`, `f9`, each fixture depending on the one listed before it so the ids rise in the Conventions' order, all through the autouse `standing_rows`. FD is `is_deleted=True` with `is_active` left at its default True; FI is `is_active=False`.
- **Builders:** `mk_project(name=..., **columns)` = "project" (status left to its default `PLANNING`); "deleted" = `is_deleted=True, is_active=False`; `mk_many(count)` = the 104 projects built with `add_all`. `set_status`, `bump` (bumpP) and `seqscan` are the Conventions' SQL steps verbatim, followed by `db.expire_all()` where the Conventions say so.
- **Reading helpers (no expected values inside):** `ids(result)`; `snap(db, row)` = every column by a Core select, for "unchanged" (snapshot after the last Given line); `stored_count(db)` = the pair of `projects` and `factories` counts, "nothing written".
- **Database-error cards:** `with pytest.raises(DataError) as exc:` around `with db.begin_nested():`; the `raises:` Then line asserts on `exc.value` after the block.
- **Statement recorder:** `StatementRecorder(db)` around the When only; `rec.sql()` = the one SELECT from `projects`, `order_part_of(sql)` = after the first `ORDER BY`, before `LIMIT`; `rec.written()` = INSERT / UPDATE / DELETE.
- **Row letters** of the cards are lower case in the code. A Given row no later line names is built without a variable (F841).

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| PRJ-GF-07 | yes | Then 2, every run | `assert {255775, 255776} == {255775}` |
| PRJ-GF-08 | yes | Then 1, every run | `assert 2 == 1` |
| PRJ-GF-10 | yes | Then 1, every run | `assert [<Project …>] == []` |
| PRJ-GF-14 | no | Then 2, every plain run | `assert [255786, 255787, 255788] == [255787, 255788, 255786]`: "Zulu" first |
| PRJ-GF-15 | no | Then 2, default runs and plans 3–5; XPASS on plans 1, 2 | `assert [255790, …, 255789] == [255789, …, 255792]`: the bumped lowest id last |
| PRJ-GF-16 | no | Then 2, every plain run | `assert [255795] == [255794]`: "alpha" second |
| PRJ-GF-17 | yes | Then 2, every run | `assert 'ORDER BY' in 'SELECT projects.id … LIMIT %(param_1)s OFFSET %(param_2)s'` |
| PRJ-GS-05 | yes | Then 2, every run | `assert {256027, 256028} == {256027}` |
| PRJ-GS-07 | yes | Then 2, every run | `assert {256030, 256031} == {256030}` |
| PRJ-GS-10 | no | Then 2, every plain run | `assert [256034, 256035, 256036] == [256035, 256036, 256034]` |
| PRJ-GS-11 | yes | Then 2, every run | `assert 'ORDER BY' in 'SELECT projects.id … LIMIT …'` |

Every card fails on the Then its "Fails today on" line names.

**Proof of the lines past the failure point.** Plugin `refc_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\C` (`-p refc_plug`, `REFC_MODE=...`), which replaces `DAOProject.get_by_factory` / `get_by_status` in-process; nothing in `app/`.

**The intended code** (`REFC_MODE=fix`: live projects only, joined to a live factory, `ORDER BY lower(name), id`): with `--runxfail` all 45 pass, so Then 3–6 of GF-17 and GS-11 hold. With the markers on, the seven strict cards are `XPASS(strict)` and the four non-strict cards XPASS.

**Explicit wrong orders, `--runxfail`** (filters as today, so GF-07, 08, 10, GS-05, 07 fail as above in every mode):

| Mode | Order | Order cards that fail | Pass cards that fail |
|---|---|---|---|
| `wrong1` | `lower(name), id DESC` | GF-15 on Then 2; GF-17, GS-11 on Then 6 | none |
| `wrong3` | `lower(name), description` | GF-15 on Then 2; GF-17, GS-11 on Then 4 | none |
| `wrong4` | `name DESC, id` | GF-14, 15, GS-10 on Then 2; GF-17, GS-11 on Then 6 | none |
| `wrong5` | `lower(name) DESC, id DESC` | GF-14, 15, GS-10 on Then 2; GF-17, GS-11 on Then 6 | none |
| `wrong6` | `id DESC` | GF-14, 15, 16, GS-10 on Then 2; GF-17, GS-11 on Then 3 | none |
| `wrong2` | `name, id` (case-sensitive) | none: GF-17 and GS-11 pass every line (`XPASS(strict)` with markers on) | none |

So every non-strict card can fail on its Then 2, and no pass card depends on the order. `wrong2` is the one order the cards cannot tell from the intended one; see Notes for maintainers.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
- **Gap 1 (`ProjectStatusEnum`'s module):** it is `app.models.enums.ProjectStatusEnum` (the DAO imports it from there). The guess did not need correcting: the cards pass the name `"PLANNING"` and set other statuses by SQL with a cast to `projectstatusenum`, which is the real database type; both work as the cards say.
- **Gap 2:** cards use `is_deleted True, is_active False` as given; nothing to check here.
- `Factory` is `app.models.factory.Factory`, columns `name`, `abbreviation`, `is_active`, `is_deleted` as the Conventions say.

## Coverage gaps
None — 100% line and branch coverage (`--cov=app.dao.project --cov-branch`, private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs, 5 forced plans and 2 time zones: `34 passed, 11 xfailed` in each, except plans 1 and 2 (`enable_seqscan=off`; that plus hash join and nested loop off) with `34 passed, 10 xfailed, 1 xpassed` (PRJ-GF-15, non-strict). The other plans: `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off. Time zones: `PGOPTIONS=-c timezone=UTC` and `-c timezone=Asia/Dhaka` (database default `America/New_York`). No card compares a real-clock stamp. 20 repeats of the whole file with `test_discussion.py` in one process: nothing red. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1444 is fixed, GF-17 and GS-11 turn the run red: remove the markers of GF-14, 15, 16, 17, GS-10, 11. BUG-1445: GF-07, 08, GS-05. BUG-1446: GF-10, GS-07.
- Never read a GF-14, 15, 16 or GS-10 XPASS as the bug being gone: GF-17 and GS-11 are the proof.
- **For the verifier (not a discrepancy):** the case-insensitive part of R4 is not pinned by any card on this database. Its collation is `English_United States.1252`, which already sorts "apple" < "Banana" < "Zulu" and "roof" next to "Roof" for a plain `ORDER BY name`; GF-17 / GS-11 only check that `name` comes before `.id` in the SQL text. A fix with `ORDER BY name, id` (`wrong2` above) passes every card here, and would order case-sensitively on a `C`-collation database.

## Revision history
- **Revision 1 of the cases (project.verify.md, case-missing findings):** added PRJ-GF-27, GS-20 (xfail BUG-1444, non-strict) and GS-21 (xfail BUG-1445, BUG-1444, non-strict). With `--runxfail` each fails on Then 1 in every run: GF-27 `[342994, …, 342997] == [342997, …, 342995]` (row order), GS-20 likewise, GS-21 `assert [343003] == [343004]` (the deleted project fills the first place). They never XPASSed in any run or plan. Closes the case-insensitivity weak spot noted below: a case-sensitive `name, id` now fails GF-27 / GS-20. Patched in place, no other test changed. 3 default runs, 5 forced plans (as above) and the database time zones `UTC` and `Asia/Dhaka`, `ruff check` passed, coverage with a private `COVERAGE_FILE`, LF only. Card audit (my own `audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R`): every ID once, in card order, `# Then 1..N` per card, markers as the Expect lines. Reference plugin `attxr_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R` (`-p attxr_plug`, `ATTXR_MODE=ref`, in-process, nothing in `app/`; covers the seven revised modules): with `--runxfail` all 371 tests of the seven files pass, so the lines past every failure point hold. The verifier's named variants, rebuilt in the same plugin (`ATTXR_MODE=<variant>`, the reference with one change, `--runxfail`, default plan; each asserted applied): `gf_ord_case_sensitive` → GF-27; `gs_ord_case_sensitive` → GS-20; `gs_deleted_after_page` → GS-21 Then 1 (`[342327] == [342328]`). No other test failed under any of them.
