# Execution notes — `app/integrations/sslcommerz/client.py`

> Cases: `tests/unit/integrations/client.cases.md` (revision 2) · Tests: `tests/unit/integrations/test_client.py` · Source commit: e48a092
> Result: 44 passed · 3 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/integrations/test_client.py -q -p no:cacheprovider --cov=app.integrations.sslcommerz.client --cov-branch --cov-report=term-missing`

## How the tests are built
- **Pure Python module**: no `db` fixture, no factories, no mocks, no time patching (spec Externals: none). Every case asserts on the constructed object, the returned value, or the raised exception.
- **Conventions → code** (top of the test file, each commented):
  - REQ_KW → module dict `REQ_KW`; `REQ_ORDER` is the declared field order used by SSLC-REQ-02 (positional) and SSLC-REQ-06 (parametrised omission).
  - FullClient → class `FullClient`, built from four module-level method bodies (`_init_session`, `_validate`, `_query_by_tran_id`, `_verify_signature`).
  - Missing<X> → `missing(name)` builds a `type(...)` subclass of `SSLCommerzClient` with the three other bodies (same bodies as FullClient).
  - SuperClient → class `SuperClient`, each override `return super().<method>(...)`. Its `query_by_tran_id` passes only `tran_id` (the SSLC-QRY-02 variant). SSLC-QRY-03's variant is `SuperClientWithHint`, which calls `super(SuperClient, self).query_by_tran_id(tran_id, val_id_hint=val_id_hint)` so the call lands directly on the abstract base.
- **Parametrised:** SSLC-REQ-06 (ten ids `SSLC-REQ-06-<field>`), SSLC-RES-03 (`SSLC-RES-03-lowercase`, `SSLC-RES-03-empty`). 37 cases → 47 test items.
- **xfail honesty** (verified with `--runxfail`): REQ-09 fails on `TypeError: unexpected keyword argument 'value_a'`; REQ-10 on `AttributeError: ... no attribute 'value_a'`; REQ-11 on `TypeError: unexpected keyword argument 'value_c'`, as the "fails today on" column says.
- **Best-practice defaults already in the cases file** (delegated by reviewer): INIT-01 asserts the ABC `TypeError` message names all four abstract methods; "no message" is asserted as `exc.value.args == ()`.
- Stability: 3 runs, identical outcome (44 passed, 3 xfailed).

## Discrepancies
None.

## Coverage gaps
None. Branch coverage is 100% (49 statements, 0 branches).

## Factories added
None. Nothing here touches the database. Nothing is worth promoting to `tests/unit/factories.py`. `REQ_KW` / `FullClient` could move to a shared `tests/unit/integrations/` helper if the `mock_client` or `payment_transaction_manager` tests need a ready-made `InitSessionRequest` or stub client.

## Notes for maintainers
- **When BUG-020 is fixed** (`value_a`..`value_d` added to `InitSessionRequest`), SSLC-REQ-09/10/11 will XPASS (strict → fail), so remove their xfail markers. SSLC-REQ-08 must keep passing, because the new fields must be optional.
- If the abstract method set of `SSLCommerzClient` changes, update `ABSTRACT_METHODS`, `_BODIES`, `FullClient` and `SuperClient` together. SSLC-INIT-01 pins the full set.
- INIT-01 relies on CPython's ABC error text listing the abstract method names. This holds on Python 3.12, which the venv uses.
- TODO (user direction, 2026-09-28): `MockSSLCommerzClient` is temporary. It will be removed or replaced by a real client, or restricted to non-prod, with default off. That change belongs to `app/integrations/sslcommerz/mock_client.py` and its spec, not to this module. These tests use their own subclasses and do not depend on the mock, so they need no changes when it goes.

## Revision history
- **2026-09-29 — cases revision 2.** The cases file was re-issued on the same spec (source commit e48a092) with no case changes: 37 cases, none added, none retired, no Given/Then changes. `client.verify.md` (verdict PASS) sent the executor no `test-weakness` findings. The only edit to the test file was its module docstring, which now says revision 2. Re-run: 3 runs, same result each time (44 passed, 3 xfailed). Under `--runxfail`, REQ-09/10/11 still fail on the assertions the cases name (`TypeError` on `value_a`, `AttributeError` on `value_a`, `TypeError` on `value_c`). Branch coverage is still 100%. Batch mode: nothing added to `tests/unit/factories.py`, and no shared docs were edited.
