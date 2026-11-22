# Execution notes — `app/dao/waitlist.py`

> Cases: `tests/unit/dao/waitlist.cases.md` (Revision 1, READY, 52 cases) · Tests: `tests/unit/dao/test_waitlist.py` · Source commit: e48a092
> Result: **52 tests for 52 cases — 47 passed · 5 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (30 statements, 6 branches). The non-strict card LS-15 xfailed in every run (no XPASS seen).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_waitlist.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, in card order, with a `# Then N` comment before each numbered Then line. LF only.

## How the tests are built
- **Nothing is patched.** The two commit spies (CS-08, US-04) are `mock.patch.object(db, "commit", wraps=db.commit)`: still callable, records calls.
- **Constants:** `dao` (the singleton), `T1`, `T2`, `T3` (aware UTC).
- **`TAG` fixture:** `uuid.uuid4().hex[:10]`, one per test.
- **Shared table.** `waitlist_signups` has no workspace and other suites/forks write to it in their own (rolled-back) transactions. Every email carries the test's `TAG`, and every filtered card searches for it, so its result can only contain the test's own rows. The three "no filter" cards (LS-01, LS-08, LS-09) read `N0` with `read_n0(db)` inside the test's own transaction, at the card's Given line, and compare `total == N0 + 2` and `{A.id, B.id} <= idset(page)` with `limit=1000`, as designed. Uncommitted rows of concurrent runs are invisible (READ COMMITTED), and the pipeline never commits, so N0 cannot move between the read and the When. "Nothing written" (`stored_count`) is a count of the whole table taken in the same transaction, same reasoning.
- **Builders:** `mk_signup(email, **columns)` = "signup" (defaults `first_name "Zed"`, `last_name "Ray"`, `company_name "Acme"`, `source "landing"`, `ip_hash "h1"`; flushes); `mk_101(tag)` builds E1 … E101 with `add_all` and returns `newest` (ids E101 … E1).
- **Reading helpers (no expected values inside):** `ids`, `idset`; `reread(db, id)` = `expire_all()` then `db.get`; `snap(db, row)` = every column by a Core select (US-01's "unchanged except status" compares the two dicts without `status`); `count_where(db, sql, **params)` for CS-04 and CS-08's raw counts.
- **Statement recorder:** `before_cursor_execute` listener on the session's connection, around the When only. `recorder.sql()` = the one recorded SELECT on `waitlist_signups` with `LIMIT` (the page, not the count); `order_part_of(sql)`.
- **Database-error cards:** `with pytest.raises(...) as exc:` around `with db.begin_nested():`; that block is Then 1.
- Row letters of the cards are lower case in the code; a Given row no later line names has no variable.

## Spec gaps of the cases file, checked
| # | Assumed | Real | Effect |
|---|---|---|---|
| 1 | `app.models.waitlist.WaitlistSignup` | **`app.models.waitlist_signup.WaitlistSignup`** (same class, table `waitlist_signups`) | Imported from the real module; no card changed. The verifier corrected the Conventions line (kept in Revision 1). |
| 2 | `ILIKE` uses Postgres's default escape `\` | Held: the DAO passes no `escape=`, so `\d` matches a plain `d`. LS-06 fails on Then 2: `assert [286] == [285]` (B found, A not), as its Fails line says. | none |
| 3 | `N0` + `limit=1000` holds every row | Held: the table had few committed rows (ids in the low thousands come from sequence use, not rows). | none |

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| WLS-LS-04 | yes | Then 2, every run | `assert [281, 282] == [281]`: `_` matched `axb` too |
| WLS-LS-05 | yes | Then 2, every run | `assert [283, 284] == [283]`: `%` matched `pzzq` too |
| WLS-LS-06 | yes | Then 2, every run | `assert [286] == [285]`: the backslash escaped `d`; B found, A missed |
| WLS-LS-15 | no | Then 2, every run (5 default, 5 plans, 3 time zones, 2000 repeats) | `assert [288, 289, 287] == [289, 288, 287]`: physical order B, C, A (the updated A moved last) |
| WLS-LS-16 | yes | Then 4, every run | `assert '.id' in ' waitlist_signups.created_at DESC \n '` |

**Lines past the failure point.** Scratch plugin `wl_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\waitlist` (`-p wl_plug`, `PYTHONPATH` there), which replaces `list_signups` in-process; nothing in `app/`. `WL_MODE=fix` (search escaped with `\` and `escape="\\"`, `ORDER BY created_at DESC, id DESC`): with `--runxfail` **45 passed**, so every Then of the five cards holds under the intended code (LS-16 Then 5–7 included). With the markers on: 4 `XPASS(strict)` (LS-04, 05, 06, 16) and LS-15 xpassed.

**Explicit wrong orders (`WL_MODE=order:<name>`, `ORDER BY created_at DESC, <tie-break>`, `--runxfail`):**

| Tie-break | LS-15 | LS-16 | Pass cards that fail |
|---|---|---|---|
| `id` (ascending) | Then 2 `[869, 870, 871] == [871, 870, 869]` | Then 6 (`1 == 2` DESC) | none |
| `first_name` | Then 2 | Then 4 | none |
| `email` | Then 2 | Then 4 | none |
| `email DESC` | **passes** | Then 4 | none |
| `first_name DESC, id` | Then 2 `[3038, 3039, 3037]` | Then 7 (two commas) | none |

So the non-strict card can fail on its Then 2, and no pass card depends on the order among ties. Its one blind spot: `email DESC` gives the intended order by accident, because the card's emails `a.`, `b.`, `c.` sort the same way as the ids (see Notes for maintainers; LS-16 still catches that variant).

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Coverage gaps
None — 100% line and branch coverage (`--cov=app.dao.waitlist --cov-branch`, private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs and 5 forced plans via `PGOPTIONS` (`enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off), and three database time zones (`timezone=UTC`, `Asia/Dhaka`, `America/Los_Angeles`): each `40 passed, 5 xfailed`, and `--runxfail` gave the same five failing values in each. No card compares a real-clock stamp (CS-01 checks only that `created_at` is aware); CS-01, LS-14 and LS-15 were still repeated 2000 times each in one process, and every test 20 times (`rep_plug.py`, scratch, fresh items per repeat): `4000 passed, 2000 xfailed` and `800 passed, 100 xfailed` — nothing red, LS-15 never XPASSed. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1410 is fixed, LS-04, 05, 06 turn the run red (`XPASS(strict)`): remove their markers. When BUG-1411 is fixed, LS-16 does; remove its marker and LS-15's.
- Never read an LS-15 XPASS as BUG-1411 being gone: LS-16 is the proof.
- LS-15 does not tell `id DESC` from `email DESC` as the tie-break (its emails sort like its ids). A future revision of the card could give the rows emails that sort against the ids (e.g. `c.` for A, `a.` for C).
- `N0` cards assume the table holds fewer than 999 committed rows (spec gap 3).

## Revision history
- **Revision 1 of the cases (`waitlist.verify.md`, case-missing Findings 1–3):** added WLS-GE-08 (after GE-07) and WLS-LS-26 … LS-31 (after LS-25), each at its card's place, same form, `TAG`-scoped like the rest. All seven are `pass` cards and pass today. No existing test changed: no existing card, Convention or ID changed (LS-15's emails were left as they are, per the Revision line). Checks on the final text: 3 default runs and the 5 forced plans, each `47 passed, 5 xfailed`; `--runxfail` gives the same five failures with the same Then lines as above; `WL_MODE=fix` with `--runxfail` **52 passed**, with the markers on `4 failed (XPASS(strict)), 47 passed, 1 xpassed`; coverage 100% line and branch with a private `COVERAGE_FILE`; `ruff check` passed; LF.

