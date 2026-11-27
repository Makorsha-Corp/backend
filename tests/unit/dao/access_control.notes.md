# Execution notes — `app/dao/access_control.py`

> Cases: `tests/unit/dao/access_control.cases.md` (READY, 35 cases) · Tests: `tests/unit/dao/test_access_control.py` · Source commit: e48a092
> Result: **35 tests for 35 cases — 31 passed · 4 xfailed · 0 discrepancies · 0 errors** — branch coverage 100% (11 statements, 0 branches). Under the forced plan `enable_seqscan=off` the two non-strict cards XPASS: `31 passed, 2 xfailed, 2 xpassed`.
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_access_control.py -q -p no:cacheprovider`

## Who wrote what
Normal mode, no local model: every test sits below a `# [claude] <ID>` comment, in card order, with a `# Then N` comment before each numbered Then line.

## How the tests are built
- **Nothing is patched**; no method reads the clock, so no test compares real-clock stamps (no repeat loop needed).
- **Constants:** `dao`, `OWNER`, `FINANCE`, `PAGE`, `FEATURE`, `MISSING` (no card uses it).
- **Standing rows:** `w1`, `w2` from `make_workspace(db)`, through the autouse `standing_rows`.
- **Builders:** `mk_rule(**columns)` = "rule, but …" (inserts and flushes one row); `mk_many_rules(count)` = the "101 rules E1 … E101, built with `add_all`" Given, returns the rows.
- **Reading helpers:** `idset`, `ids`, `stored_count` ("nothing written": `access_control` row count), `seqscan(db)` (the three `SET LOCAL` lines), `StatementRecorder` (`before_cursor_execute` on the session's connection, around the When only; `sql()` = the one SELECT from `access_control`; `written()`), `order_part_of(sql)`.
- **Database-error cards:** `with pytest.raises(DataError) as exc:` around `with db.begin_nested():`.
- **Shared database:** rows with no workspace may come from other modules; GR-06 and GT-07 check membership only, as designed. No test depends on rows it did not create.

## xfail location (`--runxfail`, reading the failing value)
| Card | Strict | Fails on | Actual |
|---|---|---|---|
| ACL-GR-07 | no | Then 2 | `assert [1063, 1064, 1065, 1062] == [1062, 1063, 1064, 1065]` — the updated row comes back last |
| ACL-GR-08 | yes | Then 2 | `assert 'ORDER BY' in 'SELECT … access_control.role = %(role_1)s \n LIMIT %(param_1)s OFFSET %(param_2)s'` |
| ACL-GT-08 | no | Then 2 | `assert [1067, 1068, 1069, 1066] == [1066, 1067, 1068, 1069]` |
| ACL-GT-09 | yes | Then 2 | `assert 'ORDER BY' in 'SELECT … access_control.type = %(type_1)s \n LIMIT …'` |

**Reference and wrong-order plugin.** `acx_plug.py` in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\wsx\access_control` (`-p acx_plug`, `ACX_MODE=<mode>`), which replaces both methods in-process; nothing in `app/`.

| `ACX_MODE` (ORDER BY) | `--runxfail` | Markers on |
|---|---|---|
| `fix` (`id`) | 35 passed: Then 3–5 of GR-08 / GT-09 hold | GR-08, GT-09 `XPASS(strict)` → failed; GR-07, GT-08 xpassed |
| `id_desc` (`id DESC`) | GR-07, GT-08 fail Then 2; GR-08, GT-09 fail Then 4 | 31 passed, 4 xfailed |
| `target` | GR-07, GT-08 fail Then 2 (`[a, d, b, c]`); GR-08, GT-09 fail Then 3 | 31 passed, 4 xfailed |
| `target_id` (`target, id`) | GR-07, GT-08 fail Then 2; GR-08, GT-09 fail Then 5 | 31 passed, 4 xfailed |
| `id_target` (`id, target`) | GR-08, GT-09 fail Then 5; GR-07, GT-08 pass (the rows' order is right) | 31 passed, 2 xfailed, 2 xpassed |

So each non-strict card can fail on its Then 2, the strict cards reach Then 3, 4 and 5, and no pass card depends on order.

## Discrepancies
None. No card was changed, no marker loosened.

## Spec gaps of the cases file, checked
- Gap 1: `AccessControlTypeEnum` in `app.models.enums` exists with `PAGE = "page"`, `MANAGE_ORDER_STATUS = "manage-order-status"`, `FEATURE = "feature"` — the assumption holds.
- Gap 2: handled as designed (membership checks).

## Coverage gaps
None — 100% line and branch coverage (run with a private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Stability
5 default runs: `31 passed, 4 xfailed` each. Forced plans through `PGOPTIONS`: `enable_seqscan=off` and that plus hash join and nested loop off: `31 passed, 2 xfailed, 2 xpassed` (GR-07, GT-08 XPASS: with every scan type disabled the planner takes the id index, so rows come back id ascending); `enable_hashjoin=off`; index, bitmap and index-only scans off; that plus hash and merge join off: `31 passed, 4 xfailed`. Database time zones `UTC` and `Asia/Dhaka`: `31 passed, 4 xfailed`. Coverage run the same. `ruff check`: all checks passed. LF only.

## Notes for maintainers
- When BUG-1408 is fixed, GR-08 and GT-09 turn the run red: remove the four markers.
- Never read a GR-07 / GT-08 XPASS as the bug being gone: GR-08 and GT-09 are the proof.
- The xfail reasons name BUG-1408 with its bugs.md title.
