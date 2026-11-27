# Verification — `app/utils/order_workflow_terminal.py`

> **Verdict:** PASS
> Tests: 31 passed · 0 xfailed (reproduced ✅, none to reproduce) · coverage 100% branch (21 stmts, 10 branches)
> Mutation: 23 mutants · 23 killed · 0 survived → score 100% (after excluding 0 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 3

## Summary
These tests can be trusted. Every case in the cases file (revision 3) has exactly one test. Each test
asserts every Then item with exact checks: `==` against the full dict, `is True` / `is False`, and a
map-unchanged check against a deep copy. Nothing is mocked. The database cases run against real
Postgres, and OWT-T-01 re-reads the row after `expire_all()`. The runs matched the notes (31 passed,
100% branch) on three runs in a row. The mutation tool killed all 23 mutants. Nothing needs to change.

## Findings
None.

Observations (not findings, no action required):
- The test file's module docstring still says "cases.md (revision 2)". The cases file is now at
  revision 3, but its header says no case was added, removed or renumbered, and the notes record
  revision 3. The test file therefore matches the current cases.
- OWT-T-01 asserts `type(result[a_id]) is int`. The case only says "value is `int`", so the test is
  stricter than required, which is allowed.
- OWT-O-03, -08 and -09 also assert that the map is unchanged. Their Then columns do not list this,
  but the module Conventions require it for every O case, so the tests follow the cases.

## Surviving mutants
None. All 23 were killed:
L16 `IsNot→Is`; L17 negate-if and drop `not`; L18 return None; L23 `Eq→NotEq`; L30 `Or→And`;
L31 negate-if, `And→Or`, `Gt→GtE` and `0→1`; L32 `1→2`; L33 negate-if; L35 return None;
L44 negate-if, `Or→And` and `Is→IsNot` ×2; L45 return None and `False→True`; L47 return None,
`And→Or`, `IsNot→Is` and `Eq→NotEq`.

## Traceability
Cases: 31 (OWT-T-01..21, OWT-O-01..10). Tests: 31 `def test_` functions. A script checked the IDs:
each case ID starts exactly one test docstring, and every test has a case ID. Unmatched: none.
Marker mismatches: none. All 31 cases expect `pass`, and the file has no xfail markers. BUG IDs used:
none. Extra mocks and swallowed failures: none. A grep for `xfail|mock|patch|except|raises` matches
only the docstring line that says "Nothing is mocked".

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_workflow_terminal.py -q -p no:cacheprovider --cov=app.utils.order_workflow_terminal --cov-branch --cov-report=term-missing
  app\utils\order_workflow_terminal.py      21      0     10      0   100%
  31 passed in 3.61s
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_workflow_terminal.py -q -p no:cacheprovider --runxfail -rf
  31 passed in 2.90s   (no xfail tests to reproduce)
.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_workflow_terminal.py -q -p no:cacheprovider   (x2, flakiness)
  31 passed in 3.11s
  31 passed in 3.11s
.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/utils/order_workflow_terminal.py tests/unit/utils/test_order_workflow_terminal.py --timeout 180 --json %TEMP%/owt_verify_mut.json
  Mutants: 23 · killed 23 · timeout 0 · survived 0 · score 100%
```
