# Verification — `app/integrations/sslcommerz/client.py`

> **Verdict:** PASS
> Tests: 44 passed · 3 xfailed (reproduced ✅) · coverage 100% branch
> Mutation: 6 mutants · 6 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. This is a fresh re-verification against cases revision 2, which re-issued revision 1 with no case changes. All 37 case IDs map one-to-one to 37 test functions (47 items after parametrisation). Each test asserts every Then item at the exact value the case gives. The tests use no mocks, swallow no failures and weaken no checks. The three BUG-020 xfails are strict. Under `--runxfail` each one fails on the assertion its case names. Coverage, the xfail run and three plain runs all match the Result line in the notes. The mutation tool killed all 6 mutants. Nothing needs to change.

The module is three dataclasses plus an ABC and has almost no logic to mutate, so the tool produced only 6 mutants. Most of the protection comes from the cases themselves. They pin field order, required and optional fields, defaults, equality and the full set of abstract methods. This is an observation, not a finding.

## Findings
None.

## Surviving mutants
None. All 6 were killed:

| # | Line | Mutation | Status |
|---|---|---|---|
| 1 | L25 | `product_name` default `'Workspace Subscription'` → `''` | KILLED |
| 2 | L26 | `product_category` default `'subscription'` → `''` | KILLED |
| 3 | L63 | `init_session` body `raise` → `pass` | KILLED (SSLC-INIT-04) |
| 4 | L70 | `validate` body `raise` → `pass` | KILLED (SSLC-VALD-02) |
| 5 | L77 | `query_by_tran_id` body `raise` → `pass` | KILLED (SSLC-QRY-02/03) |
| 6 | L83 | `verify_signature` body `raise` → `pass` | KILLED (SSLC-SIG-02) |

## Traceability
- **Counts:** 37 cases and 37 test functions. A script diffed the case IDs against the test docstrings and found no differences.
- **Unmatched:** none, and no ID appears twice. SSLC-REQ-06 and SSLC-RES-03 also carry `pytest.param` ids (`SSLC-REQ-06-<field>`, `SSLC-RES-03-lowercase|empty`).
- **Marker mismatches:** none.
  - The 34 `pass` cases have no xfail marker.
  - SSLC-REQ-09, REQ-10 and REQ-11 are marked `xfail(strict=True, reason=BUG_020)`, and the reason string names BUG-020.
  - BUG-020 exists in `docs/testing/bugs.md` with status open.
- **Fidelity:** I read every test against its Given, When and Then. None has a missing, weakened or changed assertion.
  - The exact literals match the cases, including `str(amount) == "10.005"`, `str(amount) == "100.00"`, `exc.value.args == ()` and all four abstract names checked in the INIT-01 message.
  - Setup matches each Given. `SuperClientWithHint` calls `super(SuperClient, self).query_by_tran_id(tran_id, val_id_hint=val_id_hint)`, which lands on the abstract base with both arguments, as SSLC-QRY-03 requires.
  - Error tests use the specific types the cases name (`TypeError`, `NotImplementedError`), never `Exception`.
  - Nothing is patched. The spec lists no externals.
  - The module does not touch the database, so the re-read rule does not apply.
- **xfail honesty (`--runxfail`):** each xfail test fails on the assertion its case names.
  - REQ-09 fails with `TypeError: InitSessionRequest.__init__() got an unexpected keyword argument 'value_a'`.
  - REQ-10 fails with `AttributeError: 'InitSessionRequest' object has no attribute 'value_a'`.
  - REQ-11 fails with `TypeError: ... unexpected keyword argument 'value_c'`.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/integrations/test_client.py -q -p no:cacheprovider --cov=app.integrations.sslcommerz.client --cov-branch --cov-report=term-missing   (x3)
  app\integrations\sslcommerz\client.py      49      0      0      0   100%
  44 passed, 3 xfailed in 1.17s
  44 passed, 3 xfailed in 1.02s
  44 passed, 3 xfailed in 0.85s

.venv/Scripts/python.exe -m pytest tests/unit/integrations/test_client.py -q -p no:cacheprovider --runxfail -rf
  FAILED test_sslc_req_09__value_fields_kept
  FAILED test_sslc_req_10__value_fields_default_none
  FAILED test_sslc_req_11__one_value_field_given_others_none
  3 failed, 44 passed in 0.32s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/integrations/sslcommerz/client.py tests/unit/integrations/test_client.py --timeout 180 --json %TEMP%/mut_sslc_client.json
  Mutants: 6 · killed 6 · timeout 0 · survived 0 · score 100%
```
