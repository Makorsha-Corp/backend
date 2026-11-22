# Execution notes — `app/dao/work_order_template.py`

> Cases: `tests/unit/dao/work_order_template.cases.md` (revision 3) · Tests: `tests/unit/dao/test_work_order_template.py` · Source commit: e48a092
> Result (revision 3, 2026-11-09): 96 tests for 96 cases — 85 passed · 11 xfail (6 strict, 5 non-strict) · 0 discrepancies · 0 errors — branch coverage 100% (40 statements, 8 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_work_order_template.py -q -p no:cacheprovider -o addopts="" --cov=app.dao.work_order_template --cov-branch --cov-report=term-missing` (private `COVERAGE_FILE`)

A default run reads `85 passed, 10 xfailed, 1 xpassed`: the non-strict WOTP-AG-09 XPASSES, as its card expects ("physical order usually matches, which is why this card is non-strict").

## How the tests are built
- Normal mode (no local model); every test sits below `# [claude] <ID>`, in card order.
- **Standing rows** are one autouse fixture `st` (a `SimpleNamespace` with `W0 … SD`), built in the Conventions order and flushed one row at a time, so `W0.id < W1.id < W2.id`, `TA < TB < TC`, `S1 < S2 < S3 < SD`.
- **Given rows:** `tpl(db, st, created_at, **cols)` (template; `created_at` is always passed, as the cards give it), `rec(db, st, **cols)` (recurring: `T10`, `is_recurring True`, `next_generation_date DT`), `line(db, st, T, **cols)`, `appr(db, st, T, U, **cols)`. Each flushes. The `add_all` Givens (GW-23/24, RD-17, IT-04) build the models directly with the same default dicts and flush once.
- **Named checks:** `ids`, `idset`, `snap` (every column straight from the table, for `unchanged(X)`), `counts` (the three tables, all workspaces, for "nothing written"), `approvers(db, T)`, `reread`. The statement recorder listens to `before_cursor_execute` on the session's connection; `sql()` insists on exactly one `SELECT`; `order_part_of` takes the text after the first `ORDER BY`, cut at `LIMIT`.
- `raises: DataError` cards wrap the call in `pytest.raises` around `db.begin_nested()`; the "nothing written" count is taken before and after on the still-usable session.
- **Commit spy (DA-05):** `sp = db.begin_nested()`, `patch.object(db, "commit", wraps=db.commit)`, then `sp.rollback()` and `db.expire_all()` before the count. Nothing else is patched.
- **Dhaka (M-02, M-03):** `SET LOCAL TimeZone = 'Asia/Dhaka'` as the first step; it lasts for the test's outer transaction.
- AG-08 uses the explicit ids 1900000001…3 the card gives (rolled back after the test).

## xfail location (`--runxfail`, own `failson` plugin: failing line → `# Then N`)
| Card | Strict | Fails on | Failing check |
|---|---|---|---|
| GW-15 | no | Then 2 | `ids(result) == [c, b, a]` |
| GW-16 | no | Then 2 | `ids(result) == [c, b, a]` |
| GW-17 | no | Then 2 | page ids `== [e, d, c, b, a]` |
| GW-18 | yes | Then 4 | `".id" in order_part` (order by `created_at` only) |
| RD-13 | yes | Then 1 | `idset == {B, N}` (D returned through SD) |
| RD-14 | yes | Then 1 | `result == []` (D returned) |
| AG-08 | no | Then 2 | ids by explicit id |
| AG-09 | no | — (passes today, as the card allows) | — |
| AG-10 | yes | Then 2 | `"ORDER BY" in sql` |
| M-02 | yes | Then 2 | `before <= created_at <= after` (Dhaka now()) |
| M-03 | yes | Then 2 | `before <= updated_at <= after` |

Every strict xfail fails on the Then line its card names. `--runxfail`: 10 failed, 86 passed.

**Reference plugin** (`<scratch>/dao/plugins/ref_wotp.py`, in-process, nothing in `app/`): `get_by_workspace` ordered by `created_at DESC, id DESC`; `list_recurring_due` outer-joins `factory_sections` whenever a scope is given and requires `is_deleted = false` for a section match; approver `get_by_template` ordered by `id`; mapper events set `created_at` / `updated_at` from `utcnow()`. Under it with `--runxfail`: **96 passed**. With markers on: 85 passed, 5 xpassed, 6 failed (the 6 strict XPASS(strict) — the red run a fix must produce).

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/work_order_template.py` (40 statements, 8 branches). The inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None.

## Notes for maintainers
- 3 plain runs: `85 passed, 10 xfailed, 1 xpassed` each (AG-09 XPASS every time). `ruff check`: clean (file-level `noqa` for SIM117, DTZ001 and FURB157 — `Decimal("1")` is written as the cards give it). LF line endings.
- When BUG-2330 is fixed: GW-18 XPASSes (red) — remove its marker and those of GW-15, 16, 17. BUG-2331: AG-10 XPASSes — remove it and AG-08, AG-09. BUG-2332: RD-13, RD-14. BUG-2333: M-02, M-03 (if the test database itself runs in UTC, they still fail only because of the `SET LOCAL` step).
- The tie cards are non-strict because today's order follows the heap; they cannot prove the bug alone. GW-18 / AG-10 are the strict alarms.

## Useful for the coming permissions / notifications / payments features
Nothing here: plain reads and one bulk delete of default approvers; no role, event or money logic. The default approvers (`work_order_template_approvers`) are the list a permission feature would check against when approval roles are added; they are returned unordered today (BUG-2331).

## Revision history
- **2026-11-09 — Revision 2** (first execution): 96 cases → 85 passed · 11 xfail; no discrepancy.
- **2026-11-09 — Revision 3** (cases wording only, verify finding 1: M-02's "Fails today on" text). No test changed what it checks; the WOTP-RD-11 docstring now cites the card's full Rules line (`R4, R5b (Inputs: `0` included)`). Re-run: 85 passed · 10 xfailed · 1 xpassed (AG-09), coverage 100% branch; `--runxfail` every strict xfail fails on its named Then (GW-18 Then 4, RD-13/14 Then 1, AG-10 Then 2, M-02/03 Then 2); reference plugin 96 passed; 3 plain runs identical; ruff clean; LF.
