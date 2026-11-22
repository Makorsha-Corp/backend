# Execution notes — `app/dao/account_tag.py`

> Cases: `tests/unit/dao/account_tag.cases.md` (READY, Revision 3, 61 cases; spec APPROVED 2026-11-03) · Tests: `tests/unit/dao/test_account_tag.py` · Source commit: e48a092
> Result: **61 tests for 61 cases — 51 passed · 10 xfailed (7 strict, 3 non-strict) · 0 discrepancies · 0 errors** — branch coverage 100% (24 statements, 4 branches, 0 missed)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account_tag.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The scratch audit (`acctx\audit.py`) found 0 problems (IDs and order, docstrings, `# Then` blocks, markers and BUG ids, literals, LF).

## How the tests are built
- **Nothing is patched**; the **rolled back** cards (INC-09, DEC-11) wrap `db.commit` with `patch.object(db, "commit", wraps=db.commit)` (still callable, records calls), `sp = db.begin_nested()` directly before the call, `sp.rollback()` directly before the "after the savepoint rollback" check. Schema paths of Spec gap 1 are the real ones (`app.schemas.account_tag`).
- **Standing rows:** `w1`, `w2` (autouse `standing_rows`).
- **Given rows:** `mk_tag` / `mk_system_tag(name=..., tag_code=..., **columns)` add and flush (W1, not system, active, usage 0; a card's `workspace_id` overrides the default). The `add_all` Givens build `_tag(...)` objects and flush once (`add_many`). `bump_t`, `seqscan` as in the Conventions. "Stored value changed behind the object" = the card's `UPDATE` through `db.execute`, without expiring.
- **Reading helpers (no expected values inside):** `ids`, `names`, `stored_count` (database value, T not expired), `reread`, `snap` ("unchanged": every column by a Core select after `expire_all`), `written_count` ("nothing written": `account_tags` rows), `count_rows`.
- **Statement recorder** around the When only; `sql()` = the one SELECT `FROM account_tags`; `order_part_of` = after `ORDER BY`.

## xfail check (`--runxfail`, failing value read)
| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| ATG-ACT-05 | strict | Then 2 | `assert 100 == 101` |
| ATG-ACT-07 | non-strict | Then 2 | `assert [106113, 106114, 106115] == [106115, 106113, 106114]` (system tag last) |
| ATG-ACT-08 | non-strict | Then 2 | `assert [106116, …, 106117] == [106117, …, 106119]` |
| ATG-ACT-09 | strict | Then 2 | `assert 'ORDER BY' in 'SELECT account_tags.id AS account_tags_id, …'` |
| ATG-SYS-05 | strict | Then 2 | `assert [106230, 106231] == [106231]` (Then 1 held) |
| ATG-SYS-06 | non-strict | Then 2 | `assert ['Utility', 'client', 'Bank'] == ['Bank', 'client', 'Utility']` |
| ATG-SYS-07 | strict | Then 2 | `assert 'ORDER BY' in 'SELECT account_tags.id AS account_tags_id, …'` |
| ATG-INC-06 | strict | Then 2 | `assert 4 == 11` (loaded value used) |
| ATG-DEC-08 | strict | Then 2 | `assert 2 == 9` |
| ATG-DEC-09 | strict | Then 2 | `assert 2 == 0` |

Every designed xfail fails at the Then its card names, with the value its card describes.

## Explicit wrong order (non-strict proof)
`acctx\wrong.py` (`-p wrong`), file run with `--runxfail`:

| Rewrite | Non-strict cards that fail (at Then 2) | Pass cards that fail |
|---|---|---|
| `account_tags.id DESC` | ACT-07, ACT-08 (SYS-06's expected order equals id DESC) | 0 |
| `account_tags.id ASC` | ACT-07, ACT-08, SYS-06 | 0 |
| `account_tags.name DESC, account_tags.id DESC` | ACT-07, ACT-08, SYS-06 (3 of 3) | 0 |

**Reference plugin** (`acctx\ref.py`): intended behaviour of BUG-1482 (orders), BUG-1483 (active system tags), BUG-1484 (`UPDATE … SET usage_count = usage_count ± 1 … RETURNING`, the stored result set on the object without dirtying it; decrement only where above 0, no flush otherwise), BUG-1485 (no cap), (Revision 2: `remove` left as it is). With `--runxfail`: **59 of 59 pass**, so every line after each failure point holds once the bugs are fixed, and no pass card breaks under the fix.

## Discrepancies
None (Revision 2). Revision 1's DISCREPANCY-1 (ATG-INH-06: ORM `remove` of a tag with an assignment raises 23502 instead of cascading) was resolved by the spec's Gap log G1 (new inherited R6); ATG-INH-06 now expects 23502 with nothing deleted, ATG-INH-08 covers the SQL cascade. Marker removed.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/account_tag.py` (private `COVERAGE_FILE`).

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–5 (file alone, Revision 1) | 46 | 11 | 0 | 0 |
| Default, runs 1–3 (file alone, Revision 2) | 49 | 10 | 0 | 0 |
| `enable_seqscan=off`; + hash join and nested loop off; `enable_hashjoin=off` | 46 | 11 | 0 | 0 |
| index, bitmap and index-only scans off; + hash and merge join off | 46 | 11 | 0 | 0 |
| `enable_sort=off` | 46 | 11 | 0 | 0 |
| database `TimeZone` `Asia/Dhaka` / `America/New_York` | 46 | 11 | 0 | 0 |
| `--runxfail` with the reference plugin (Revision 2) | 59 of 59 | — | — | 0 |

No card compares real-clock stamps. `ruff check`: all checks passed. Line endings: LF.

## Notes for maintainers
- When BUG-1482, BUG-1483, BUG-1484, BUG-1485 are fixed, their strict cards XPASS and fail: remove the marker; the non-strict cards then pass every time.
- ATG-ACT-09 / SYS-07 assert `lower(account_tags.name)` (Spec gap 2) and `account_tags.is_system_tag DESC`.

## Revision history
- **Revision 2 (2026-11-03):** patched, not regenerated. ATG-INH-06 rewritten as now designed (`raises: IntegrityError` 23502 in a savepoint; tag and link stay); DISCREPANCY marker removed; added ATG-INH-07 (unreferenced tag removed and returned) and ATG-INH-08 (SQL `DELETE` cascades to assignments, account stays). Other blocks unchanged. Re-run: 3 runs (49 passed, 10 xfailed each), `--runxfail` (the 10 designed xfails fail at their cards' Thens), reference plugin 59 / 59, ruff, audit 0 problems, coverage 100%.

- **Revision 3 (2026-11-03):** patched, not regenerated. Added ATG-CODE-14 (trailing space on the argument) and ATG-CODE-15 (stored `_`); Then 5 `"DESC" not in order_part.upper()` added to ATG-SYS-07. Re-run: 3 default runs; forced plans `enable_seqscan=off`, with hash join and nested loop off, `enable_hashjoin=off`, index/bitmap/index-only scans off, with hash and merge join off, `enable_sort=off`; `TimeZone=Asia/Dhaka`: 51 passed, 10 xfailed in every run. `--runxfail`: the 10 xfails fail at their cards' Thens (SYS-07 still at Then 2). Reference: 61 / 61. ruff, audit 0 problems, coverage 100%.
  **Verifier's variants rebuilt** (three plans, same result): `code_r2_rtrim_arg` → CODE-14; `code_r2_rev_like` → CODE-15; `sys_r3_tail_desc` → SYS-07 Then 5. Unchanged reference 61 / 61.
