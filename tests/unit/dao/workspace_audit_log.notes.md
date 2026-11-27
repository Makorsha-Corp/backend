# Execution notes — `app/dao/workspace_audit_log.py`

> Cases: `tests/unit/dao/workspace_audit_log.cases.md` (Revision 1, READY, 23 cases) · Tests: `tests/unit/dao/test_workspace_audit_log.py` · Source commit: e48a092
> Result: **23 tests for 23 cases — 20 passed · 3 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (11 statements, 0 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_workspace_audit_log.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, in card order, with `# Then N` before each numbered Then line. LF only.

## How the tests are built
- **Nothing is patched.** WAL-LA-20 replaces `db.commit` (via `monkeypatch`) with `MagicMock(wraps=db.commit)`, the "rolled back" convention's spy; it still calls through.
- **Constants:** `dao`, `MISSING`, `SLACK`, `IP45`, `IP46`, `UA5000`.
- **Standing rows:** `w1`, `w2` (`make_workspace`), `u1` (`make_profile`), all through the autouse `standing_rows`, built in that order.
- **Reading helpers (no expected values inside):** `reread(db, id)` = `db.expire_all()` then SELECT by id; `stored_count(db)` = all `workspace_audit_logs` rows, "nothing written"; `count_rows(db, **where)` for the "count:" lines; `utc_clock()` = the clock window expression; `stamp(db, row)` = the card's `AT TIME ZONE 'UTC'` read.
- **Database-error cards:** `with pytest.raises(...) as exc:` around `with db.begin_nested():`; that block is Then 1.
- **Time-zone cards:** the test runs the card's `SET LOCAL TIME ZONE` itself, so `PGOPTIONS` time zones do not change them. Then 2 starts with `db.expire_all()` (re-read), then `stamp`.
- **Statement recorder:** `StatementRecorder(db)` (`before_cursor_execute` on the session's connection) around the When only; `written()` / `selects()`.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| WAL-LA-07 | yes | the When, inside `begin_nested`, before Then 1 (the card's "Then 1: the call raises DataError") | `StringDataRightTruncation: value too long for type character varying(45)` |
| WAL-LA-15 | yes | Then 2 | `assert 2026-11-03 08:52:37 >= 14:52:37 - 5 s`: 6 hours early |
| WAL-LA-16 | yes | Then 2 | `assert 2026-11-03 19:52:37 <= 14:52:37 + 5 s`: 5 hours late |

**Reference plugin** `walx_fix.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\workspace_audit_log` (`-p walx_fix`, in-process, nothing in `app/`): `log_action` cuts `ip_address` to 45 characters; the `created_at` column default becomes `datetime.now(timezone.utc)`. With `--runxfail`: 23 passed (Revision 1; 21 before), so every line past each failure point holds under the intended behavior. With the markers on: 20 passed, 3 `XPASS(strict)` failed — the markers turn the run red once the bugs are fixed.

**Non-strict proof:** not applicable; the module has no non-strict card and no ordered read.

## Discrepancies
None. No card was changed, no marker loosened, no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
1. `StatementError` cause: `exc.value.orig` is the `TypeError` (WAL-LA-11 Then 2 passes as written).
2. ±5 s tolerance: held in every run, including 3000 repeats of LA-14/15/16.

## Coverage gaps
None — 100% line and branch coverage. Run with a private `COVERAGE_FILE`. Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs, five forced plans (`enable_seqscan=off`; that plus hash join and nested loop off; `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off) and three `PGOPTIONS` time zones (`UTC`, `Asia/Dhaka`, `America/New_York`): each `18 passed, 3 xfailed`. Clock cards WAL-LA-14, 15, 16 repeated 3000 times each in one process (`walx_rep.py`): `3000 passed, 6000 xfailed`. Whole file 20 times in one process: `360 passed, 60 xfailed`. `ruff check`: all checks passed.

## Notes for maintainers
- When BUG-1405 is fixed, WAL-LA-07 XPASSes (strict → red): remove its marker. When BUG-1403 is fixed, WAL-LA-15 and 16 do the same.
- The time-zone cards compare with the real clock (the default `utcnow` is bound into the column default and cannot be patched); the ±5 s window has never been close.
- WAL-LA-19, 22 and 23 each leave out one required keyword; they guard R7 against a default being added to `action`, `workspace_id` or `user_id`.

## Revision history
- **Revision 1 of the cases (`workspace_audit_log.verify.md` Finding 1, recipe R-1):** added WAL-LA-22 (no `workspace_id`) and WAL-LA-23 (no `user_id`) at their card place, the end of the file, in the form of WAL-LA-19. No existing card, Convention or ID changed, so no existing test changed. Rerun: 3 default runs and the 5 forced plans, each `20 passed, 3 xfailed`; `--runxfail` `3 failed, 20 passed` (the same three xfails, same lines); reference `walx_fix` with `--runxfail` 23 passed, with markers `3 failed (XPASS strict), 20 passed`; coverage 100% line and branch with a private `COVERAGE_FILE`; `ruff check` passed; LF only. Both new cards are pass cards and passed in every run.

**The verifier's R7 variants, rebuilt here** (`walx_var.py` in the scratch folder above, `-p walx_var`, `WALX_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). Each gives one required keyword a default and keeps the reference's IP cut; run with `-p walx_fix --runxfail`, default plan:

| Variant | Cards that fail | Fails on |
|---|---|---|
| `la_r1_ws_default` (`workspace_id=None`) | WAL-LA-22 only | Then 1, `DID NOT RAISE TypeError` |
| `la_r7_user_default` (`user_id=None`) | WAL-LA-23 only | Then 1, `DID NOT RAISE TypeError` |
| `la_r7_action_default` (`action` given a default; control) | WAL-LA-19 only | Then 1, `DID NOT RAISE TypeError` |

No other card fails under any variant (22 passed each).
