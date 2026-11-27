# Execution notes — `app/services/account_service.py`

> Cases: `tests/unit/services/account_service.cases.md` (revision 3, 2026-11-22) · Tests: `tests/unit/services/test_account_service.py` · Source commit: e48a092
> Result: 81 passed · 43 xfailed · 0 discrepancies · 0 errors — branch coverage 93% (every miss is dead code, see Coverage gaps)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_account_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.account_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows** — fixture `s`: `s.W0`, `s.W1`, `s.W2` (`make_workspace` three times, so ids ascend), `s.U1` (acts), `s.U2` (built the Given rows).
- **Given rows** — `account(db, s, **but)`, `tag(db, s, **but)`, `link(db, s, a, t, **but)`, `invoice(db, s, a, state, **but)` with `STATES` holding the five invoice states of Conventions; `gone(s)` is the "gone" column set (`account(db, s, **gone(s))`). Each builder flushes.
- **Commit point** — `commit_point(db)` runs `db.commit()` (releases a savepoint only) and returns the "nothing written" snapshot `written(db)`: row counts of `accounts`, `account_tag_assignments`, `financial_audit_logs` (all workspaces) plus `(id, usage_count)` of every `account_tags` row. `snap(db, id)` is "unchanged(A)" (the eight listed columns, after `expire_all`), taken right after the commit point.
- **X** — `mk_x(db)` after the commit point; `x_gone(db, x_id)`.
- **committed:** lines run `db.rollback()` once, then re-read with `reread` / `audit` / `links` / `_count` (fresh queries after `expire_all`).
- **Patches** — exactly as Conventions: `spies`, `failing_commit`, `failing_refresh` (on `db`), `mgr_raises(m, E)` = `patch.object(svc.account_manager, m, side_effect=E)`, `patch.object(mod.account_invoice_manager, "list_accounts_hub_page", fake)` (H-01), `patch.object(svc, "get_account_with_tags", ...)` (A-12 … A-14), and the one race simulation `hidden_deleted()` (D-12). No clock patch: no card asserts a time stamp's value.
- **Statement recorder** — `record_sql(db)` listens to `before_cursor_execute` on the session's connection. G-12 selects the statements containing `FROM account_tags` (exactly one, then `ORDER BY` in it); D-08 checks no statement contains `FOR UPDATE`.
- **xfail cards whose call does not exist yet** (C-13, G-09, L-07, U-13, N-07, D-28): the call is written as the card shows, under a `# Fails today here: … (TypeError)` comment directly before `# Then 1` (the style of `test_account_manager.py`).
- **ASV-D-10** wraps the When in `pytest.raises(Exception)` as the card says (`# noqa: B017`).
- File-level `# ruff: noqa: SIM117, FURB157` — nested `with` as Conventions prescribe; `Decimal("0")` written as the cards write it. `T0` carries `# noqa: DTZ001` (naive, as the DateTime columns).

## Verification runs
- `--runxfail` with a Then-line locator plugin (scratch `svc1e/asvc/thenline.py`, `compare.py`): all 43 strict xfails fail, each in the Then block the card's "Fails today on" names (37 in that `# Then N` block; the 6 TypeError cards at the `# Fails today here` call, which is their card's Then 1 reason). 0 mismatches.
- Reference plugin (scratch `svc1e/asvc/refplugin.py`, loaded in process with `-p refplugin --runxfail`, nothing on disk under `app/` changed) implementing BUG-2986 (was cited as BUG-124), 140, BUG-2987 (was BUG-629), 862, 863, 865, 871, 873, 874, 876, 878, 879, 1486, 2982, 2984 as the spec states them: **116 passed**.
- Three plain runs: 81 passed, 43 xfailed each time (rev 3) — no flakiness.
- `ruff check` and `ruff format --check`: clean; LF line endings.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 92–95 | dead | `AccountService.get_account` — no caller; spec Not specified (Q5), in the dead-code removal checklist. |
| 357 | dead | `update_account`: "manager returned nothing" → `NotFoundError`; the manager never returns `None` (Q4). |
| 366–367 | dead | `update_account`'s `except NotFoundError` — reachable only through line 357 (Q4). |

## Factories added
None.

## Notes for maintainers
- When a bug is fixed, its xfail tests will XPASS (strict → fail): remove the marker. BUG-2984 and BUG-876 come together in practice: D-13 … D-15 are marked BUG-876 only (as their cards), but they also check the `errors` list, so they pass only once BUG-2984's blocker list is in as well.
- BUG-124 and BUG-629 were used as precedent IDs here, but their register rows describe other modules. Re-cited on 2026-11-22 (describer, via the coordinator): BUG-124 → BUG-2986 (U-04, U-08…U-11, D-09, D-11, D-12, D-26), BUG-629 → BUG-2987 (C-09, C-12, U-07). The xfail reasons quote the BUG-2986 / BUG-2987 register titles. The cases file still cites BUG-124 / BUG-629 until the describer's card edit lands; then the two agree again.
- D-19 and D-22 insert invoices with explicit ids (900000001/2, 900000011/12). A concurrent run inserting the same ids waits on the other transaction's row lock until it rolls back; it does not fail.
- The "nothing written" snapshot reads every `account_tags` row of the database; other agents' uncommitted rows are invisible to it, so it is stable under parallel runs.
- No new bug found (BUG-2972, BUG-2973 unused).

## Revision history
- 2026-11-22 — cases rev 3 (verifier findings 1–3) and bug re-citation. New tests ASV-L-09, T-09, M-03 (the six tag-entry keys and stored values), L-10, T-10, H-05 (default limits 100 / 100 / 50, rows inserted with `add_all` through the new unflushed-row helpers `account_row` / `link_row`), N-08 (other ValueError → 422, X gone), N-09 ("Not Found" → 422). D-08 Then 1 now compares upper-cased (`all("FOR UPDATE" not in t.upper() …)`). Constants `BUG_124` → `BUG_2986`, `BUG_629` → `BUG_2987` with the register titles; the docstring citations of those 12 tests and C-02's "companion of" note follow. Result: 3 runs 81 passed / 43 xfailed, 93% branch (gaps unchanged, dead code); `--runxfail` 43/43 on the named Then line; reference plugin + `--runxfail` 124 passed; ruff clean, LF.