**The verifier's named variants, rebuilt here** (`wl_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\waitlist`, `-p wl_var`, `WL_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). Base = the reference above; each run with `--runxfail`, default plan. `ref` alone: 52 passed.

| Variant | Edit | Cards that fail |
|---|---|---|
| `ge_r1_txt_lower_col` | `lower(email) == arg` | WLS-GE-08 |
| `ls_r4_txt_like` | `status LIKE arg` | WLS-LS-27 |
| `ls_r4_txt_endswith` | `status` ends with `arg` | WLS-LS-28, LS-29, LS-30 (`""` ends every status) |
| `ls_r4_txt_strip_arg` | `status == arg.strip()` | WLS-LS-26 |
| `ls_r4_txt_lstrip_arg` | `status == arg.lstrip()` | WLS-LS-26 |
| `ls_r4_txt_trim_col` | `trim(status) == arg` | WLS-LS-30 |
| `ls_r4_txt_ltrim_col` | `ltrim(status) == arg` | WLS-LS-30 |
| `ls_r4_truthy` | `if status:` instead of `is not None` | WLS-LS-29 |
| `ls_r2_lstrip` | search `lstrip()` instead of `strip()` | WLS-LS-31 |

Every variant is caught by the new card the verifier named for it; no other card fails under any of them.
