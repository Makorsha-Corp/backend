# Execution notes — `app/dao/refresh_token.py`

> Cases: `tests/unit/dao/refresh_token.cases.md` (Revision 1, READY, 51 cases) · Tests: `tests/unit/dao/test_refresh_token.py` · Source commit: e48a092
> Result: **51 tests for 51 cases — 49 passed · 2 xfailed · 0 discrepancies · 0 errors** — branch coverage 97% (35 statements, 4 branches; 1 line missed, dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_refresh_token.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, in card order. A scratch audit script (`audit.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\refresh_token\`, not kept in the repo) checked each ID once and in order, `# Then 1..N` matching each card's Then count, and the xfail marker matching each Expect line. LF only.

## How the tests are built
- **Patched:** `app.dao.refresh_token.utcnow` → NOW, as `with patch(UTCNOW, return_value=NOW):` around every When (Conventions, Externals). Nothing else is mocked. RT-RV-08's When is a raw `DELETE` with no DAO call; it runs inside the same patch for uniformity, which has no effect.
- **Constants:** `dao`, `MISSING`, `NOW`, `EARLY`, `PAST`, `LATER`, `SLACK`; `clock()` is the card's clock-window expression.
- **Per-test values:** fixture `hashes` makes one TAG per test; `H1` … `H5` are fixtures over it (only H1–H5 are used); `FAM1`, `FAM2` are `str(uuid.uuid4())` fixtures.
- **Standing rows:** `w1`, `w2`, `u1`, `u2` (chained, so ids rise in that order), all through the autouse `standing_rows`.
- **Builder:** `mk_token(token_hash=, **columns)` = "token" (U1, FAM1, LATER), flushed one at a time.
- **Reading helpers (no expected values inside):** `reread(db, id)` (expire_all, then SELECT); `raw(db, row, col)` (raw SQL, session untouched); `snap(db, id)` / `snap_except(db, id, col)` = "unchanged"; `stored_count(db)` = "nothing written"; `count_where(db, col, value)` for the card's count lines.
- **Database-error cards:** `pytest.raises` around `db.begin_nested()` around the patched When.
- **Rolled back:** `patch.object(db, "commit", wraps=db.commit)` as the spy; `sp = db.begin_nested()` directly before the When; the inside-savepoint checks, `sp.rollback()`, the after-rollback checks; the spy's `call_count == 0` is the last Then.
- **Statement recorder:** a `before_cursor_execute` listener on the session's connection, around the When only (RT-GH-08).

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| RT-CR-11 | yes | the When call, before Then 1, as the card's Fails line says | `DataError: (psycopg2.errors.StringDataRightTruncation) value too long for type character varying(512)` |
| RT-CR-12 | yes | the When call, before Then 1 | `DataError: (...StringDataRightTruncation) value too long for type character varying(64)` |

**Lines past the failure point.** Reference plugin `rt_ref.py` (same scratch dir; `-p rt_ref`, in-process only, nothing in `app/`) wraps `RefreshTokenDAO.create` to cut `user_agent` to 512 and `ip_address` to 64. With it: `--runxfail` gives 49 passed, so Then 1 and 2 of both cards hold under the intended behaviour. With the markers on, both cards are `XPASS(strict)`, so the run turns red when BUG-1407 is fixed.

**Non-strict cards / wrong-ORDER-BY proof:** not applicable. The module has no list query and no `ORDER BY`, and no card is non-strict.

## Discrepancies
None. No card was changed, no marker loosened, and no test is marked DISCREPANCY.

## Spec gaps of the cases file, checked
- Gap 1 (±5 s around `issued_at`): held in 3,000 repeats of RT-CR-01, 1,500 with the session in UTC and 1,500 in Asia/Dhaka.
- Gap 3: the bulk revokes do call `db.flush()` after the `UPDATE` (source lines 92, 106). No card depends on it, as the cases file says.
- No assumed path or value was wrong.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 33 | dead | `get_by_id`, which the spec's Q3 lists as dead code to be removed (`docs/testing/dead-code-removal-checklist.md`). |

Run with a private `COVERAGE_FILE`: `--cov=app.dao.refresh_token --cov-branch --cov-report=term-missing`. All 4 branches are covered.

## Factories added
None.

## Stability
- **Default runs:** 5, each `47 passed, 2 xfailed`.
- **Forced plans:** 5 via `PGOPTIONS`, each `47 passed, 2 xfailed`:
  - `enable_seqscan=off`
  - that plus hash join and nested loop off
  - `enable_hashjoin=off`
  - index, bitmap and index-only scans off
  - that plus hash and merge join off
- **Time zones:** 3 via `-c timezone=…` (UTC, Asia/Dhaka, America/Los_Angeles), each the same result. The session zone was confirmed with `SHOW timezone`.
- **Repeats:** 20 of every test in one process: 940 passed, 40 xfailed.
- **Coverage run:** the same result.
- **ruff:** `ruff check` passed.

## Revision history
- **Revision 1 of the cases (refresh_token.verify.md, case-missing Findings 1, 2):** added RT-RA-07 (another user's row at the lower id stays unrevoked) after RA-06, and RT-TL-03 (an unrevoked row stays unrevoked; only `last_used_at` changes) after TL-02. Both are pass cards, written by hand in the form of RA-02 and TL-01. No existing card, Convention or test changed; none retired. The scratch audit (`audit.py`) reports 51 cards, 51 tests, no problems.
- **Rerun:** 5 default runs, the 5 forced plans and 3 time zones (UTC, Asia/Dhaka, America/Los_Angeles), each `49 passed, 2 xfailed`; the coverage run the same, 97% (line 33 only). `--runxfail`: `2 failed, 49 passed` (CR-11, CR-12 unchanged). Reference `rt_ref.py` with `--runxfail`: 51 passed; markers on: `2 failed` (both `XPASS(strict)`), 49 passed. `ruff check` passed; LF. Neither new card reads the real clock (both run under the `utcnow` patch), so no repeat loop.

**The verifier's named variants, rebuilt here** (`rt_var.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\refresh_token`, `-p rt_var`, `RT_VAR=<name>`, in-process, nothing in `app/`; not the verifier's own files). Each run on top of `rt_ref`, `--runxfail`, default plan:

| Variant | What it changes | Cards that fail | Failing value |
|---|---|---|---|
| `ra_r2_le` | `revoke_all_for_user` compares `user_id <= user_id` | RT-RA-07 only, Then 1 | `assert 2 == 1` (X of U1 revoked too) |
| `tl_r1_stamp_revoke` | `touch_last_used` also sets `revoked_at = revoked_at or now` | RT-TL-03 only, Then 3 | `{'revoked_at': 2026-03-05 12:00} != {'revoked_at': None}` |

No other card fails under either variant.

## Notes for maintainers
- When BUG-1407 is fixed, RT-CR-11 and RT-CR-12 turn the run red (`XPASS(strict)`). Remove both markers then.
- RT-RF-08 and RT-RA-05 pin today's stale-copy rule: a bulk revoke does not refresh rows already loaded in the session. If the DAO starts expiring or synchronising the session (for example `synchronize_session="fetch"` or an `expire` after the update), those two cards fail. That is a spec change (FU-1 (b)), not a test fix.
- Hashes and families are unique per test, so parallel runs on `marker_test` never wait on the unique hash index and never see each other's rows.
- The file's `ruff: noqa` carries `SIM117` and `DTZ001`, for the nested `with` blocks and the naive datetimes the Conventions prescribe.
