# Execution notes — `app/dao/discussion.py`

> Cases: `tests/unit/dao/discussion.cases.md` (Revision 1, READY, 52 cases) · Tests: `tests/unit/dao/test_discussion.py` · Source commit: e48a092
> Result: **52 tests for 52 cases — 46 passed · 6 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (16 statements, 0 branches). Non-strict GE-19, GE-20, GE-24 may XPASS under forced plan 1 (`enable_seqscan=off`) without turning the run red.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_discussion.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The card bodies were transcribed by a throwaway parser of the cases file (not kept in the repo; `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\C\gen.py`), so values are the card's own text; the header (fixtures, helpers) and the three special cards (DSC-CR-01 Then 6, CR-10) were written by hand. A separate audit script (`audit.py`, same folder) checked: each ID exactly once and in card order, title and rules in the docstring, `# Then 1..N` matching the card's Then count, every quoted literal and number of the Given, When and Then lines present (the two it flags, `"Post {k}"` of GE-09 and GE-10, sit in the `mk_many` builder), marker and bug matching the Expect line, no unused argument, no fixture used without being an argument. LF only.

## How the tests are built
- **Nothing is patched.** `created_at` is the database's `now()`; the one spy is `patch.object(db, "commit", wraps=db.commit)` of DSC-CR-10 ("rolled back").
- **Constants:** `dao`, `MISSING`.
- **Standing rows:** `w1`, `w2`, `u1` (`make_workspace`, `make_profile`), chained so the ids rise in the Conventions' order, through the autouse `standing_rows`.
- **Builders:** `mk_msg(**columns)` = "msg"; "reply on X" = `mk_msg(parent_id=x.id, ...)`; `mk_many(count)` = the 51 roots built with `add_all`. `older(db, x, h)`, `bump(db, x)` (bumpD), `seqscan(db)` are the Conventions' SQL steps verbatim, each followed by `db.expire_all()` where the Conventions say so.
- **Named checks:** `items` / `total` are written as `result[0]` / `result[1]` inside each assertion, so a non-tuple result fails on the card's own Then line; `ids`, `reply_ids`, `reread` (expire, then SELECT by id), `now_db(db)` = NOW_DB, `stored_count(db)` = "nothing written", `count_with_entity(db, 501)` for the `count:` lines.
- **Database-error cards:** `with pytest.raises(E) as exc:` around `with db.begin_nested():`; the `raises:` Then lines assert on `exc.value` after the block.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener around the When only. `page_sql()` = the one SELECT with `LIMIT`; `reply_sql()` = the SELECT with `parent_id IN`, or `""` when none was sent (see DISCREPANCY-1); `sql()` = the one SELECT from `discussions` that is not a replies' load; `written()` = INSERT / UPDATE / DELETE.
- **Row letters** of the cards are lower case in the code. A Given row no later line names is built without a variable (F841).

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| DSC-GE-19 | no | Then 2, every plain run | `assert [267, 265, 266, 264] == [267, 264, 265, 266]`: the bumped lowest id moved last |
| DSC-GE-20 | no | Then 2, every plain run | `assert [269, 270, 271, 268] == [268, 269, 270, 271]` |
| DSC-GE-21 | yes | Then 3, every run | `assert '.id' in ' discussions.created_at ASC \n '` |
| DSC-GE-24 | no | Then 2, every plain run | `assert [275, 276, 274] == [274, 275, 276]` |
| DSC-GE-25 | no | Then 2, every plain run | `assert [278, 279, 280] == [279, 280, 278]`: physical order, as the card says |
| DSC-GE-26 | yes | Then 2, every run (the card's Fails line since Revision 1) | `assert 'parent_id IN' in ''` |

**Proof of the lines past the failure point.** Plugin `refc_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\C` (`-p refc_plug`, `REFC_MODE=...`), which replaces `DiscussionDAO.get_by_entity` in-process and sets the `replies` relationship's `order_by`; nothing in `app/`.

**The intended code** (`REFC_MODE=fix`: roots `created_at, id`; replies `selectinload` in the call, ordered `created_at, id`): with `--runxfail` all 48 pass, so Then 4 and 5 of GE-21 and Then 3 of GE-26 hold. With the markers on, GE-21 and GE-26 are `XPASS(strict)` and the four non-strict cards XPASS.

**Explicit wrong orders, `--runxfail`:**

| Mode | Roots order | Replies order | Cards that fail | Pass cards that fail |
|---|---|---|---|---|
| `wrong1` | `created_at, id DESC` | `id DESC` | GE-19, 20, 24, 25 on Then 2; GE-21 on Then 5; GE-26 on Then 2 | none |
| `wrong2` | `created_at, message` | `message` | GE-20, 24, 25 on Then 2; GE-21 on Then 3; GE-26 on Then 2 | none |
| `wrong3` | `created_at, message DESC` | `message DESC` | GE-19, 20, 24, 25 on Then 2; GE-21 on Then 3; GE-26 on Then 2 | none |
| `wrong4` | `created_at, user_id, id DESC` | `created_at, id DESC` | GE-19, 20, 24, 25 on Then 2; GE-21 on Then 5; GE-26 on Then 2 | none |
| `wrong6` | `created_at, entity_type, id DESC` | `created_at, message, id` | GE-19, 20, 24, 25 on Then 2; GE-21 on Then 5; GE-26 on Then 2 | none |
| `wrong5` (primary key reversed, a mutation, not a tie order) | `created_at DESC, id` | `created_at DESC, id` | the six xfail cards, and GE-13, 17, 18, 22, 23 | GE-13, 17, 18, 22, 23 — as they should |

So every non-strict card can fail on its Then 2, and no pass card depends on the order among ties.

## Discrepancies
None open. DISCREPANCY-1 below was closed by cases Revision 1 (the card now says Then 2 and names BUG-1490); kept for the record.

| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 | DSC-GE-26 | xfail BUG-1439 strict, fails today on Then 3 (`"ORDER BY" in reply_sql`) | strict xfail, but fails on **Then 2** (`"parent_id IN" in reply_sql`): no replies query is sent during the call at all | Recorded SQL of `get_by_entity`: `SELECT count(*) …`, the page `SELECT … ORDER BY discussions.created_at ASC LIMIT … OFFSET …`, `SELECT profiles … WHERE profiles.id IN (…)` (the author load) — nothing on `discussions.parent_id`. `replies` is `lazy="selectin"` on a self-referential relationship without `join_depth`, which SQLAlchemy does not eager-load; each root's replies load lazily, one query per root, when first read. | Spec premise wrong (Returns: "each with `replies` … loaded"; the code's docstring says "eager-loaded"). Filed as **BUG-1490** (new). The marker stays strict and its reason names BUG-1439 and BUG-1490. Back to the describer: R6 / Returns should name BUG-1490, and GE-26's "Fails today on" should read Then 2. |

