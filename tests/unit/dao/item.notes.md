# Execution notes — `app/dao/item.py`

> Cases: `tests/unit/dao/item.cases.md` (revision 3) · Tests: `tests/unit/dao/test_item.py` · Source commit: e48a092
> Result: 77 passed · 33 xfailed · 0 discrepancies · 0 errors — branch coverage 97%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_item.py -q -p no:cacheprovider --cov=app.dao.item --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → helpers** (top of the test file, each commented with its convention):
  - W1/W2 → fixtures `w1`, `w2` (`make_workspace`); W404 → fixture `w404` (max workspace id + 1000).
  - Item shorthand → `mk(db, ws, name, unit="pcs", sku=, desc=, nn=, deleted=)`: one insert + flush per item, so ids ascend in insertion order. `name_normalized` defaults to `normalize_item_name(name)`; the S section always passes `nn=` explicitly.
  - Tags → `mktag(db, ws, name, active=)` (unique `tag_code` from a counter), `tag(db, item, t, ws_id=)` for assignments (default = item's workspace; `ws_id=w2.id` for the cross-workspace rows of AF-19/AF-39). UNKNOWN_TAG → `unknown_tag(db)` (max tag id + 1000).
  - `N(k)` → `N(k)` (base-26 three-letter strings, `N(1)="aaa"`).
  - Actions → `lst` (limit=100 default), `af_ids` (AF section: sorted ids), `cnt`, `units`, `similar`; `pairs()` turns similar rows into `(item id, score)`, compared with `pytest.approx(x, abs=1e-4)`.
  - Session clean → `assert_session_clean` (`db.new`, `db.dirty`, `db.deleted` empty).
  - SQL statement counter → `StatementCounter(engine)`, a `before_cursor_execute` listener on the session-scoped `engine` fixture, attached only around the call (S-05..08).
  - Trigram preconditions → `sim(db, a, b)` runs `SELECT similarity(:a, :b)` before asserting S-10, S-11, S-12, S-27.
  - Database-error cases (L-10, L-11, S-17) → `pytest.raises(DataError)` wrapping `with db.begin_nested():`; the context manager rolls the savepoint back on the error; `snapshot()` (`expire_all` + re-query of W1 items as `(id, name, unit, is_active)`) is compared before vs after.
- **Mocks:** none (spec: no externals; no time, no races).
- **Parametrized:** L-10/L-11, S-03/S-04, S-06..S-08, S-21/S-22. (S-05 has its own test since revision 3, because it adds a `type(result) is list` assertion the others do not have.) Each case ID is its own `pytest.param` id.
- **S-01 rows (R10):** the DAO returns `sqlalchemy.engine.Row` objects. Since revision 3 the case asserts exactly that: `isinstance(row, Row)` (imported from `sqlalchemy.engine`), `len(row) == 2`, indexing, and `item, score = row` unpacking. Per the cases file there is deliberately no `isinstance(row, tuple)` assertion in either direction.
- **Mid-string search (AF-46..48):** the search text sits in the middle of the sku (`XX-ZETA-YY`), unit (`bigzetaroll`) and tag name (`Hot-dip galvanized`), and no other field of A contains it, so a "starts with" or "ends with" `ILIKE` pattern on that column would fail the test (verify findings 1–3, mutants 46/48/51).
- **xfail honesty:** verified with `--runxfail`: each of the 33 xfails fails on the assertion named in "fails today on" (e.g. AF-33/34 and CNT-08 raise `ValueError: invalid literal for int()` at `app/dao/item.py:53`; S-11 returns 0 rows; S-25 starts with "delta" and includes "echo").

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 89 | dead | body of `ItemDAO.search_by_name_in_workspace` (Not specified: dead code, to be removed — Q4) |
| 116 | dead | body of `ItemDAO.get_active_items_in_workspace` (Not specified: dead code, to be removed — Q4) |

## Factories added
None. Item and tag builders are local to this module's tests. Move `mk`/`mktag`/`tag` into `tests/unit/factories.py` once a second test file needs items or tags.

## Notes for maintainers
- **ITEM-S-25 / S-26 (BUG-018)** depend on today's un-tie-broken sort returning tied rows in storage order. They stayed xfailed in 3 of 3 runs, but a different plan (parallel scan, vacuum) could make them XPASS or fail in a different place. Strict xfail makes that surface as a failure.
- **When a bug is fixed**, its strict xfails will XPASS → remove the marker: BUG-012 (AF-33/34/35, CNT-08), BUG-013 (AF-26..29, 38, 41..44), BUG-014 (AF-17/18), BUG-015 (AF-37), BUG-017 (AF-11/12/13/45, U-04/05/06/07/11/12), BUG-018 (S-25/26), BUG-033 (L-04/13/14/15), BUG-034 (S-11).
- **After the BUG-033 fix:** L-01, L-05, L-06, L-07, L-09 use names whose alphabetical order equals id order, so they stay green.
- Test data uses no digits except where a case allows them (AF-26/27/29/30/33/34, S section), so the all-digit id match cannot interfere. `_mk_units` names items `Item aaa`, `Item aab`, … for that reason.
- The number of statements counted in S-05..08 depends on no autoflush happening inside the call; setup rows are flushed by `mk`, so there is nothing pending.

## Revision history
- **Cases revision 3** (this run): added ITEM-AF-46 (search mid-sku), ITEM-AF-47 (search mid-unit), ITEM-AF-48 (search mid-tag-name) for verify findings 1–3 (surviving mutants 46, 48, 51). Rewrote ITEM-S-01 to the reworded case: `type(result) is list`, length 1, row is a `sqlalchemy.engine.Row`, `len(row) == 2`, `row[0]` is `Item` A, `row[1]` is a `float` equal to 1.0, tuple unpacking (verify finding 4 / spec G7, R10). Split ITEM-S-05 out of the S-05..08 parametrized test because it now also asserts `type(result) is list`; S-06..08 unchanged. No other tests changed; no retired IDs. Result 74 → 77 passed, 33 xfailed, coverage unchanged at 97%. Three runs identical.
- **Cases revision 2:** initial implementation (74 passed · 33 xfailed · 97%).

## Fix round after verification round 2 (2026-10-17)
- ITEM-S-25 and ITEM-S-26 (BUG-018) rest on physical row order: markers now `strict=False`, bodies unchanged.
- New ITEM-S-28 (strict, statement recorder): the similar-name query must carry `lower(items.name)` and `items.id` after the score in its `ORDER BY`. Fails today on Then 2.
- When BUG-018 is fixed, remove the markers of S-25, S-26 and S-28 together.
- Counts: 111 tests · 77 passed · 34 xfailed.
