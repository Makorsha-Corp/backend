# Execution notes — `app/integrations/sslcommerz/mock_client.py`

> Cases: `tests/unit/integrations/mock_client.cases.md` (revision 2) · Tests: `tests/unit/integrations/test_mock_client.py` · Source commit: e48a092
> Result: 127 passed · 65 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/integrations/test_mock_client.py -q -p no:cacheprovider --cov=app.integrations.sslcommerz.mock_client --cov-branch --cov-report=term-missing`

## How the tests are built
- **Pure module**: no `db` fixture, no factories, no externals mocked, no time patching. Every case asserts on the return value or the raised exception.
- **Settings**: the autouse fixture `mock_settings` monkeypatches `settings.SECRET_KEY = K1`, `BACKEND_BASE_URL = "http://api.test:9000"`, `API_V1_STR = "/api/v9"` on `app.core.config.settings`. It returns the `monkeypatch`, so cases that switch keys (SIGN-02, SIGN-08, BVI-07, K2-minted tokens) call `set_key(mock_settings, …)` and the change is undone after the test.
- **Conventions → code** (all at the top of the test file, each one commented): `H`, `ENC`, `TOK`, `T1`/`T2`, `P1`/`S1`, `mint`, `INV`, `UNATT`, `VKEY`, `REQ` (with `REQ_KW` copied from `client.cases.md`), `SK`, `MAL` (seven `pytest.param`s), `NAS`, `BAD_AMT`, `FORM`, `F1`, and (revision 2) `E` (with a module-level guard that it is 124 chars ending `fQ==`, which the NCB/MD inputs depend on), `MD_OK`, `MD_REJ`, `NCB` (= `NCB_P1`, the four rows built from P1, plus the `-`→`+` and `_`→`/` rows), `NCJ`. `A`/`B`/`C` are fresh `MockSSLCommerzClient()` instances created inside each test.
- **Shared invalid-token inputs**: `DEC_02_INPUTS`, `DEC_03_INPUTS`, `DEC_04_INPUTS` are lists of `(instance, monkeypatch) -> str` builders. Some inputs need the live key or an instance (the tampered token, the K2-minted token). MOCK-VAL-05 parametrises over all three lists plus `MD_REJ`, which is what its case asks for. `MD_OK`, `MD_REJ` and `NCB` are builders of the same `(instance, monkeypatch) -> str` shape: the `-`/`_` NCB rows mint on the given instance. MOCK-QRY-17 uses `MD_OK + NCB_P1`, as its case asks. `_other_key` mints a T1 token under K2 and then restores K1. MOCK-QRY-10 and MOCK-QRY-12 reuse it.
- **Parametrised**: 69 cases give 192 test items. Param ids name the variant (for example `extra-segment`, `hint-None`, `status-removed`).
- **xfail honesty** (checked with `--runxfail`): DEC-05, VAL-06 and QRY-14 fail on `KeyError` or `TypeError` (non-subscriptable, or comparing strings with non-ASCII). VAL-07 and QRY-14[BAD_AMT] fail on `decimal.InvalidOperation`. QRY-04/05/09/11/16 fail on the equality assertion because the result is `UNATTEMPTED`. QRY-12 fails on equality because the result is `INVALID_TRANSACTION`. VSIG-09 fails on `TypeError`. DEC-07/09 fail on `assert {<decoded payload>} is None`. VAL-11 and QRY-17 fail on equality because the result is a VALID `ValidationResult`. Every one matches the "fails today on" column.
- **Stability**: 3 runs, identical outcome each time (127 passed, 65 xfailed).

## Discrepancies
None. DISCREPANCY-1 (revision 1) is resolved: the spec logged it as BUG-583, and the cases file moved the `extra-segment` input out of MOCK-DEC-03/VAL-05 into the xfail(BUG-583) cases MOCK-DEC-07, VAL-11 and QRY-17.

## Coverage gaps
None. Branch coverage is 100% (50 statements, 12 branches).

## Factories added
None. The batch-mode rules forbid edits to `tests/unit/factories.py`, and nothing here touches the database. Worth promoting later: `REQ_KW`/`REQ` now appears in both `test_client.py` and `test_mock_client.py`. A shared `tests/unit/integrations/_helpers.py` could hold it, together with `H`/`ENC`/`TOK`/`mint`, if the payment-manager tests need to mint mock tokens.

## Notes for maintainers
- **When BUG-580 is fixed** (the mock records minted outcomes): QRY-04/05/09/11/12/16 will XPASS, so remove their markers. QRY-02/03/10/13/15 and VAL-10 must keep passing. They guard per-instance records, and they check that `validate` and hint lookups record nothing.
- **When BUG-581 is fixed**: DEC-05/06, VAL-06/07 and QRY-14 will XPASS, so remove their markers. **When BUG-582 is fixed**: VSIG-09 will XPASS, so remove its marker.
- **When BUG-583 is fixed** (strict canonical decoding, exactly one `.`): DEC-07/09, VAL-11 and QRY-17 will XPASS, so remove their markers. DEC-08, DEC-10, VAL-05[MD_REJ rows] and VAL-12 must keep passing. After the fix, mutants that change only the split point (`rsplit(".", 1)` → `rsplit(".", 2)`, verify #43/#59) are equivalent (spec note).
- BVI-02 relies on those exact tran_id strings producing `-` / `_` and `=` padding in the base64. If the payload layout changes (key order, extra fields), re-check it.
- **TODO-001 (user direction, 2026-09-29)**: the mock will be removed or upgraded later. Until then it stays as is. If it is kept, it should be enable-able only in non-production, and default off. When that happens, retire or rewrite this test file together with `mock_client.spec.md` / `.cases.md`. The file docstring carries the same TODO.

## Revision history
- **Revision 2 (cases rev 2, 2026-09-29)**: Existing tests are unchanged, except for two things. MOCK-DEC-03 lost its `extra-segment` param (DISCREPANCY-1, now BUG-583) and gained the two inputs that rev 2 lists and rev 1 did not implement: `"!!!.abc"` and `incorrect-padding` (`E[:-2] + "." + S1`). MOCK-VAL-05 now also parametrises over `MD_REJ`. New tests: DEC-07 (xfail BUG-583), DEC-08, DEC-09 (xfail BUG-583), DEC-10, VAL-11 (xfail BUG-583), VAL-12, QRY-17 (xfail BUG-583). The `BUG_583` reason constant was added and the `DISCREPANCY_1` constant was removed. Result went from 111 passed / 45 xfailed to 127 passed / 65 xfailed, with branch coverage still 100%. Retired IDs: none.
- **Re-run (2026-09-29, batch executor pass)**: No code changes. Checked that all 69 case IDs map to exactly one test each and that the 16 xfail(strict) markers match the 16 bug cases. Re-ran 3 times: 127 passed, 65 xfailed every time. With `--runxfail`, exactly the 65 xfail items fail, each on its designed reason. Branch coverage is 100%. No decisions were needed.
