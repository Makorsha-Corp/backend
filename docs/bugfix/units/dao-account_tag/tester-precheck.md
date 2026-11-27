# Tester pre-check: dao-account_tag

Date: 2026-11-27 (batch 3). Source `app/dao/account_tag.py`. Specs and cases:
`tests/unit/dao/account_tag.*`, `tests/unit/services/account_tag_service.*`.

**Search.** I grepped the bare numbers `1482`–`1485` in `tests/**/*.py`. Markers use reason
constants: `BUG_1482`..`BUG_1485` (plus `NON_STRICT` suffix) in `tests/unit/dao/test_account_tag.py`
lines 35–39, and `BUG_1482`, `BUG_1483`, `BUG_1485` in `tests/unit/services/test_account_tag_service.py`
lines 48–50. Every `xfail(reason=BUG_14xx...)` use was mapped. No other file names these bugs.

**Caller test files** (found with Grep for `account_tag` / `AccountTag` in `tests/**/*.py`; none of
them carries a marker for these bugs):
- `E:\Projects\Makorsh-Corp\backend\tests\unit\dao\test_account_tag.py` (unit's own)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\services\test_account_tag_service.py` (both lists)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\managers\test_account_manager.py` (counters)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\dao\test_account_tag_assignment.py` (decrement via `remove_all_tags_from_account`)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\services\test_account_service.py`
- `E:\Projects\Makorsh-Corp\backend\tests\unit\dao\test_account.py`
- `E:\Projects\Makorsh-Corp\backend\tests\unit\managers\test_workspace_manager.py` (tag seeding)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\managers\test_sales_manager.py`
- `E:\Projects\Makorsh-Corp\backend\tests\unit\services\test_sales_service.py`
- `E:\Projects\Makorsh-Corp\backend\tests\test_register_timezone.py`

**Run today** with `--runxfail -rf`, DB `bf_dao_account_tag_test`: all 14 target tests fail, each on
the Then its card names (ACT-05 101≠100; SYS-05 deleted tag returned; ACT-09 / SYS-07 no `ORDER BY`;
INC-06 4≠11, DEC-08 2≠9, DEC-09 2≠0; the non-strict order tests on their order Then).

**Simulated fixes** (scratch pytest plugin swapping the DAO methods in memory, no `app/` edit; all 10
files above, 1583 tests): with a correct fix (ORDER BY keys as specified, `is_active` filter on the
system list, no cap, Core relative UPDATE with RETURNING) **exactly the 14 target tests change**
(9 strict xfail → pass, 5 non-strict xfail → xpass); no other test changes in any caller file. The one
xpass already in the baseline (`test_sales_service.py` SS-A-07b, BUG unrelated) is unchanged.

## BUG-1482: both tag lists have no order

| File | Tests | Strict |
|---|---|---|
| DAO | ATG-ACT-07 (system first), ATG-ACT-08 (name ci, then id), ATG-SYS-06 | no (physical order can match) |
| DAO | ATG-ACT-09, ATG-SYS-07 (SQL text) | yes; fail on Then 2 (no `ORDER BY`) |
| service | ATV-T-07, ATV-Y-04 | no |

Verdict: **right**, all 7. ACT-08 and SYS-06 are R4's and R3's own examples, with a forced sequential
scan and a bump so the physical order differs. ACT-09 wants `account_tags.is_system_tag DESC`,
`lower(account_tags.name)` and `account_tags.id` after `ORDER BY`; SYS-07 wants `lower(account_tags.name)`,
`account_tags.id` and no `DESC`. `order_by(AccountTag.is_system_tag.desc(), func.lower(AccountTag.name), AccountTag.id)`
passes. Risk for the systems engineer: a raw `text()` sort, `func.upper`, `collate(...)` or an
`ilike`-style key would fail the SQL-text tests although it might sort right; `nulls_last()` or
`asc()` wrappers are fine. Neither test checks key order; ACT-07 / ACT-08 do.

## BUG-1483: system list includes deleted system tags

| File | Tests | Strict |
|---|---|---|
| DAO | ATG-SYS-05 | yes; fails on Then 2 |
| service | ATV-Y-03 | yes |

Verdict: **right**, both. They check R2 only (the live system tag stays, the deleted one goes).

## BUG-1484: usage counter can lose concurrent changes

| File | Tests | Strict |
|---|---|---|
| DAO | ATG-INC-06 | yes; fails on Then 2 (4, not 11) |
| DAO | ATG-DEC-08 | yes; fails on Then 2 (2, not 9) |
| DAO | ATG-DEC-09 | yes; fails on Then 2 (2, not 0) |

Pass controls that constrain the fix: INC-07 (expired object → 11), INC-08 / DEC-10 (the flush also
saves a pending rename), **DEC-03 (at 0 nothing is flushed: a pending rename stays unsaved)**, INC-09 /
DEC-11 (flushed, not committed), INC-02/03, DEC-05/06 (`None`, nothing written), DEC-04 (negative stays).

Verdict: **right but incomplete** → entry in `docs/bugfix/wrong-tests.md` ("BUG-1484: ATG-INC-06 and
ATG-DEC-08"), the same gap as BUG-931 (A19). Candidates run through the scratch plugin:

| Candidate | INC-06 / DEC-08 / DEC-09 today | with the correction | Fixes the race? |
|---|---|---|---|
| Core `update(...).values(usage_count=usage_count ± 1).returning(...)`, decrement guarded `usage_count > 0`, `set_committed_value`, flush only when written | pass | pass (20/20 counter tests) | yes |
| ORM `query.update(..., synchronize_session=False)` + `db.refresh(tag, ["usage_count"])` | pass | pass (20/20) | yes |
| shortcut: `db.refresh(tag, ["usage_count"])`, then the old `+= 1` / `-= 1` | **pass** (and identical outcomes to the correct fix over all 10 files) | INC-06, DEC-08 fail on Then 4 | **no** |
| today's code | fail on Then 2 | still fail on Then 2 | no |

**Condition:** the diff in `wrong-tests.md` (also saved as
`docs/bugfix/units/dao-account_tag/test-correction.diff`, `git apply --check` clean) must be on
`origin/main` before the batch-3 baseline. If it isn't, BUG-1484 is skipped this round (remove it from
`brief.md`, re-run the firewall, and drop it from the `state.md` row).

Notes for the systems engineer:
- Reject any fix that re-reads and then writes an absolute value, or that locks the row
  (`with_for_update`; HR-10 says no lock).
- The ORM's default synchronisation evaluates `usage_count + 1` against the stale in-memory value, so
  the returned tag must be set from the database (RETURNING or a refresh of `usage_count`), or R5/R6
  "returned tag shows the stored result" breaks.
- DEC-03 requires that a decrement at stored 0 flushes nothing (session `autoflush=False`, as the
  app's `SessionLocal`). INC-08 / DEC-10 require that a written change flushes other pending changes.
  A fix that calls `db.flush()` unconditionally before the decrement's UPDATE breaks DEC-03.

## BUG-1485: active list stops at 100

| File | Tests | Strict |
|---|---|---|
| DAO | ATG-ACT-05 | yes; fails on Then 2 (100, not 101) |
| service | ATV-T-08 | yes |

Verdict: **right**, both. Control ATG-ACT-06 (a deleted tag ahead of 100 active ones takes no place)
passes today and after the fix. No test calls the method with `skip` / `limit`, so removing them breaks
nothing; `AccountTagService.get_tags` passes only `workspace_id` (checked in `app/`).

## Outside this unit

- `app/dao/account_tag_assignment.py` `remove_all_tags_from_account` calls `decrement_usage_count` once
  per link; BUG-1487 / BUG-870 (account manager) are where saves recreate or erase links. No test there
  names BUG-1484, and the simulated fix changed nothing in that file.
- BUG-2987 / BUG-629: deleted tags can still be attached on account create / update, so their counters
  move (spec P2: raw write, intended at the DAO).
- Other DAOs with the same read-then-write counter pattern should get the relative-UPDATE check at
  their pre-check too (none found in this unit's callers).

## Note for stage C

Remove the markers on all 14 tests (DAO: ACT-05, ACT-07, ACT-08, ACT-09, SYS-05, SYS-06, SYS-07,
INC-06, DEC-08, DEC-09; service: ATV-T-07, ATV-T-08, ATV-Y-03, ATV-Y-04). Every marker names only one
of this unit's bugs, so all go; then the constants `BUG_1482`..`BUG_1485` and `NON_STRICT` in the DAO
file, and `BUG_1482`, `BUG_1483`, `BUG_1485` in the service file, have no use left and go too. The flip
check should show 9 strict xfails → passed and 5 non-strict (xfailed or xpassed) → passed, nothing else.
If BUG-1484 was skipped (correction not landed), leave INC-06, DEC-08, DEC-09 and `BUG_1484` alone:
11 flips.
