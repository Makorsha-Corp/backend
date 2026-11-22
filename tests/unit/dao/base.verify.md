# Verification — `app/dao/base.py`

> **Verdict:** PASS
> Tests: 62 passed · 3 xfailed (reproduced ✅ — all 3 fail on the designed assertion under `--runxfail`) · coverage 100% branch (41 stmts, 8 branches)
> Mutation: 25 mutants · 22 killed · 3 survived → score 100% (after excluding 3 equivalent, 0 dead, 0 bug-path)
> Source commit: e48a092 · Cases revision: 5

## Summary
These tests can be trusted. All 65 cases are implemented one-to-one, and each implementation matches its case. The only "mock" is a spy that wraps `db.commit` (it records calls and still commits), which the cases' Conventions allow. Every write case re-reads the row with raw SQL. Every error case checks the specific exception type. The three strict xfails fail on the designed assertion (BUG-100 heap order `[B, C, A]`, BUG-101 `UnmappedInstanceError`). Three consecutive runs gave the same result. Every behavior-bearing mutant is killed. The finding from the previous verification (DISCREPANCY-1 / BASE-G-05) is closed: spec G6 rewrote `get` R5, cases revision 4/5 redesigned G-05, and the executor removed the xfail. The test now passes and checks both sides of the rule.

## Findings
None.

Informational, with no stage action: BUG-100 and BUG-101 appear in xfail reasons, but they are still only in `tests/unit/dao/base.bugs-staging.md`. They are not yet in `docs/testing/bugs.md`, where `grep` finds 0 matches. In batch mode this is expected, because one agent merges the shared register later. So this is not counted as a traceability failure (best-practice default, delegated by reviewer). Re-check after the merge. BUG-035 (the deferred statuses leak) is already in `bugs.md`.

## Surviving mutants
| # | Line | Mutation | Class | Why | Fix by |
|---|---|---|---|---|---|
| 1 | L9:20 | `TypeVar("ModelType")` → `TypeVar("")` | equivalent | The name string of a typing-only `TypeVar` is used only in `repr` and introspection. No method reads it, so runtime behavior is unchanged. | — |
| 2 | L10:27 | `TypeVar("CreateSchemaType")` → `TypeVar("")` | equivalent | Same reason: it is the name string of a typing-only `TypeVar`. | — |
| 3 | L11:27 | `TypeVar("UpdateSchemaType")` → `TypeVar("")` | equivalent | Same reason: it is the name string of a typing-only `TypeVar`. | — |

Killed: every `return None` replacement (L43, 59, 84, 119, 139, 161, 187); both `isinstance(dict)` negations (L76, L108); the `hasattr` negation (L114); the `by_alias` flip in create (L79); all three update dump flags (`exclude_unset`, `exclude_none`, `by_alias`, L111); every `==` → `!=` filter flip (L43, L163, L190, L191); and the `skip` / `limit` default changes of both list methods (L46, L144).

## Traceability
- 65 cases and 63 test functions, which collect as 65 items (GM-09/10 and GW-11/12 are `pytest.param` ids). Nothing is unmatched in either direction: no case is missing, no ID is duplicated or unknown, and every test carries a case ID. This was checked with an AST script over the first docstring line plus the `pytest.param` ids.
- There are no marker mismatches:
  - Every `pass` case has no xfail marker. No DISCREPANCY remains; the earlier G-05 one was resolved.
  - `xfail BUG-100` maps to GM-04 and GW-05: `xfail(strict=True, reason=BUG_100)`, with the reason text "BUG-100: …".
  - `xfail BUG-101` maps to R-03: `xfail(strict=True, reason=BUG_101)`.
- xfail honesty (`--runxfail`):
  - GM-04 fails at `test_base.py:302`, which is case (a). The ids come back in heap order, e.g. `[36892, 36893, 36891]`.
  - GW-05 fails at `test_base.py:840`, which is case (a), in the same `[B, C, A]` order.
  - R-03 raises `UnmappedInstanceError: Class 'builtins.NoneType' is not mapped`.
  - All three fail on the designed assertion. None fails on a setup or import error.

## Fidelity review (all 65 cases read against Given/When/Then)
No missing, weakened or changed assertions, and no wrong setup. Specific checks:
- **G-05:** checks the pending row returns `None` and that a raw SELECT does not flush. After `db.flush()` the same object comes back (`is`), and the raw SELECT then finds the row.
- **"Not committed" cases (C-05, U-12, R-02):** all use a wrapping commit spy plus a savepoint rollback, then re-read.
- **Error cases:** all use `pytest.raises(<specific type>)` inside a savepoint and re-read afterwards. C-09 inspects `db.new` before the rollback, as the case requires.
- **GW-13:** an engine statement counter confirms zero SQL ran. GW-13 and GIW-05 assert the exact `AttributeError` message with `==`.
- **Ordering xfails:** they use the sequential-scan planner settings and the heap-disorder setup from the Conventions.
- **R-04 / R-05:** they use regular tables created inside the transaction, where the cases specify temp tables. Postgres forbids FKs from temp tables to permanent tables, and the notes document this. The tables are uncommitted and rolled back, so the substitution is faithful to the case's intent. This is not a finding.

## Commands run
```
.venv/Scripts/python.exe -m pytest tests/unit/dao/test_base.py -q -p no:cacheprovider --cov=app.dao.base --cov-branch --cov-report=term-missing
  app\dao\base.py   41   0   8   0   100%
  62 passed, 3 xfailed in 9.20s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_base.py -q -p no:cacheprovider --runxfail -rf
  FAILED test_base_gm_04__ordered_by_id · test_base_r_03__missing_id_returns_none · test_base_gw_05__ordered_by_id
  3 failed, 62 passed in 4.31s

.venv/Scripts/python.exe -m pytest tests/unit/dao/test_base.py -q -p no:cacheprovider   (x2, flakiness check)
  62 passed, 3 xfailed in 3.94s
  62 passed, 3 xfailed in 3.71s

.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/dao/base.py tests/unit/dao/test_base.py --timeout 180 --json <scratchpad>/base_mut.json
  Mutants: 25 · killed 22 · timeout 0 · survived 3 · score 88% (raw; 100% after excluding 3 equivalent)
```
These results match the Result line in the notes: 62 passed · 3 xfailed · 0 discrepancies · 100% branch coverage.
