# Execution notes — `app/dao/item_tag.py`

> Cases: `tests/unit/dao/item_tag.cases.md` (READY, 92 cases; spec APPROVED 2026-10-17) · Tests: `tests/unit/dao/test_item_tag.py` · Source commit: e48a092
> Result: **92 tests for 92 cases — 81 passed · 11 xfailed · 0 discrepancies · 0 errors** — line and branch coverage 100% (24 statements, 4 branches). The 5 non-strict order cards may XPASS without turning the run red (see Stability).
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item_tag.py -q -p no:cacheprovider`

## Who wrote what
| Part | Count | Marker in the file |
|---|---|---|
| Exemplars (hand-written, Step A; printed verbatim in `item_tag.helpers.md`) | 6 — CODE-03, ACT-01, INC-01, DEC-04, INH-05, INH-01 | "Exemplar tests" section, no tag |
| Local model (Step C) | 70 | `# [local-coder] <ID>` |
| Claude, the `Author: claude` cards (Step D) | 16 — SYS-07, 08, 09, 10, ACT-08, 11, 12, 13, INC-11, 12, 13, DEC-13, 14, 15, INH-18, 19 | `# [claude] <ID>` |

After the exemplars, the tests are grouped by callable (one header per section of the cases file) and in card order inside each section.

## How the tests are built
- **Local-coder mode.** The local model's only view of the file is `item_tag.helpers.md`.
- **Nothing is patched** (spec "Externals to mock: none"); the commit spy of INC-13 / DEC-15 wraps the real `db.commit` (`patch.object(db, "commit", wraps=db.commit)`), so nothing is replaced. There is no clock fixture. `created_at` comes from the model's Python default. "close to now" is the Conventions expression (5 minutes, Spec gap 6) in the helper `close_to_now(value)`.
- **Constants:** `dao` (= `item_tag_dao`, a module-level name, not a fixture) and `MISSING = 999999999`.
- **Standing rows:** only `w1`, `w2` (from `tests/unit/factories.make_workspace`). `w2` depends on `w1`, so the ids rise in Conventions order. The autouse fixture `standing_rows` makes both present in every test. Every tag is built in the card's own Given.
- **Builders** (fixtures; keyword-only; each inserts one row and flushes, so ids rise in Given order):
  - `mk_tag(*, name, tag_code, **columns)` is the Conventions "tag": W1, `is_system_tag False`, `is_active True`, `usage_count 0`, `color` / `icon` / `description` / `created_by` None; `created_at` left to the model default. Each column after "but" is one more keyword.
  - `mk_system_tag(...)` is the same with `is_system_tag True` (a separate builder, because the runner's keyword check only accepts keywords the card's text names).
- **Reading helpers** (no expected values inside): `ids(result)`, `names(result)`; `reread(db, row)` (expire_all, then select by the identity key); `snap(db, row)` (every column, Core select); `stored_count(db, row)` (column query, no expire / refresh; with `autoflush=False` it does not see a pending change); `count_rows(db, "item_tags", **where)`; `written(db)`.
- **Database-error cards** (INH-02 … INH-09) wrap the call in `db.begin_nested()` inside `pytest.raises(...) as exc`. Then 1 is that block.
- **Step D helpers** (not in the helper sheet):
  - `bulk_tags(db, workspace, rows, *, is_system_tag)` — SYS-07, ACT-08: one multi-row Core `INSERT … RETURNING id` (`sort_by_parameter_order=True`) of the 101 rows with the Conventions "tag" columns, ids in insertion order. Then 2 compares with `sorted(n_ids)` ("the 101 ids, ascending").
  - `StatementRecorder(db)` — SYS-10, ACT-13, INH-19: a `before_cursor_execute` listener on the session's connection, active only around the When call. `[sql] = recorder.selects()` takes the one SELECT (unpacking fails loudly if there is not exactly one); `order_part_of(sql)` is the text after `ORDER BY`, `""` when there is none.
  - **Stale object** (INC-11, INC-12, DEC-13, DEC-14): the Given runs `db.execute(text("update item_tags set usage_count = <n> where id = :i"), {"i": t1.id})` on the same session and transaction after T1 was flushed. T1 is not expired (INC-12 calls `db.expire(t1)` as its Given 3). Never a second connection.
  - **Rolled back** (INC-13, DEC-15): inside the commit spy, `sp = db.begin_nested()` directly before the call; Then 1–2 inside the savepoint, then `sp.rollback()`, Then 3 (`reread`) and Then 4 (`commit_spy.call_count == 0`).
