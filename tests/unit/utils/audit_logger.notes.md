# Execution notes — `app/utils/audit_logger.py`

> Cases: `tests/unit/utils/audit_logger.cases.md` (revision 4) · Tests: `tests/unit/utils/test_audit_logger.py` · Source commit: e48a092
> Result: 45 passed · 20 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_audit_logger.py -q -p no:cacheprovider --cov=app.utils.audit_logger --cov-branch --cov-report=term-missing`

## How the tests are built
- **W1 / W2 / U1** → fixtures `w1`, `w2`, `u1` (`make_workspace`, `make_profile` from `tests/unit/factories.py`). The profile has no membership row. The FK only needs a `profiles` row.
- **MIN** → helper `MIN(w1, u1, **overrides)` returns the minimal kwargs dict. For AUD-L-22/23, which have no W1 or U1, the kwargs are written inline.
- **Clock** → helper `call(db, **kw)` wraps every `log_financial_audit` call in `patch("app.utils.audit_logger.utcnow", return_value=NOW)`, so only L cases are patched. The pure CD/X tests have no mock at all.
- **Re-read** → `ws_rows` / `ws_count` / `only_row` (`expire_all` then a fresh `SELECT`, ordered by id). `only_row` also asserts "exactly 1 row".
- **SQL NULL checks** (AUD-L-01, L-03, L-05) → `is_null(db, id, column)` runs raw `SELECT <col> IS NULL`.
- **Unknown id** → `unknown_id(db, Model)` = `max(id) + 1000`.
- **FLUSH-ERR** (AUD-L-07/08/09, L-22, L-23) → `pytest.raises(...)` wraps `with db.begin_nested(): call(...)`. The row count is re-read after the savepoint has rolled back.
- **xfail cases with a flush error today** (AUD-L-11..19, L-21) → the call is inside `with db.begin_nested():`, as Conventions says. The assertions after it are unchanged.
- **Validation errors** (AUD-L-24/25/26/28) → one parametrized test with ids `AUD-L-24`, `AUD-L-25`, `AUD-L-26`, `AUD-L-28`. It checks `len(db.new) == 0` and W1 count 0. AUD-L-07/08/09 are parametrized the same way.
- **AUD-L-29** → an explicit `sp = db.begin_nested()` ... `sp.rollback()`.
- **Test-only types** (`Status`, `Color`, `Level`, `Money`, `Custom`, `RelList`, `MyStr/MyInt/MyFloat`, `U`) are defined at module level, exactly as Conventions lists them.
- **"fails today on" check:** with `--runxfail`, each xfail fails at the named point. L-11/12 fail with `DataError` (varchar 255/45). L-13..16, L-18, L-19 and L-21 fail with `StatementError` wrapping `TypeError`. L-17 fails with `DataError` ("invalid input syntax for type json", the NaN token). X-06/07/08 get float values. X-15/X-18 have the key missing. X-16 fails on `type is Color`. X-19..X-23 fail on the unconverted value.
- **Flakiness:** the file was run 3 times with identical results (45 passed, 20 xfailed).

### AUD-X-05 `Counter` property (revision 3)
The property increments `reads` and returns the new count, so every read gets a distinct value. The test asserts `obj.reads >= 2`, `result == {"n": obj.reads}` (the stored value is the LAST read) and `len(result) == 1`. Today's code reads each field twice (`hasattr` + `getattr`), so `["n","n"]` makes 4 reads and stores 4. A first-read-wins implementation (`setdefault`) would store 2 and fail. The assertion does not depend on how many reads the implementation makes. (Resolves verify.md Finding 1; the r1 "1 then 2" design could not tell the two apart.)

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (35 stmts, 16 branches, 0 missed).

## Factories added
None (batch mode — `tests/unit/factories.py` not edited). No new builders were needed. Candidates for promotion later: the `unknown_id(db, Model)` and `is_null(db, id, column)` raw-SQL helpers are generic and would help other modules.

## Notes for maintainers
- When BUG-142 is fixed, AUD-L-13..19, L-21, X-19, X-20, X-21 and X-23 will XPASS (strict → fail); remove their markers. AUD-L-20 and X-22 must stay green.
- When BUG-141 is fixed, AUD-X-06/07/08 XPASS. AUD-X-09 (regression) stays green, because `Decimal(str("2000.00")) == Decimal("2000")`.
- When BUG-143 is fixed, AUD-X-15/16/18 XPASS. AUD-X-17 stays green. Note AUD-X-18 also needs the BUG-141 Decimal-string format.
- When BUG-144 is fixed, AUD-L-11/12 XPASS.
- BUG-140 has no test here (deferred to the manager/service specs). AUD-L-02 covers the module-level half.
- AUD-L-17: Postgres `json` rejects `NaN` at the DB (DataError), not in Python. After the fix this depends on `NaN` being converted before `json.dumps`.
- The xfail tests call inside `begin_nested()` so that today's flush error rolls back only the savepoint. Keep this when editing, or teardown will hit an aborted transaction.

## Revision history
- r1 (cases revision 2): initial implementation of all 65 cases.
- r1 re-check (2026-09-29, batch run): cases file unchanged (revision 2), source commit unchanged (e48a092); all 65 case IDs present; re-ran 3× (2 plain + 1 coverage): 45 passed · 20 xfailed each time, 100% branch coverage. No test changes.
- r2 (cases revision 3, 2026-09-29): verify.md Finding 1 (case-weakness, fixed by the case designer in revision 3). Rewrote only `test_aud_x_05__duplicate_field_later_read_wins`: the property now returns its running read count and the test asserts `obj.reads >= 2`, `result == {"n": obj.reads}`, `len(result) == 1`. No other tests changed; no Retired IDs. Re-ran 3× (2 plain + 1 coverage): 45 passed · 20 xfailed each time, 100% branch coverage.
- r3 (cases revision 4, 2026-09-29): cases file unchanged in content (revision 4 is a re-run with no added, changed or retired IDs); source commit unchanged (e48a092). The only edit is the module docstring's revision number, which now says revision 4 (this resolves the cosmetic observation in verify.md). All 65 case IDs are present. Ran 3 times (2 plain + 1 coverage): 45 passed · 20 xfailed each time, 100% branch coverage (35 stmts, 16 branches, 0 missed). No discrepancies.
