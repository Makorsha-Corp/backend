# Execution notes — `app/dao/miscellaneous_project_cost.py`

> Cases: `tests/unit/dao/miscellaneous_project_cost.cases.md` (revision 3) · Tests: `tests/unit/dao/test_miscellaneous_project_cost.py` · Source commit: e48a092
> Result: 74 passed · 13 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_miscellaneous_project_cost.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- Normal mode (full Claude, no local model). One test per card, in card order, each below `# [claude] <ID>`, with a `# Then N` comment before each numbered Then's assertions (before the `with pytest.raises` for a `raises:` line).
- **Standing rows** → autouse fixture `s` (a `SimpleNamespace`): `s.W0 … s.W2`, `s.U1 … s.U3`, `s.F0 … s.F2`, projects `s.PJ0, s.PJA, s.PJ1, s.PJB, s.PJD` (soft-deleted), `s.PJX`, components `s.C0, s.CA, s.C1, s.C2, s.CB, s.CDL, s.CX`, built and flushed in the Conventions' order so the id inequalities hold. The two schema-only cards (OQ28-03, 04) take no fixture; the autouse rows are still built.
- **Given rows** → `cost(db, s, **but)` (Conventions "cost"), `component_only(db, s, C, **but)`, `unlinked(db, s, **but)`; each inserts and flushes one row. `_create(db, s, amount, name=…, **links)` is the dict `create` of the INH / OQ28 cards (PJ1 unless a link is given). `dump(schema, s)` = `{**S.model_dump(), "workspace_id": W1.id}`.
- **seqscan**, **Dhaka** → `seqscan(db)`, `dhaka(db)` (the three / one `SET LOCAL` lines, verbatim).
- **Named checks** → `ids`, `idset`, `reread(db, id)` (expire, then `db.get`), `cost_count(db, *where)`, `total_costs(db)` ("nothing written", all workspaces).
- **Statement recorder** → `StatementRecorder(db)` (a `before_cursor_execute` listener on the session's connection). `.sql` unpacks the one SELECT from `miscellaneous_project_costs` (fails if there is not exactly one); `.order_part` = text after the first `ORDER BY`, before `LIMIT`; `.lock_part`, `.written` as Conventions.
- **DB errors** → `with pytest.raises(DataError | IntegrityError) as exc:` around `with db.begin_nested():`, then the `pgcode` assert; the session stays usable for the count.
- **xfail markers** → `xfail_bug("BUG-n", strict=…)`; the reason carries `(revisit after launch)` for the BUG-2460 / BUG-2461 cards (Conventions "Revisit after launch"); INH-01 (BUG-100) has no tag. Pass cards tagged Revisit carry `revisit after launch (owner 2026-11-10)` in the docstring.
- **GP-25** adds `db.expire_all()` between the Given and the When: without it the identity map hands back the Python `Decimal("2.125")` the test inserted, not the stored `2.13`. The card checks stored amounts ("stored amounts are returned as exact Decimal values"), so the expire is setup, not a changed check.
- Mocks: none (Externals: None).

## Checks
- `--runxfail` with my own `failson_d.py` (scratch, maps the failing line to its `# Then N`): all 9 strict cards fail at **Then 2**, as their "Fails today on" lines say (GP-28, GC-24, INH-01 on `"ORDER BY" in sql`; GP-29 … GP-34 on the `idset == {…}` with the component cost missing). The four non-strict order cards fail at Then 2 too, except that GP-27 sometimes passes (below).
- Reference plugin `ref_mpc.py` (scratch, `-p ref_mpc`, replaces `get_by_project` / `get_by_component` / `get_by_workspace` on the DAO class in-process: component match through a `project_components` sub-select of the same workspace, `ORDER BY id` before paging): with `--runxfail` **87 / 87 pass**.
- ruff check (file header `noqa`: SIM117, DTZ001, FURB157, RUF015 for the carded `with` nesting, naive T0 / T1, `Decimal("0")` and the `[…][0]` lookups) and ruff format: clean. Line endings LF.

## Discrepancies
None.

## Coverage gaps
None — 100% line and branch coverage (`--cov=app.dao.miscellaneous_project_cost --cov-branch`, private `COVERAGE_FILE`). Inherited `BaseDAO` methods are measured by `tests/unit/dao/test_base.py`.

## Factories added
None (local builders only).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–3 | 74 | 13 / 12 / 13 | 0 / 1 (GP-27) / 0 | 0 |
| Default, 4 more runs | 74 | 13, 13, 12, 13 | GP-27 once | 0 |
| `PGOPTIONS=-c TimeZone=America/New_York` | 74 | 13 | 0 | 0 |
| `--runxfail` | 74 | — | — | 13 failed, each at its card's Then 2 (GP-27 passed once of two) |
| `--runxfail -p ref_mpc` | 87 of 87 | — | — | 0 |

GP-27 (pages of one after an edit) passes now and then: the updated row's new version can land in a slot freed by pruning earlier tests' rolled-back rows, so the heap order happens to match id order. That is the physical-order case the card is non-strict for; not a discrepancy.

## Notes for maintainers
- When BUG-2460 is fixed, GP-28 / GC-24 XPASS and fail: remove their markers and those of the non-strict GP-26, GP-27, GC-22, GC-23. BUG-2461 fixed → GP-29 … GP-34 XPASS. BUG-100 fixed → INH-01.
- GP-13 / GC-11 assert `"projects." not in sql`; a BUG-2461 fix that joins or sub-selects `project_components` still passes (`project_components.` does not contain `projects.`), but GC-11 also requires `"project_components." not in sql` for the component list, so the fix must leave `get_by_component` a single-table query.
- GP-33 builds a W2 component under a W1 project on purpose (invalid data, HR-16); the fix must filter the component's workspace.

## Revision history
- **Revision 3 (2026-11-10):** patched, not regenerated (`miscellaneous_project_cost.verify.md` findings 1–2). MPC-GP-13 Then 3 and MPC-GC-11 Then 4 now check `"FOR UPDATE" not in rec.sql` instead of the vacuous `rec.lock_part == ""` (Postgres prints the lock clause last, so the text after it is empty with a lock as well). MPC-GP-25 unchanged: it already ended its Given with `db.expire_all()`, which the card now states. Every other test kept as it was. Re-run: 3 plain runs 74 passed / 13 xfailed each; `--runxfail` the 13 xfails fail at Then 2 as carded; reference plugin `ref_mpc` with `--runxfail` 87 / 87; coverage 100%; ruff check and format clean; LF.
  **Lock-everything variant** (`omde\D\lockall_d.py`, stacked on `ref_mpc`, `--runxfail`: every whole-row read of `miscellaneous_project_costs` gets `FOR UPDATE`): exactly 2 failed, GP-13 (Then 3) and GC-11 (Then 4), both on the `"FOR UPDATE" not in sql` line; 85 passed.
