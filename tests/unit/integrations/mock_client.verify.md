# Verification — `app/integrations/sslcommerz/mock_client.py`

> **Verdict:** PASS
> Tests: 127 passed · 65 xfailed (reproduced ✅) · coverage 100% branch (50 stmts, 12 branches)
> Mutation: 63 mutants · 61 killed · 2 survived → score 100% (after excluding 0 equivalent, 0 dead, 2 bug-path)
> Source commit: e48a092 · Cases revision: 2

## Summary
These tests can be trusted. Each of the 69 cases maps to exactly one test. Each assertion matches its case's Then column exactly, and each of the 16 bug cases carries `xfail(strict=True)` naming its BUG ID. With `--runxfail`, all 65 xfail items fail on the exception or assertion their case names. The runs are stable (3 identical runs) and match the notes (127 passed, 65 xfailed, 100% branch coverage).
Two mutants survive, the same two that survived the rev-1 verification (#43, #59). Both change only where a multi-dot token is split. Such a token is accepted today only on the BUG-583 path (MD_OK). Only the xfail(BUG-583) cases DEC-07, VAL-11 and QRY-17 target that path, and the mutation run leaves xfail tests out. The spec itself (line 60) predicts this and says the mutants become equivalent once BUG-583 is fixed. Both are classed `bug-path`. The previous findings F1 (spec-gap) and F2 (case-missing) are resolved: spec G1/BUG-583 and cases rev 2 cover them.

## Findings
None.

Informational (not findings):
- BUG-580/581/582/583 are not in `docs/testing/bugs.md` yet. They live in `tests/unit/integrations/mock_client.bugs-staging.md`, which is expected in batch mode (the registers are merged later). Every xfail reason names an ID that exists in staging.
- TODO-001 (the mock is to be removed or restricted to non-production) is recorded in the spec, the notes and the test docstring. There is nothing to verify.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 43 | L66 `encoded, signature = val_id.rsplit(".", 1)` | maxsplit `1 -> 2` | bug-path | On a single-dot token the split is identical. On MD_REJ tokens (`E.S1.`, `E.S1.x`, `a.b.c`) both the original and the mutant return `None`, so DEC-08 and VAL-05 cannot tell them apart. The only inputs where the two differ are MD_OK (`E.x.S1`, `E..S1`): the original accepts them, which is BUG-583, and the mutant rejects them, which is the intended behavior (`_decode_val_id` R3a). Only xfail(BUG-583) cases DEC-07, VAL-11 and QRY-17 use these inputs, and the mutation run excludes them. The spec's test-designer note (spec L60) records this. After the fix the mutant is equivalent. | — (resolves when BUG-583 is fixed) |
| 59 | L90 `verify_sign=val_id.rsplit(".", 1)[1]` | maxsplit `1 -> 2` | bug-path | L90 runs only on tokens `_decode_val_id` accepted. For every single-dot token, `[1]` is the same under both maxsplits. It differs only for a multi-dot token that was accepted, which exists only on the BUG-583 path (MD_OK). VAL-01, VAL-12 and BVI-05 assert `verify_sign` exactly on single-dot tokens. Once BUG-583 is fixed no multi-dot token is accepted, so the mutant becomes equivalent. | — (resolves when BUG-583 is fixed) |

## Traceability
Cases: 69. Tests: 69 (192 parametrised items). Unmatched case IDs: none. Tests without a case ID: none. Each ID sits in the first docstring line of exactly one test (checked with an AST script).
Marker check: the 53 `pass` cases have no xfail marker, and there are no DISCREPANCY markers (DISCREPANCY-1 is retired). All 16 `xfail BUG-NNN` cases use `xfail(strict=True, reason=BUG_NNN)` with the matching ID:
- BUG-581: DEC-05/06, VAL-06/07, QRY-14
- BUG-580: QRY-04/05/09/11/12/16
- BUG-582: VSIG-09
- BUG-583: DEC-07/09, VAL-11, QRY-17

Fidelity: every Then item is asserted, and exact values are compared with `==` or `is`. Whole-object `ValidationResult` equality is used where the case requires it: VAL-01, BVI-05, INV, UNATT, and the `== X.validate(tok)` checks.
- Setups follow Given: fresh or separate A/B/C instances, K1→K2 switches through monkeypatch, and `_other_key` restores K1.
- NCB/MD/NCJ inputs are built exactly as the Conventions define them. The layout of E is guarded by a module-level assert.
- No try/except blocks. `pytest.raises` names `KeyError` (and asserts `args[0]`) or `TypeError`, as the cases require.
- Only `settings` attributes are monkeypatched, matching the spec's "Externals to mock: none" plus the settings it controls.
- The module is pure, so no DB re-read applies.

xfail honesty (`--runxfail --tb=line`): every failure is at the designed point:
- MAL fails with `KeyError` or `TypeError` at `_sign` L29.
- NAS fails with the non-ASCII `TypeError` at L70.
- BAD_AMT fails with `decimal.InvalidOperation` at L84.
- VSIG-09 fails with `TypeError` at L108.
- DEC-07/09 fail on `assert {decoded payload} is None`.
- VAL-11 and QRY-17 fail on equality with a VALID result.
- QRY-04/05/09/11/16 fail on equality with UNATTEMPTED.
- QRY-12 fails on equality with INVALID_TRANSACTION.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/integrations/test_mock_client.py -q -p no:cacheprovider --cov=app.integrations.sslcommerz.mock_client --cov-branch --cov-report=term-missing
  app\integrations\sslcommerz\mock_client.py  50  0  12  0  100%
  127 passed, 65 xfailed in 3.47s
.venv/Scripts/python.exe -m pytest tests/unit/integrations/test_mock_client.py -q -p no:cacheprovider --runxfail -rf
  65 failed, 127 passed in 1.48s   (all 65 = the xfail items, each on its designed reason)
.venv/Scripts/python.exe -m pytest tests/unit/integrations/test_mock_client.py -q -p no:cacheprovider   (x2 more)
  127 passed, 65 xfailed in 1.49s
  127 passed, 65 xfailed in 1.45s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/integrations/sslcommerz/mock_client.py tests/unit/integrations/test_mock_client.py --timeout 180 --json <system temp>/mock_client_mut.json
  Mutants: 63 · killed 61 · timeout 0 · survived 2 · score 97% (raw)
  SURVIVED #43 L66:52 const: 1 -> 2
  SURVIVED #59 L90:43 const: 1 -> 2
```
