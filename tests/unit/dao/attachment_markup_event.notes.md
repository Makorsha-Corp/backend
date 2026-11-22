# Execution notes — `app/dao/attachment_markup_event.py`

> Cases: `tests/unit/dao/attachment_markup_event.cases.md` (Revision 1, READY, 25 cases) · Tests: `tests/unit/dao/test_attachment_markup_event.py` · Source commit: e48a092
> Result: **25 tests for 25 cases — 22 passed · 3 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (12 statements, 0 branches). The non-strict AME-LA-08 may XPASS without turning the run red (not seen).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment_markup_event.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, written by hand from the cards. My audit script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\B\audit.py`) checked IDs, order, titles, rules, `# Then` numbers, markers, quoted literals and unused arguments (one false hit on CE-04's `event_type="", description=""`, which the test writes). LF only.

## How the tests are built
- **Nothing is patched.** The `created_at` default is bound at import; AME-CE-02 checks it against `clock_timestamp()` within 5 seconds under `SET LOCAL TIME ZONE 'Asia/Dhaka'` (first statement of the body).
- **Constants:** `dao`, `MISSING`, `T10`, `T11`, `T12` (naive).
- **Standing rows:** `w1`, `w2`, `u1`, `at1`, `at2`, `atd` through the autouse `standing_rows`, chained so ids rise in order.
- **Builders / Given steps:** `mk_entry(created_at=, **columns)` = "entry"; `mk_many_entries(count)` builds E1 … Ecount with `add_all` at `T10 + k minutes` and returns `newest`; `bump_e(db, X)` = bumpE; `seqscan(db)`.
- **Reading helpers:** `ids`, `reread`, `stored_json`, `is_sql_null`, `utc_clock` (read after the call), `stored_count` ("nothing written"), `events_of`.
- **Statement recorder:** as in the markup file; `sql()` is the one SELECT `FROM attachment_markup_events`; `order_part_of` cuts at `LIMIT`.
- **Database-error cards and rolled back:** as in the markup file.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| AME-LA-08 | no | Then 2, in every run (default, 3 plans, UTC, Asia/Dhaka) | `assert [699, 697, 698, 696] == [699, 698, 697, 696]`: the bumped lowest id moves last |
| AME-LA-09 | yes | Then 3, every run | `assert '.id' in ' attachment_markup_events.created_at DESC \n '` |
| AME-LA-10 | yes | Then 2, every run | `assert 200 == 201` |

**Proof plugin** `attxb_plug.py` (`-p attxb_plug`, `ATTXB_MODE`), replacing `list_for_attachment` in-process; nothing in `app/`.

| Mode | `list_for_attachment` | `--runxfail` | Markers on |
|---|---|---|---|
| `fix` (intended) | `created_at DESC, id DESC`, no cap | all 24 pass, so Then 4, 5 of LA-09 hold | LA-09, LA-10 `XPASS(strict)`, LA-08 XPASS |
| `wrong1` | `created_at DESC, id`, cap 200 | LA-08 Then 2 (`[2001, 1998, 1999, 2000]`); LA-09 Then 5 (`1 == 2`); LA-10 Then 2 | 21 passed, 3 xfailed |
| `wrong2` | `created_at DESC, description`, cap 200 | LA-08 Then 2 (`[2869, 2867, 2868, 2866]`); LA-09 Then 3; LA-10 Then 2 | 21 passed, 3 xfailed |
| `wrong3` | `created_at DESC, user_id DESC, id`, cap 200 | LA-08 Then 2 (`[3737, 3734, 3735, 3736]`); LA-10 Then 2; **LA-09 passes** | LA-09 `XPASS(strict)` |

So the non-strict card fails on its Then 2 under each wrong order, and no pass card depends on the order among ties.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

Prose only, a card weakness for the verifier (no test affected): AME-LA-09's Then 5 counts `DESC` words, so an order `created_at DESC, user_id DESC, id ASC` satisfies all five of its checks (`wrong3` above). AME-LA-08 still catches that order. A check that the text after `.id` starts with ` DESC` would close it.

## Spec gaps of the cases file, checked
None names a guessed path or column; `app.models.attachment_markup_event` and every column the cards use exist as written. Gap 1 (`clock_timestamp()` and 5 s instead of `now()` and 1 s) is how CE-02 is written.

## Coverage gaps
None — 100% line and branch coverage. Run with a private `COVERAGE_FILE`.

## Factories added
None.

## Stability
5 default runs, 5 forced plans (as in `attachment_markup.notes.md`) and the database time zones `UTC` and `Asia/Dhaka` (default `America/New_York`): each `21 passed, 3 xfailed`. AME-CE-02 compares with the real clock: 3000 repeats under the default time zone and 3000 under `UTC` (`attxb_repeat.py`, `ATTXB_REPEAT=3000`): all passed. 20 repeats of every test: nothing red. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1436 is fixed, LA-09 turns the run red; when BUG-1437 is fixed, LA-10 does: remove their markers (and LA-08's with BUG-1436).
- With BUG-1437's fix the `limit` parameter goes (deferred card list); AME-LA-11 keeps passing.

## Revision history
- **Revision 1 of the cases (attachment_markup_event.verify.md, case-missing findings):** added AME-LA-14 (pass). Patched in place, no other test changed. 3 default runs, 5 forced plans (as above) and the database time zones `UTC` and `Asia/Dhaka`, `ruff check` passed, coverage with a private `COVERAGE_FILE`, LF only. Card audit (my own `audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R`): every ID once, in card order, `# Then 1..N` per card, markers as the Expect lines. Reference plugin `attxr_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R` (`-p attxr_plug`, `ATTXR_MODE=ref`, in-process, nothing in `app/`; covers the seven revised modules): with `--runxfail` all 371 tests of the seven files pass, so the lines past every failure point hold. The verifier's named variants, rebuilt in the same plugin (`ATTXR_MODE=<variant>`, the reference with one change, `--runxfail`, default plan; each asserted applied): `la_ws_le` → LA-14. No other test failed under any of them.