The other reply cards (GE-01 Then 7, GE-24, GE-25, GE-27, GE-28) end as designed: their replies load lazily when the Then line reads them, by a query with no `ORDER BY`, so GE-24 and GE-25 still fail on Then 2 for BUG-1439.

No card was changed, no marker loosened, no expected value changed.

## Spec gaps of the cases file, checked
Spec gaps 1 and 2 of the cases file are about rules, not paths; nothing guessed. `Discussion` is `app.models.discussion.Discussion`; `created_at` is `timestamptz` in the database, so `created_at == NOW_DB` compares two aware values (verified under `America/New_York`, `UTC` and `Asia/Dhaka`).

## Coverage gaps
None — 100% line and branch coverage (`--cov=app.dao.discussion --cov-branch`, private `COVERAGE_FILE`).

## Factories added
None.

## Stability
5 default runs, 5 forced plans and 2 time zones, each `42 passed, 6 xfailed`. `PGOPTIONS` carried five forced plans (`enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off) and `-c timezone=UTC`, `-c timezone=Asia/Dhaka` (the database default is `America/New_York`). The cards that read the database clock (CR-01, GE-13, GE-17, GE-18, GE-22, GE-23) were repeated 500 times each in one process (`refc_rep.py`, `REFC_REPEAT=500`): 3000 passed. 20 repeats of the whole file with `test_project.py` in one process: nothing red (non-strict cards may XPASS there). `ruff check`: all checks passed (one `# noqa: RUF015` on GE-01 Then 7, the card's own expression).

## Notes for maintainers
- When BUG-1438 is fixed, GE-21 turns the run red: remove the markers of GE-19, 20, 21.
- When BUG-1439 **and** BUG-1490 are fixed, GE-26 turns the run red: remove the markers of GE-24, 25, 26. Fixing BUG-1439 alone (an `order_by` on the relationship) leaves GE-26 failing on Then 2.
- Never read a GE-19, 20, 24 or 25 XPASS as the bug being gone: GE-21 and GE-26 are the proof.

## Revision history
- **Revision 1 of the cases (discussion.verify.md, case-missing findings):** added DSC-GE-31, GE-32, GE-33, CR-11 (pass). DSC-GE-26: the card now names BUG-1439 and BUG-1490 and fails on Then 2, so DISCREPANCY-1 is closed; the marker reason no longer carries the DISCREPANCY note (it names BUG-1439 and BUG-1490) and the docstring's Rules line names both bugs. GE-26 still fails on Then 2: `assert 'parent_id IN' in ''`. Patched in place, no other test changed. 3 default runs, 5 forced plans (as above) and the database time zones `UTC` and `Asia/Dhaka`, `ruff check` passed, coverage with a private `COVERAGE_FILE`, LF only. Card audit (my own `audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R`): every ID once, in card order, `# Then 1..N` per card, markers as the Expect lines. Reference plugin `attxr_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R` (`-p attxr_plug`, `ATTXR_MODE=ref`, in-process, nothing in `app/`; covers the seven revised modules): with `--runxfail` all 371 tests of the seven files pass, so the lines past every failure point hold. The verifier's named variants, rebuilt in the same plugin (`ATTXR_MODE=<variant>`, the reference with one change, `--runxfail`, default plan; each asserted applied): `ge_ws_le` → GE-31; `ge_txt_strip` → GE-32; `gee_id_le` → GE-33; `cr_strip` → CR-11 (and CR-07). No other test failed under any of them.
