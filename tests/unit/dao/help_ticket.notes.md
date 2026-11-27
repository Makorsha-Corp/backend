# Execution notes — `app/dao/help_ticket.py`

> Cases: `tests/unit/dao/help_ticket.cases.md` (Revision 3, 2026-11-26, READY, 122 cases) · Tests: `tests/unit/dao/test_help_ticket.py` · Source commit: 41d5ac1
> Result: **122 tests for 122 cases — 112 passed · 10 xfailed · 0 xpassed · 0 discrepancies · 0 errors** — branch coverage 100% line and branch (55 statements, 16 branches). The four non-strict cards (HLP-LW-17, LP-20, LW-27, LP-26) xfailed in every run; an XPASS would not turn the run red.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_help_ticket.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, written by hand from the cards. An audit script (`audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\D`, written for this run) checked: each ID exactly once and in card order, the title in the docstring, `# Then 1..N` matching the card's Then count, marker strictness and bug matching the Expect line, the quoted literals of the Given lines present in the test or its builders. LF only.

## How the tests are built
- **Patched:** only in `CW` cards, `clock(L, U)`: `app.dao.help_ticket.datetime` becomes a `datetime` subclass whose `now()` returns L; `app.dao.help_ticket.utcnow` (`create=True`, the module does not import it today) and `app.utils.time.utcnow` return U. CW cards without a clock line run under `default_clock()` = clock(2026-06-01 12:00, 2026-06-01 12:00).
- **Constants:** `dao`, `MISSING`; the xfail reasons `BUG_1441`, `BUG_1442`, `BUG_1443` (bug id and title).
- **Standing rows:** `TAG` (a fixture, `uuid.uuid4().hex[:8]` per test), `w1` ("Gamma TAG"), `w2` ("Delta TAG"), `u1` ("Rahim"), `u2` ("Karim"), in that order, through the autouse `standing_rows`.
- **Builders:** `mk_ticket(ticket_number, **columns)` = "ticket" (status and type left to the model defaults `"pending"` / `"support"`; a card's `type "feedback"` is passed as `type="feedback"`); `mk_many_tickets(count)` = the `add_all` Givens (returns E1 … Ecount); `new_pending(db, w1, u1, number)` = the two code lines `P = HelpTicket(...)` / `db.add(P)`. `newer`, `bump_t` (bumpT), `seqscan` are the Conventions' code verbatim.
- **Reading helpers (no expected values inside):** `ids`, `tids`, `own(result, own_ids)` (OWN = the ids the Given made), `reread` (expire_all, then SELECT by id), `now_db`, `w1_count`, `ws_counts` (W1 and W2 counts, "nothing written").
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener around the When only. `selects()`, `written()`; `sql()` = the one SELECT naming `help_tickets` (fails loudly unless exactly one); `order_part_of(sql)`.
- **NoType (2026-11-26):** a module-level `class NoType(pydantic.BaseModel)` with `title`, `description`, `category=None`, as Conventions define it (HLP-CW-11). `HelpTicketCreate.model_construct(...)` is written in the tests as the cards give it (CW-10, CW-12, CW-13); pydantic emits a `PydanticSerializationUnexpectedValue` UserWarning on dump for these, which Conventions call harmless — warnings are not turned into errors.
- **Database-error cards:** the When is `with pytest.raises(E) as exc:` around `with db.begin_nested():`; the Then lines assert on `exc.value` afterwards.
- **rolled back (CW-08):** `mock.patch.object(db, "commit", wraps=db.commit)` as the spy; `sp = db.begin_nested()` directly before the call; Then 3 is `sp.rollback()` then the count.
- **Shared table:** every platform card searches for TAG (or a text holding TAG) and compares only its own tickets through `own(...)`; LP-04, LP-05, LP-10 use `limit=1000` as designed. `help_tickets` held 0 committed rows when checked.
- **One-query cards (HLP-GB-01, GW-01, LW-21):** the ids passed to the When (`A.id`, `W1.id`) are read into locals just before the Given's `db.expire_all()` and passed from there. Written literally, `A.id` / `W1.id` of an expired instance reload the row inside the recorder (3 and 2 SELECTs seen), which is the test's own SQL, not the DAO's. No expected value changed; recorded as a card note below.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| HLP-CW-03 | yes | Then 2, every run | `assert 'HELP-2027-001' == 'HELP-2026-001'` |
| HLP-LW-17 | no | Then 2, every run and plan | `assert [6003, 6001, 6002, 6000] == [6003, 6002, 6001, 6000]` |
| HLP-LW-18 | yes | Then 3, every run | `assert '.id' in ' help_tickets.created_at DESC \n '` |
| HLP-LP-11 | yes | Then 2 | `assert [6033, 6034] == [6033]` (`_` matched "axb") |
| HLP-LP-12 | yes | Then 2 | `assert [6035, 6036] == [6035]` (`%` matched "50 x") |
| HLP-LP-13 | yes | Then 1 | `assert [6038] == [6037]` ("ab" matched, "a\b" not — Spec gap 2 as the card says) |
| HLP-LP-20 | no | Then 2, every run and plan | `assert [6250, 6248, 6249, 6247] == [6250, 6249, 6248, 6247]` |
| HLP-LP-21 | yes | Then 3, every run | `assert '.id' in ' help_tickets.created_at DESC \n '` |
| HLP-LW-27 | no | Then 1 (2026-11-26 run) | `assert [506485, …, 506484, 506483] == [506485, …, 506483, 506482]` |
| HLP-LP-26 | no | Then 1 (2026-11-26 run) | `assert [506777, …, 506775, 506776] == [506777, …, 506775, 506774]` |

2026-11-26 `--runxfail` (Revision 2): all ten fail on the Then line their card names, on the value the card describes (CW-03 `HELP-2027-001`; LW-17/LP-20 Then 2 and LW-27/LP-26 Then 1 on row order; LW-18/LP-21 Then 3 `'.id' in order_part`; LP-11/LP-12 Then 2 with the decoy also returned; LP-13 Then 1 with "ab" returned). Result: `10 failed, 104 passed`. The 22 new cards and 5 revised cards are all `pass` cards, so no new xfail.

**Proof of the lines past the failure point.** Plugin `htd_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\D` (`-p htd_plug`, `PYTHONPATH` set to that folder), which replaces `list_by_workspace`, `list_platform` and `create_with_user` in-process; nothing in `app/`. `HTD_MODE=fix` (intended: `created_at DESC, id DESC`; `%`, `_`, `\` escaped with `ESCAPE '\'`; year from `app.utils.time.utcnow()`): with `--runxfail` **83 passed**, so every later Then of the eight cards holds. With the markers on: `6 failed (XPASS strict), 75 passed, 2 xpassed`.

**Explicit wrong orders** (`HTD_MODE=order`, `HTD_ORDER=<secondary>`, today's search and year), `--runxfail`:

| Secondary order after `created_at DESC` | Non-strict cards | Pass cards that fail |
|---|---|---|
| `id` (ascending) | LW-17, LP-20 fail on Then 2 (`[10599, 10596, 10597, 10598]`) | none |
| `title` | LW-17, LP-20 fail on Then 2 | none |
| `ticket_number` | LW-17, LP-20 fail on Then 2 | none |
| `status` | LW-17, LP-20 fail on Then 2 | none |
| `description` | LW-17, LP-20 fail on Then 2 | none |
| `workspace_id, id` | LW-17, LP-20 fail on Then 2 | none |
| `id DESC, title` (control) | LW-17, LP-20, LW-18, LP-21 pass | none |

So both non-strict cards can fail on their Then 2, and no pass card depends on the order among ties.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

Card note, no test affected (for the case designer): HLP-GB-01, GW-01 and LW-21 put `db.expire_all()` in the Given and then use `A.id` / `W1.id` in the When; read literally, those attribute reads reload the expired rows inside the recorder and Then "len(selects) == 1" counts them. The tests read the ids before the `expire_all()` (see How the tests are built). A future revision could write the When with ids saved in the Given.

## Spec gaps of the cases file, checked
| # | Assumption | Held? |
|---|---|---|
| 1 | Creator name = the name given to `make_profile(name=…)` | Yes: both platform reads select `Profile.name` (`profiles.name`). |
| 2 | An unescaped `\` escapes the next letter today | Yes: LP-13 fails on Then 1, "ab" matched. |
| 3 | Committed tickets of other runs could crowd a page | `help_tickets` had 0 committed rows; LP-04/05/10 use `limit=1000` as designed. |
| 4 | `created_at` and `updated_at` both equal `now()` at insert | Yes (CW-01 Then 6, in every run and 3000 repeats). |

Guessed paths: none in this module's Spec gaps; `HelpTicket`, `HelpTicketCreate`, `help_ticket_dao` are where the Conventions say.

## Coverage gaps
None — 100% line and branch coverage (55 statements, 16 branches; 2026-11-26 run, `--cov=app.dao.help_ticket --cov-branch`). The new `ticket_type` branches of both lists and the `hasattr(ticket_type, "value")` branch of `create_with_user` are hit both ways (CW-09 enum → `.value`; CW-10, CW-13 plain string; CW-11 no field → default `"support"`).

Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs, each `75 passed, 8 xfailed`. 5 forced plans through `PGOPTIONS` (`enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off), each `75 passed, 8 xfailed`. Database time zone `UTC` and `Asia/Dhaka` (`PGOPTIONS=-c timezone=…`; the default is `America/New_York`): each `75 passed, 8 xfailed`. The coverage run the same. Real-clock card HLP-CW-01 (`created_at == now()`) with CW-02, CW-07, CW-08 repeated 3000 times each in one process (`htd_repeat.py`, same folder, `HTD_REPEAT=3000`): REPEAT_CLOCK. The whole file 20 times in one process: REPEAT_FILE. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1442 is fixed, LW-18 and LP-21 turn the run red: remove the four BUG-1442 markers. Never read an LW-17 / LP-20 XPASS as the bug being gone; LW-18 and LP-21 are the proof.
- When BUG-1443 is fixed, LP-11, LP-12, LP-13 XPASS (strict): remove their markers. When BUG-1441 is fixed, CW-03 XPASSes; its `create=True` patch of `app.dao.help_ticket.utcnow` then patches the real import.
- The clock patch replaces the module's `datetime` name; a fix that calls `datetime.now(timezone.utc)` would get L from the subclass and keep CW-03 red, which is right (the card wants U's year).
- `create_with_user` R3 (BUG-1440, two concurrent creates) has no unit card; it is deferred to an integration test.

## Revision history
- **Revision 1 of the cases (help_ticket.verify.md, case-missing findings):** added HLP-GN-11, GB-06, LW-23 … LW-26, LP-25 (pass) and LW-27, LP-26 (xfail BUG-1442, non-strict); HLP-GN-10 and GP-06 gained an unflushed edit (B = ticket `HELP-2025-001` / `HELP-2026-003`, `B.title = "Edited"`) and the two `pending:` lines `B in db.dirty`, `len(db.dirty) == 1` as Then 4, 5; `statement:` and `nothing written:` are now Then 6, 7. Their test names follow the new titles. With `--runxfail` LW-27 and LP-26 fail on Then 1 (row order). The platform card LP-25 reads only its own ticket (`own(...)`, `search=TAG`); LP-26 searches `TAG`, which only this test's workspaces carry. Patched in place, no other test changed. 3 default runs, 5 forced plans (as above) and the database time zones `UTC` and `Asia/Dhaka`, `ruff check` passed, coverage with a private `COVERAGE_FILE`, LF only. Card audit (my own `audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R`): every ID once, in card order, `# Then 1..N` per card, markers as the Expect lines. Reference plugin `attxr_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\R` (`-p attxr_plug`, `ATTXR_MODE=ref`, in-process, nothing in `app/`; covers the seven revised modules): with `--runxfail` all 371 tests of the seven files pass, so the lines past every failure point hold. The verifier's named variants, rebuilt in the same plugin (`ATTXR_MODE=<variant>`, the reference with one change, `--runxfail`, default plan; each asserted applied): `lws_txt_like` → LW-23; `lws_txt_strip` → LW-24; `lws_txt_trimcol` → LW-25; `lp_status_truthy` → LP-25; `gn_ws_le` → GN-11; `lw_ws_le` → LW-26; `gn_w_expire` → GN-10 Then 4; `gp_w_expire` → GP-06 Then 4; `gb_inner_join` → GB-06 Then 1; `lw_ord_title_asc` → LW-27; `lp_ord_title_asc` → LP-26. No other test failed under any of them.
- **2026-11-26 — Revision 2 of the cases (spec revision 2026-11-26: status `pending` | `opened` | `closed`, new `type` column, `ticket_type` filter).** Source commit 41d5ac1.
  - *Revised cards, tests rewritten:* HLP-CW-01 (now 10 Then lines: `type(result.status) is str`, `status == "pending"`, `type(result.type) is str`, `type == "support"` on the return and the re-read; renamed to the new title); HLP-LW-05 (`status="PENDING"`, renamed `…status_pending_in_capitals…`); HLP-LW-19 and HLP-LP-22 (filter `"open"` → `"pending"`). The fixture comment for "ticket" now names the defaults `"pending"` / `"support"`; the builder itself did not change (it never set `status`).
  - *New tests:* HLP-GN-12; HLP-CW-09 … CW-13; HLP-LW-28 … LW-37; HLP-LP-27 … LP-32 — all pass as designed. New helper `NoType` and the `pydantic` import. Every other test unchanged; no ID retired.
  - *Checks:* card audit script (inline, against the cases file): all 114 IDs once and in card order, `# Then N` count equal to the card's Then count for every card. 3 default runs, each `104 passed, 10 xfailed`. `--runxfail`: 10 failed on their named Then lines (table above). `ruff check`: all checks passed. LF only.
  - *Discrepancies:* none. Note for the case designer (not a discrepancy): the stored-type card HLP-LW-34 and CW-12 / CW-13 rely on `type` being `String(16)` (`app/models/help_ticket.py`), which held.
- **2026-11-26 — Revision 3 of the cases (verify round 2026-11-26, R-7, R-8; fill-gaps G1 → R1d).** Added, in card order, HLP-CW-14, CW-15, LW-38, LW-39, LP-33 … LP-36 (all `pass`) and the Conventions helper `WithStatus` (module-level `pydantic.BaseModel` with `title`, `description`, `category=None`, `status: str`). CW-14 runs under `default_clock()` with the statement recorder around the call and `pytest.raises(TypeError)` without a savepoint, as the card says; the `nothing written` snapshot is taken before the call. No existing test changed. Result: `112 passed, 10 xfailed`; coverage 100% line and branch (55 statements, 16 branches). `--runxfail`: `10 failed, 112 passed`, the same ten cards on the same Then lines and values as in the Revision 2 table. Card audit: 122 IDs once, in card order, `# Then N` counts match. `ruff check` passed. Discrepancies: none.
