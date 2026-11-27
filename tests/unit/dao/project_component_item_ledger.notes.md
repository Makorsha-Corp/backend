# Execution notes — `app/dao/project_component_item_ledger.py`

> Cases: `tests/unit/dao/project_component_item_ledger.cases.md` (revision 3) · Tests: `tests/unit/dao/test_project_component_item_ledger.py` · Source commit: e48a092
> Result: 208 passed · 51 xfailed · 0 discrepancies · 0 errors — branch coverage 97% (line 121, dead)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/dao/test_project_component_item_ledger.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- Normal mode (full Claude, no local model). Every case ID is one test or one param id, each below `# [claude] <IDs>`, with a `# Then N` comment before each numbered Then's assertions (before the `with pytest.raises` for a `raises:` line).
- **Parametrized groups** (one param id per card; Given and Then identical, one input differs):
  - Card numbers 01–16 and 18–22 of CI, CO, TT, DR: the same card for each of the four lists, only the When's method differs → `test_pcil_list_NN__…[PCIL-CI-NN | PCIL-CO-NN | PCIL-TT-NN | PCIL-DR-NN]` with `list_call(fam, …)` (C1 / I1 / `"transfer_in"` / `T1…T5`, workspace W1 unless the card names another). The xfail markers are per param: BUG-640 for CI / CO, BUG-2462 for TT / DR. Each family's card 17 differs (another item / component / type / a time just after the end) and is its own test.
  - TT-25 … 33 (argument variant), TT-34 … 37 (stored variant), DR-36 / 37 and DR-38 / 39 (session zone), BAL-18 … 23, LE-12 … 17, TC-15 … 18 (where the newer / other row sits), BAL-27 … 29 and LE-21 … 23 (unknown or zero id).
