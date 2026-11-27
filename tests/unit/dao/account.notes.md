# Execution notes — `app/dao/account.py`

> Cases: `tests/unit/dao/account.cases.md` (READY, Revision 3, 76 cases; spec APPROVED 2026-11-03) · Tests: `tests/unit/dao/test_account.py` · Source commit: e48a092
> Result: **76 tests for 76 cases — 60 passed · 16 xfailed (14 strict, 2 non-strict) · 0 discrepancies · 0 errors** — branch coverage 96% (21 statements, 4 branches; 1 line missed, dead code)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_account.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment. The scratch audit (`C:\Users\User\AppData\Local\Temp\makorsh-pipeline\acctx\audit.py`) checked each ID once and in card order, the docstring, `# Then 1..N` against the card with a check in each block, strictness and every BUG id of the Expect line in the marker reason, every quoted literal of the Then lines, and LF endings: 0 problems.

## How the tests are built
- **Nothing is patched.** Paths of Spec gaps 1 and 2 are the real ones: `app.schemas.account.AccountCreate`, `app.models.account_invoice.AccountInvoice`.
- **Standing rows:** fixtures `w1`, `w2`, `u1`, each depending on the one before (flushed in Conventions order); autouse `standing_rows`.
- **Given rows:** `mk_account(name=..., **columns)` (W1, active, not deleted), `mk_tag(name=..., tag_code=..., **columns)`, `link(a, t, **columns)` — each adds and flushes, so ids rise in Given order. `closed` (fixture: needs U1) and `HALF_CLOSED` are the Conventions' column sets. `bulk(db, w1, n)` builds "Acct 001"… with `add_all` and one flush. `bump_a`, `seqscan` run the Conventions' SQL in order.
- **Reading helpers (no expected values inside):** `ids`, `names`, `reread` (expire_all, then SELECT by id), `written_counts` ("nothing written": accounts and account_tag_assignments rows, all workspaces), `count_rows` ("count:" lines).
- **Statement recorder:** a context manager around the When only (`before_cursor_execute` on the session's connection). `sql()` = the one SELECT `FROM accounts` (fails loudly unless exactly one); `order_part_of` = after `ORDER BY`, before `LIMIT`; `written()` = INSERT/UPDATE/DELETE.
- **Errors:** `pytest.raises(...)` around `db.begin_nested()` around the call; ACC-INH-02 (`TypeError` before any SQL) has no savepoint, as the card says.
- ACC-IW-06 calls `include_inactive=True`, which does not exist today; the call is written as the card shows.
- ACC-IW-19 is kept as designed (BUG-861 read as covering the stored code too, Spec gap 3); its marker reason says so.

## xfail check (`--runxfail`, failing value read)
Every xfail card was run with `--runxfail` (scratch plugin `acctx\rx.py` maps the failing line to its `# Then N`). Each fails at the Then its card names, with the value the card describes.

| Case | Strict | Fails on | Value read under `--runxfail` |
|---|---|---|---|
| ACC-IW-06 | strict | the When (card: "Then 1, the call raises") | `TypeError: AccountDAO.get_accounts_in_workspace() got an unexpected keyword argument 'include_inactive'` |
| ACC-IW-08 | strict | Then 1 | `assert [] == [548717, 548718]` |
| ACC-IW-09 | strict | Then 1 | `assert [] == [548719]` |
| ACC-IW-11 | strict | Then 1 | `assert [548724, 548725] == [548724]` (both returned) |
| ACC-IW-12 | strict | Then 1 | `assert [548726, 548727] == [548727]` (every account) |
| ACC-IW-13 | strict | Then 1 | `assert [] == [548728]` |
| ACC-IW-17 | strict | Then 1 | `assert [] == [548736]` |
| ACC-IW-18 | strict | Then 1 | `assert [] == [548737]` |
| ACC-IW-19 | strict | Then 1 | `assert [] == [548738]` |
| ACC-IW-22 | strict | Then 1 | `assert [<Account …>] == []` |
| ACC-IW-27 | non-strict | Then 2 | `assert ['Zulu', 'app…ilo', 'delta'] == ['apple', 'Ba…ango', 'Zulu']` |
| ACC-IW-28 | strict | Then 2 | `assert 'ORDER BY' in 'SELECT DISTINCT accounts.id AS accounts_id, …'` |
| ACC-IW-43 | strict | Then 1 | `assert [] == [807990]` (Revision 3) |
| ACC-BT-07 | strict | Then 2 | `assert [<Account …>] == []` (Then 1, one link, held) |
| ACC-BT-08 | non-strict | Then 2 | `assert ['Zulu', 'apple', 'Banana'] == ['apple', 'Banana', 'Zulu']` |
| ACC-BT-09 | strict | Then 2 | `assert 'ORDER BY' in 'SELECT DISTINCT accounts.id AS accounts_id, …'` |

Today's plan for both lists is a Unique over a Sort that starts with `id` (the `DISTINCT`), so the non-strict cards come back in id order whatever the heap order: ACC-IW-27 and ACC-BT-08 failed in every default run.

## Explicit wrong order (non-strict proof)
Scratch plugin `acctx\wrong.py` (`-p wrong`) adds an explicit wrong `ORDER BY` to the module's list SELECTs while `get_accounts_in_workspace` / `get_accounts_by_tag_id` run; the file runs with `--runxfail`.

| Rewrite | Non-strict cards that fail (at Then 2) | Pass cards that fail |
|---|---|---|
| `accounts.id DESC` | ACC-IW-27, ACC-BT-08 (2 of 2) | 0 |
| `accounts.id ASC` | ACC-IW-27, ACC-BT-08 (2 of 2) | 0 |
| `accounts.name DESC, accounts.id DESC` | ACC-IW-27, ACC-BT-08 (2 of 2) | 0 |

**Lines past the failure point (reference plugin).** `acctx\ref.py` (`-p ref`) replaces the methods in-process with the intended behaviour of every BUG the cards cite (include_inactive; name trimmed, blank = no filter; LIKE escaping of `%`, `_`, `\`; tag code trimmed and case-insensitive on both sides; active tags only; `EXISTS` instead of join + `DISTINCT`; `ORDER BY lower(name), id`; a deleted tag matches nothing) (Revision 2: `remove` left as it is; the spec now states the ORM's 23502). With `--runxfail`: 66 of 66 pass. Nothing in `app/` changes.

## Discrepancies
None (Revision 2). Revision 1 had DISCREPANCY-1 (ACC-INH-07: 23502, not 23503; a SQL `DELETE` gives 23001 because every FK to `accounts` but the tag links is RESTRICT) and DISCREPANCY-2 (ACC-INH-08: ORM `remove` nulls the tag links, 23502, instead of cascading). The spec's Gap log G1 restated inherited R5 as fact; the cards now expect 23502 with nothing deleted, and ACC-INH-09 / 10 cover the database side (23001; cascade). Markers removed.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 31 (`search_by_name_in_workspace`) | dead | Second name search (`ILIKE`, active, not deleted, no order); no caller; ruled remove (spec P3; `docs/testing/dead-code-removal-checklist.md`). |

Otherwise 100% line and branch coverage (private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–5 (file alone, Revision 1) | 46 | 17 | 0 | 0 |
| Default, runs 1–3 (file alone, Revision 2) | 51 | 15 | 0 | 0 |
| `enable_seqscan=off` | 46 | 17 | 0 | 0 |
| `enable_seqscan=off`, hash join and nested loop off | 46 | 17 | 0 | 0 |
| `enable_hashjoin=off` | 46 | 17 | 0 | 0 |
| index, bitmap and index-only scans off | 46 | 17 | 0 | 0 |
| the line above, hash and merge join off | 46 | 17 | 0 | 0 |
| `enable_sort=off` | 46 | 16 | 1 (ACC-BT-08) | 0 |
| database `TimeZone` `Asia/Dhaka` / `America/New_York` | 46 | 17 | 0 | 0 |
| `--runxfail` with the reference plugin (Revision 2) | 66 of 66 | — | — | 0 |

`PGOPTIONS` carried the forced plans and time zones. No card compares real-clock stamps. `ruff check`: all checks passed (header `noqa` covers SIM117 and DTZ001 for the Conventions' nested `with` and naive datetimes). Line endings: LF.

## Notes for maintainers
- When BUG-878, BUG-637, BUG-868, BUG-861, BUG-864, BUG-866, BUG-1480, BUG-1481 are fixed, their strict cards XPASS and fail: remove the marker; the non-strict ones (ACC-IW-27, ACC-BT-08) then pass every time; remove theirs too.
- ACC-IW-28 / ACC-BT-09 assert `lower(accounts.name)` in the `ORDER BY` (Spec gap 4); `DISTINCT` must go with the fix (Postgres refuses `SELECT DISTINCT … ORDER BY lower(name)`, 42P10).
- ACC-INH-07 / 08 pin today's ORM behavior (23502, nothing deleted). If `passive_deletes=True` is ever added to the `invoices` / `tag_assignments` backrefs, they fail and change with the spec.

## Revision history
- **Revision 2 (2026-11-03):** patched, not regenerated. ACC-INH-07 and ACC-INH-08 rewritten as now designed (`raises: IntegrityError` 23502 in a savepoint; nothing deleted); DISCREPANCY markers removed; added ACC-INH-09 (SQL `DELETE` → 23001, account stays), ACC-INH-10 (SQL `DELETE` cascades to links, tag stays), ACC-INH-11 (unreferenced account removed and returned). Every other test block kept as it was. Re-run: 3 runs (51 passed, 15 xfailed each), `--runxfail` (the 15 designed xfails fail at their cards' Thens, values as before), reference plugin 66 / 66, ruff, audit 0 problems, coverage unchanged (96%, line 31 dead).

- **Revision 3 (2026-11-03):** patched, not regenerated; new tests inserted at their card positions. Added ACC-IW-37 … IW-43 (IW-43 strict xfail BUG-637), ACC-BT-17, BT-18, BT-19; Then 5 `"DESC" not in order_part.upper()` added to ACC-IW-28 and ACC-BT-09. Re-run: 3 default runs; forced plans `enable_seqscan=off`, with hash join and nested loop off, `enable_hashjoin=off`, index/bitmap/index-only scans off, with hash and merge join off, `enable_sort=off`; `TimeZone=Asia/Dhaka`: 60 passed, 16 xfailed in every run, no non-strict pass by accident. `--runxfail`: the 16 xfails fail at their cards' Thens (IW-28 / BT-09 still at Then 2, the new Then 5 is past it). Reference plugin: 76 / 76 (Then 5 holds under `ORDER BY lower(name), id`). ruff, audit 0 problems, coverage unchanged (96%, line 31 dead).
  **Verifier's variants rebuilt** (`acctx\variants.py` on the reference, `--runxfail`, default / sequential scans off / index and bitmap scans off — the same result on all three): `iw_r1_ws_le` → IW-37; `iw_r5_ws_le` → IW-38; `iw_r5_ends` → IW-39 (and IW-21); `iw_r5_rev_contains` → IW-40, IW-41; `iw_r5_rev_like` → IW-41; `iw_r7_join_dup` → IW-42; `iw_r2_lstrip` → IW-43; `iw_r8_tail_desc` → IW-28 Then 5; `bt_r4_tail_desc` → BT-09 Then 5; `bt_r1_accws_ge` → BT-17; `bt_r1_accws_drop` → BT-17, BT-18; `bt_r1_accws_le`, `bt_r1_linkws_le` → BT-18; `bt_r2_tag_ws_added` → BT-19. Every named variant fails its recipe's card; the unchanged reference passes 76 / 76 on each plan.