- **xfail markers:** strict → `strict=True, reason="BUG-NNN: <bug title>"`; non-strict (SYS-08, SYS-09, ACT-11, ACT-12, INH-18) → `strict=False` with the bug title and the reason it cannot be strict (physical row order, or the server's collation for ACT-11).
- **Probe:** `item_tags` has 0 committed rows in `marker_test`, so the absolute `count:` lines (INH-01: 1 row, INH-02 … 09: 0 rows) hold. The constraint names `item_tags_workspace_id_fkey` and `item_tags_created_by_fkey` exist (`pg_constraint`).

## xfail location (`--runxfail -rf`)
All 11 xfail cards are `Author: claude`; the local model got none. Each fails on the Then line its card names, with the value the card predicts:

| Card | Strict | Fails on | Actual |
|---|---|---|---|
| SYS-08 | no | Then 2 | `["Tool", "consumable", "Bolt"]` (insertion order) |
| SYS-09 | no | Then 2 | `[S2.id, S1.id]` (when it fails; see Stability) |
| SYS-10 | yes | Then 2 | the SELECT has no `ORDER BY` |
| ACT-11 | no | Then 2 | `[T3.id, T2.id, T1.id, T4.id]` ("alpha" before "Alpha", `English_United States.1252`) |
| ACT-12 | no | Then 2 | `[T2.id, T1.id]` (when it fails) |
| ACT-13 | yes | Then 4 | `order_part` is ` item_tags.is_system_tag DESC, item_tags.name` (Then 3 passes) |
| INC-11 | yes | Then 2 | `result.usage_count` 4, not 11 |
| DEC-13 | yes | Then 2 | 2, not 9 |
| DEC-14 | yes | Then 2 | 2, not 0 |
| INH-18 | no | Then 2 | `[T2.id, T1.id]` (when it fails) |
| INH-19 | yes | Then 2 | the SELECT has no `ORDER BY` (`… LIMIT … OFFSET …`) |

## Local-coder run
- **Model:** Qwen3.6-35B-A3B Q4_K_M, n_ctx 16,384, thinking off. Server started and stopped around each batch.
- **Totals (`item_tag.local-run.json`):** 70 cases (25 trial + 45 full run) — **62 accepted first try, 8 accepted after retries, 0 handed back in the end.** 2,282 s; 396k prompt / 15k completion tokens.
  - Trial (25): 21 first try, 4 after retry. INC-09 (attempt 3: "nothing written" as `== 0`, then an indentation error); INH-03, INH-09 (`w1` used in the `dao.create` dict but not requested). INH-07 was handed back once in batch 1 (missing `w1`, unused `before`, `# Then 1` after the `pytest.raises` block; all three correctly rejected) and accepted on the re-run in batch 2 after one retry (missing `w1`).
  - Full run (45): 41 first try, 4 after one retry — INH-04, INH-06, INH-11 (`w1` missing from the arguments again: the batch-2 sheet line did not stop it, though the runner's rejection fixed it every time) and INH-10 (unused `before`).
  - Root cause of every retry: the model (copying the `(db)` signature of exemplar INH-05, or the exemplar's `before` snapshot). No retry came from the sheet being wrong, the card or the spec. No wrong accept.
- **Sheet changes:** after batch 1 the `raises:` bullet (`# Then 1` above `with pytest.raises(...)`) and "never `== 0`" for "nothing written"; after batch 2 the line that a `dao.create` dict with `w1.id` needs `w1`. No change after the full run.
- **Finishing-step checks on the local tests:** compared with the as-delivered copy, all 70 are byte-identical (only moved into card order). `ruff check` and `ruff --select F841,F811` clean; an AST pass found no unused fixture argument. All 70 pass on every run. No local test errors; no local xfail (none were sent).

## Stability
- **Default plan, 10 whole-file runs + the coverage run:** never red (81 passed every time). The 6 strict xfails xfailed every time. SYS-08 and ACT-11 xfailed every time. The three "moved row" non-strict cards often XPASS: SYS-09 in 8 of 10 runs, ACT-12 and INH-18 in 9 of 10 (runs 3 and 4 had all 11 xfailed; the coverage run had 2 XPASS).
- **Forced sequential scan** (`PGOPTIONS="-c enable_indexscan=off -c enable_bitmapscan=off -c enable_indexonlyscan=off"`): 81 passed, 11 xfailed.
- **Forced index scan** (`PGOPTIONS="-c enable_seqscan=off -c enable_bitmapscan=off"`): 81 passed, 8 xfailed, 3 XPASS (SYS-09, ACT-12, INH-18). `PGOPTIONS` reaches the connection (`SHOW enable_seqscan` → `off`).
- **Why:** the Given's `description = "moved"` update is a HOT update (no indexed column changes), so the index entry still points at the old tuple chain and an index scan on `workspace_id` returns T1 first, which is the intended order; a sequential scan returns the new tuple version last. Which plan the planner picks varies with the table statistics (other agents use the same database). This is exactly why the cards are non-strict; the strict statement-recorder cards SYS-10, ACT-13, INH-19 are the stable alarms. No strict xfail and no pass card flipped.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage of `app/dao/item_tag.py` (24 statements, 4 branches, 0 partial):
`--cov=app.dao.item_tag --cov-branch --cov-report=term-missing`.

## Factories added
None (`tests/unit/factories.py` is unchanged).

## Notes for maintainers
- When **BUG-929** is fixed (`ORDER BY lower(name), id` in `get_system_tags_in_workspace`), SYS-10 XPASSes strictly → remove its marker, and the markers of SYS-08, SYS-09.
- When **BUG-930** is fixed (`ORDER BY is_system_tag DESC, lower(name), id`), ACT-13 XPASSes → remove the markers of ACT-11, ACT-12, ACT-13. The recorder checks the literal text `lower(item_tags.name)` (Spec gap 5); a fix with `func.lower(...)` renders that text, an `ILIKE`/collation-based fix would not.
- When **BUG-100** is fixed in `BaseDAO.get_by_workspace`, INH-19 XPASSes → remove the markers of INH-18, INH-19.
- When **BUG-931** is fixed (atomic `usage_count = usage_count ± 1` and the returned tag shows the stored value), INC-11, DEC-13, DEC-14 XPASS → remove their markers. INC-12 is the control that must keep passing.
- SYS-09 and ACT-11 rest on two tags whose names differ only in case; retire them if a unique index on tag names is ever added (item tag service FU-1 (c)).
- `LegacyAPIWarning` from `Query.get()` in `app/dao/base.py:136` (`remove`, INH-24) comes from the code, not the test.
