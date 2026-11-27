# Execution notes — `app/dao/account_tag_assignment.py`

> Cases: `tests/unit/dao/account_tag_assignment.cases.md` (READY, Revision 2, 36 cases; spec APPROVED 2026-11-03) · Tests: `tests/unit/dao/test_account_tag_assignment.py` · Source commit: e48a092
> Result: **36 tests for 36 cases — 33 passed · 3 xfailed (2 strict, 1 non-strict) · 0 discrepancies · 0 errors** — branch coverage 100% (36 statements, 6 branches, 0 missed)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_tag_assignment.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The scratch audit (`acctx\audit.py`) found 0 problems.

## How the tests are built
- **Nothing is patched.** GD cards set `mod.account_tag_dao` with `monkeypatch.setattr` (restored after the test). Rolled-back cards (DA-05, RA-05) use the `db.commit` spy (`patch.object(..., wraps=db.commit)`), `sp = db.begin_nested()` before the call and `sp.rollback()` before the "after" checks. Schema path of Spec gap 1 is the real one (`app.schemas.account_tag_assignment`).
- **Standing rows:** fixtures `w1`, `w2`, `u1`, `a1` ("Acme"), `a2` ("Beta"), `a9` ("Far", W2), each depending on the one before, so they flush in Conventions order; autouse `standing_rows`.
- **Given rows:** `mk_tag(name=..., tag_code=..., **columns)`; `link(tag, **columns)` (W1, A1); `close(db, a, u1)` sets the four columns and flushes; `bump_t`, `seqscan` as in the Conventions. Given step ATA-DA-03.3 ("returns True") is asserted as a precondition.
- **Reading helpers:** `ids`, `links(db, a, w)`, `stored_count`, `reread`, `snap` (every column, Core select after `expire_all`), `written_counts` (`account_tag_assignments` and `account_tags` rows).
- **Statement recorder** around the When only; `sql()` = the one SELECT `FROM account_tags`.

## xfail check (`--runxfail`, failing value read)
| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| ATA-TFA-06 | strict | Then 2 | `assert [106276, 106277] == [106277]` (Then 1 held; the deleted tag is returned) |
| ATA-TFA-07 | non-strict | Then 2 | `assert [106278, …, 106279] == [106279, …, 106281]` |
| ATA-TFA-08 | strict | Then 2 | `assert 'ORDER BY' in 'SELECT account_tags.id AS account_tags_id, …'` |

## Explicit wrong order (non-strict proof)
`acctx\wrong.py`, file run with `--runxfail`: ATA-TFA-07 fails at Then 2 under `id DESC`, `id ASC` and `name DESC, id DESC` (1 of 1 each); no pass card fails.

**Reference plugin** (`acctx\ref.py`: active tags only, `ORDER BY lower(name), id`, plus the BUG-1484 counters reached through `remove_all_tags_from_account`): with `--runxfail`, **32 of 32 pass**.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage (private `COVERAGE_FILE`).

## Factories added
None.

## Stability
5 default runs and the forced plans (`enable_seqscan=off`; with hash join and nested loop off; `enable_hashjoin=off`; index/bitmap/index-only scans off; with hash and merge join off; `enable_sort=off`) and time zones `Asia/Dhaka`, `America/New_York`: 29 passed, 3 xfailed in every run; ATA-TFA-07 never passed by accident. No real-clock comparison. `ruff check`: all checks passed. Line endings: LF.

## Notes for maintainers
- When BUG-865 / BUG-1486 are fixed, remove the markers of TFA-06, TFA-08 (strict) and TFA-07 (non-strict).
- RA-01 tests the replace-all as it behaves today (links to deleted tags removed, BUG-1487 is the account manager's).

## Revision history
- **Cases reference change (2026-11-03):** the Deferred row for inherited R4 now points to ATG-INH-08 / ACC-INH-10 (SQL `DELETE` cascades) and notes the ORM 23502 cards. No card changed; the test file is unchanged. Re-run: 3 runs (29 passed, 3 xfailed each), `--runxfail` (the 3 xfails fail at Then 2 as before), ruff, audit 0 problems.

- **Revision 2 (2026-11-03):** patched, not regenerated. Added ATA-GA-05 (W2 asked for a W1 link), ATA-GA-06 (another account, same tag), ATA-RA-06 (W2 asked: nothing removed), ATA-RA-07 (another account: nothing of A1 removed). Re-run: 3 default runs; forced plans `enable_seqscan=off`, with hash join and nested loop off, `enable_hashjoin=off`, index/bitmap/index-only scans off, with hash and merge join off, `enable_sort=off`; `TimeZone=Asia/Dhaka`: 33 passed, 3 xfailed in every run. `--runxfail`: the 3 xfails fail at Then 2 as before. Reference: 36 / 36. ruff, audit 0 problems, coverage 100%.
  **Verifier's variants rebuilt** (three plans, same result): `ga_r2_ws_le` → GA-05; `ga_r2_acc_le` → GA-06; `ra_r1_ws_le` → RA-06; `ra_r1_acc_le` → RA-07. Unchanged reference 36 / 36.
