# Verification — `app/utils/attachment_allowlist.py`

> **Verdict:** PASS
> Tests: 160 passed · 27 xfailed (reproduced ✅) · coverage 100% branch (61 stmts, 18 branches)
> Mutation: 117 mutants · 116 killed · 1 survived → score 100% (116/116, after excluding 0 equivalent, 1 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 4

## Summary
The tests can be trusted. This is a re-verification after cases revision 4. All 110 cases are implemented faithfully: exact values, exact error classes, full message matches, and every xfail fails on the assertion its case names. The two mutants that survived last round (`frozen=True` → `False` on L28 and L109) are now killed by AAL-TSP-01…03 and AAL-NRQ-01…02. The earlier formatting findings are fixed: the literal TAB/NEWLINE in the AAL-NUR-27 case row and in spec R2a are now written as escapes. The runs match the notes line and are stable across 3 runs. The only survivor is the dead `'(none)'` fallback on L133, which the spec marks unreachable. Nothing needs to change.

## Findings
None.

Batch-mode caveat, not a finding: BUG-120…125 are defined in `tests/unit/utils/attachment_allowlist.bugs-staging.md` (6 entries) but are not yet in `docs/testing/bugs.md` (0 hits). This is expected because the merge agent adds them later. Re-check the IDs after that merge.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 114 | L133 | `'(none)'` → `''` | dead | The spec's branch map (line 132–133) marks `not ext` / `'(none)'` unreachable. L129 already guarantees that `parts[1]` is non-empty, and lowercasing a non-empty string keeps it non-empty, so the fallback text can never appear in a message. | — |

## Traceability
- Cases: 110 (84 pass · 26 xfail). There are 110 test functions, one per case ID, with no duplicates and no test lacking a case ID. Pytest items: 187 (160 pass + 27 xfail; AAL-NUR-27 has 2 params). I checked this with an AST script over the test file against the case-table rows.
- Unmatched: none.
- Marker mismatches: none. Every `xfail BUG-NNN` case carries `pytest.mark.xfail(strict=True, reason="BUG-NNN: …")` with the right ID, and no pass case has a marker.
- Fidelity of the new revision-4 tests: all assertions match their cases.
  - AAL-TSP-01 and AAL-NRQ-01 are parametrized per field. Each asserts the exact `dataclasses.FrozenInstanceError` and then re-checks the original value (`set(...) ==` for the frozenset fields, `is EXTENSION_TO_SPEC["png"]` for `spec`).
  - TSP-02 and NRQ-02 cover both the new-attribute and the delete variants, including the `hasattr(..., "extra") is False` check.
  - TSP-03 uses the `try/finally` restore that its case prescribes. The `finally` block only restores state and does not swallow the `pytest.raises` failure.
  - TSP-04, TSP-05 and NRQ-03 assert every Then item (`==`, `is not`, hash equality, set sizes 1/2, and the inequality side).
- The remaining 102 tests are unchanged from the previous verification. I re-read them against the cases: no weakened, missing or changed assertions, no try/except around actions, and no mocks. AAL-VCR-20's `pytest.raises(ValueError)` is as the case designs it.
- xfail honesty (`--runxfail`): exactly the 27 xfail items fail (SAN-09…14, SAN-17…19, SAN-26…29, SAN-31…33, NUR-20…25, NUR-27 a/b, VCR-17…19). Every other item passes. Their failure points match the notes; none fails on setup or import.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_attachment_allowlist.py -q -p no:cacheprovider --cov=app.utils.attachment_allowlist --cov-branch --cov-report=term-missing
  app\utils\attachment_allowlist.py  61  0  18  0  100%
  160 passed, 27 xfailed in 2.30s
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_attachment_allowlist.py -q -p no:cacheprovider --runxfail -rf --tb=line
  27 failed, 160 passed   (the 27 failures = exactly the xfail items)
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_attachment_allowlist.py -q -p no:cacheprovider   (x2 more)
  160 passed, 27 xfailed in 1.03s
  160 passed, 27 xfailed in 0.98s   → stable, matches notes Result line (160 passed · 27 xfailed · 100% branch)
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/attachment_allowlist.py tests/unit/utils/test_attachment_allowlist.py --timeout 180 --json %TEMP%/attachment_allowlist_mut.json
  Mutants: 117 · killed 116 · timeout 0 · survived 1 · score 99% (raw)
  SURVIVED #114 L133:79 const: '(none)' -> ''
```