- **Standing rows** → autouse fixture `s` (`SimpleNamespace`): `s.W0…W2`, `s.U1…U3`, `s.F0…F2` (`"Plant " + TAG`, TAG made once per test), `s.PJ0, PJ1, PJD` (soft-deleted), `PJ9`, components `s.C0, CL, C1, C2, CD, C9`, items `s.I0, IL, I1, I2, IR` (inactive), `I9`, built and flushed in the Conventions' order.
- **Given rows** → `ENTRY(s)` (the Conventions dict) and `entry(db, s, performed_at, **but)`; `id=HIGH_ID` is a marker that `entry` replaces with `high_id(db)` (max id or the sequence's `last_value` via `pg_get_serial_sequence`, + 1000001) when the row is built. `minute_rows(db, s, n, **but)` is the carded `rows = [… T1 + timedelta(minutes=k) …]`, each added and flushed. `costs(db, s, (at, type, amount), …)` writes TC Givens of the form "entry, but `transaction_type`, `total_cost`". The `UPDATE … SET notes …` and `SET LOCAL TimeZone …` steps are written verbatim.
- **Named checks** → `ids`, `idset`, `ledger_rows(db)` ("nothing written", all workspaces, taken before the recorder starts), `StatementRecorder(db)` (`before_cursor_execute` on the session's connection; `.sql` unpacks the one SELECT from the table, `.order_part`, `.lock_part`, `.written`, `.statements`).
- **DB errors** → `pytest.raises(DataError)` around `db.begin_nested()`; `ArgumentError` with no savepoint, inside the recorder (DR-34 / 35 assert `statements == []`).
- **BAL-11 … 14** add `db.expire_all()` between the Given and the When: without it the identity map hands back the inserted Python `Decimal("2.125")`, not the stored value the card checks ("stored as … reads back …"). Setup only; no check changed.
- **xfail reasons**: `"BUG-n — revisit after launch (owner 2026-11-10)"` for BUG-640, 2462, 2463, 2464, 654; plain `"BUG-645"`, `"BUG-100"`.
- Mocks: none.

## Checks
- `--runxfail` with my own `failson_d.py` (scratch; maps the failing line to its `# Then N` and prints the exception type): 51 failed, 208 passed. Every strict card fails at its card's Then: CI / CO / TT / DR-21, BAL-17, LE-10 at Then 4 (no `, …id DESC`); INH-03 at Then 2 (no `ORDER BY`); DR-38 … 41, DR-46 … 49 at Then 1; TC-09 … 14, 28, 29 at Then 2 (the plain sum). The 17 PF cards fail with `AttributeError: … no attribute 'get_by_performer'` at the call — PF-11 / 12 inside Then 1's `raises` block, the others on the When line just before `# Then 1` (the card's "Fails today on: Then 1 (the call raises AttributeError)"). The 11 non-strict tie cards fail at Then 2 in the default plan.
- Reference plugin `ref_pcil.py` (scratch, `-p ref_pcil`; replaces the methods on the DAO class in-process: `ORDER BY performed_at DESC, id DESC`, aware bounds to naive UTC with `None` passed through, `get_by_performer`, net cost by exact type, `get_by_workspace ORDER BY id`): with `--runxfail` **259 / 259 pass**.
- ruff check (header `noqa`: SIM117, DTZ001) and ruff format clean; `--select F841,F811` clean. LF.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 121 (`get_by_order`) | dead | Entries of one order, oldest first; no caller; ruled remove (spec Q2, Not specified; `docs/testing/dead-code-removal-checklist.md`). |

Otherwise 100% line and branch coverage (`--cov=app.dao.project_component_item_ledger --cov-branch`, private `COVERAGE_FILE`).

## Factories added
None (local builders only).

## Stability
| Run | Passed | xfailed | xpassed (non-strict) | Not as designed |
|---|---|---|---|---|
| Default, runs 1–4 | 208 | 51 | 0 | 0 |
| `PGOPTIONS=-c TimeZone=America/New_York` | 208 | 51 | 0 | 0 |
| `PGOPTIONS=-c TimeZone=Asia/Dhaka` | 208 | 51 | 0 | 0 |
| `enable_seqscan=off` | 208 | 51 | 0 | 0 |
| index, bitmap and index-only scans off | 208 | 45 | 6 (CI / CO / TT / DR-19, BAL-16, LE-09) | 0 |
| `enable_sort=off` | 208 | 51 | 0 | 0 |
| `--runxfail` | 208 | — | — | 51 failed, each where its card says |
| `--runxfail -p ref_pcil` | 259 of 259 | — | — | 0 |

Under a forced sequential scan the physical order of the tied rows happens to be the intended one, so six non-strict tie cards pass. That is the case they are non-strict for; no pass card moved.

## Notes for maintainers
- BUG-640 fixed → CI-21, CO-21 XPASS (strict): remove their markers and those of CI / CO-19, 20. BUG-2462 → TT / DR-21 (+ 19, 20). BUG-2463 → BAL-17, LE-10 (+ BAL-16, LE-09). BUG-2464 → DR-38 … 41, 46 … 49. BUG-654 → TC-09 … 14, 28, 29. BUG-645 → all 17 PF. BUG-100 → INH-03 (+ INH-02).
- The order alarms look for the exact text `project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC` in the SQL; a fix written with an alias or a different column order fails them.
- DR-34 / 35 pin today's `ArgumentError` for a `None` bound; the BUG-647 fix retires R3 and these two cards change with the spec (Deferred table).
- The parametrized list tests share one body for four methods: a change to one list's card must split that param out into its own test.

## Revision history
- **Revision 3 (2026-11-10):** patched, not regenerated (`project_component_item_ledger.verify.md` finding 1). PCIL-CI-22, CO-22, TT-22, DR-22 (one parametrized test) gain Then 10 and BAL-32, LE-26 gain Then 9: `"FOR UPDATE" not in rec.sql`. PF-17 Then 8 replaces the vacuous `rec.lock_part == ""` with the same check. Every other test kept as it was. Re-run: 3 plain runs 208 passed / 51 xfailed each; `--runxfail` the 51 xfails fail at their cards' Thens as before (PF-17 still on the When call, AttributeError, before Then 1); reference plugin `ref_pcil` with `--runxfail` 259 / 259; coverage 97% (line 121 dead, unchanged); ruff check and format clean; LF.
  **Lock-everything variant** (`omde\D\lockall_d.py`, stacked on `ref_pcil`, `--runxfail`: every whole-row read of `project_component_item_ledger` gets `FOR UPDATE`): exactly 7 failed, CI-22, CO-22, TT-22, DR-22, PF-17, BAL-32 and LE-26, each on its `"FOR UPDATE" not in sql` line; 252 passed. The aggregate total-cost query is not whole-row and is left unlocked (Postgres refuses `FOR UPDATE` with aggregates).
