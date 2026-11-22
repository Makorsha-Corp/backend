# Execution notes — `app/dao/attachment.py`

> Cases: `tests/unit/dao/attachment.cases.md` (READY, 25 cases) · Tests: `tests/unit/dao/test_attachment.py` · Source commit: e48a092
> Result: **25 tests for 25 cases — 24 passed · 1 xfailed · 0 discrepancies · 0 errors** — branch coverage 68% (30 statements, 4 branches; every miss is the dead `restore`).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_attachment.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, written by hand from the cards. A throwaway audit script (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\A\check.py`, not kept in the repo) checked: each ID exactly once and in card order, the docstring starting with the ID, `# Then 1..N` matching the card's Then count, marker and bug matching the Expect line, no unused argument; `lits.py` there checked that every double-quoted literal of a card is in its test. LF only.

## How the tests are built
- **Patched:** `app.dao.attachment.utcnow` → NOW, through `frozen_clock()`, active during the When of every `SD` card only (Conventions, Externals). Nothing else is mocked.
- **Constants:** `dao`, `MISSING`, `NOW` (naive), `T0` (aware UTC).
- **Standing rows:** `w1`, `w2`, `u1`, `u2` (each depends on the one before, so ids rise in Conventions order), through the autouse `standing_rows`.
- **Builders:** `mk_attachment(**columns)` = "attachment"; `mk_deleted_attachment(**columns)` = "deleted attachment". The ATT-SD-12 rows (link, markup, markup event, ledger) are built inline with the card's constructors.
- **Reading helpers (no expected values inside):** `stored_utc(db, row)` is the card's SQL; `reread(db, row)` is `db.expire_all()` then SELECT by id; `snap(db, row)` is every column by a Core select, for "unchanged", taken after the last Given line; `stored_count(db)` is (all `attachments` rows, those with `is_deleted`), "nothing written".
- **Time-zone lines** (`SET LOCAL TIME ZONE ...`) are the first statement of the body, as the Conventions say.
- **Database-error card (SD-10):** `with pytest.raises(IntegrityError) as exc:` around `with db.begin_nested():`; that block is Then 1.
- **rolled back (SD-09):** `commit_spy(db)` = `mock.patch.object(db, "commit", wraps=db.commit)`; `sp = db.begin_nested()` directly before the call.
- **Statement recorder:** `StatementRecorder(db)`, a `before_cursor_execute` listener on the session's connection, around the When only; `recorder.sql()` is the one SELECT from `attachments`; `recorder.written()` is the card's `written`.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| ATT-SD-02 | yes | Then 3, every run (default, `UTC` and `Asia/Dhaka` database zones, 5 plans; the card sets its own zone) | `assert datetime(2026, 11, 3, 11, 8) == datetime(2026, 11, 3, 17, 8)`: 11:08 UTC stored, as the card says |

**Reference plugin.** `attx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\attx\A` (`-p attx_plug`, `ATTX_MODE=fix`) replaces `AttachmentDAO.soft_delete` in-process with one that stores `utcnow().replace(tzinfo=timezone.utc)`; nothing in `app/`. With `--runxfail` all 25 pass; with the marker on, SD-02 is `XPASS(strict)`. SD-02's failing Then is its last, so no line lies past it.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
Gap 1: the sibling constructors of ATT-SD-12 (`AttachmentLink`, `AttachmentMarkup`, `AttachmentMarkupEvent`, `AttachmentLedger`) all held as written. Gaps 2 and 3 need no executor action.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 91–107 | dead | `restore` — no caller; to be removed (spec P3, Not specified; Deferred table). |

Run with a private `COVERAGE_FILE` (`...\attx\A\.coverage`). Inherited `BaseDAO` methods live in `app/dao/base.py` and are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs, 5 forced plans and 2 database time zones, each `24 passed, 1 xfailed` (run together with `test_attachment_link.py`: `87 passed, 8 xfailed`, plans 1 and 2 `87 passed, 7 xfailed, 1 xpassed` from ALK-GL-07). `PGOPTIONS` carried: `enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off; `timezone=UTC`; `timezone=Asia/Dhaka` (the database default is `America/New_York`). No test compares a real-clock stamp (NOW is patched). `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1430 is fixed, ATT-SD-02 turns the run red (`XPASS(strict)`): remove its marker.
- Every `SD` card reading `deleted_at` sets its own `SET LOCAL TIME ZONE`; do not drop those lines, or the passing cards will depend on the database's zone.
