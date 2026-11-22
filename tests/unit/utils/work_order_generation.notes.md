# Execution notes — `app/utils/work_order_generation.py`

> Cases: `tests/unit/utils/work_order_generation.cases.md` (revision 2) · Tests: `tests/unit/utils/test_work_order_generation.py` · Source commit: e48a092
> Result: 26 passed · 12 xfailed · 0 discrepancies · 0 errors — branch coverage 88% (100% of specified code; the only miss is the dead branch)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_work_order_generation.py -q -p no:cacheprovider --cov=app.utils.work_order_generation --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → fixtures/helpers** (all local to the test file; batch mode, `factories.py` not edited):
  - W1, W2 → fixtures `w1`, `w2` (`make_workspace` from `tests/unit/factories.py`).
  - F1, F2 (W1), F3 (W2) → fixtures `f1`, `f2`, `f3` via local `_make_factory`.
  - S1, S2 (F1) → fixtures `s1`, `s2` via local `_make_section`.
  - "Machines" → `mk(db, factory, section=None, name=..., **overrides)`: live (`is_deleted=False`, `is_active=True`) in the factory's workspace; `section` given → one `MachineSectionAssignment` row ("assigned S"), else none ("unassigned"). The assignment row takes the machine's workspace (so WOG-R-18's W2 machine assigned to W1's S1 carries `workspace_id = W2`).
  - 1000/1001-machine cases → `mk_bulk`: one multi-row `INSERT ... RETURNING id` for machines (names "Machine 0001"…) plus one bulk insert for assignments; asserts the row count.
  - "Template T" → `template(...)`: an in-memory `WorkOrderTemplate`, never added to the session.
  - "Call" → `call(db, t, workspace, **kwargs)`.
  - "Set equals {…}" → `assert_set_equals` (sorted equality + length check). "returns [X]" → exact list `==`.
  - "no pending changes" → `assert_no_pending` (`db.new` and `db.dirty` empty).
  - WOG-R-15/16/17 share their machine set through the `r15_machines` fixture.
  - The ordering cases (WOG-R-26, 35) share `_ordering_machines`, which asserts ids ascend with insertion before calling.
- **Mocks:** none (spec lists no externals, no time and no race simulations).
- **DB-error cases:** none; the function has no error rows.
- **Re-reads:** the function is read-only, so no write cases need a re-read. "No side effects" is checked with the session's pending-change sets.
- **Flakiness:** ran the file 3 times with identical outcomes. The ordering xfails compare against an order that differs from insertion order, so heap order cannot pass them by accident.

## Discrepancies
None.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 28–31 (and the false branch of `if section_id:` into L27) | dead | Second `if factory_section_id:` branch. It can't be reached because `section_id = template.default_factory_section_id or factory_section_id` is already truthy whenever `factory_section_id` is. The spec's Not specified section lists it for removal. |

## Factories added
None (batch mode). Candidates to promote to `tests/unit/factories.py` later:
- `make_factory(db, workspace)`, `make_factory_section(db, factory)`.
- `make_machine(db, factory, section=None, **overrides)` with an optional `MachineSectionAssignment`.
- `bulk_machines(db, factory, count, section=None)`, a fast multi-row insert for cap tests.

## Notes for maintainers
- When BUG-340 or BUG-341 is fixed, WOG-R-07..09 or WOG-R-10..14 will XPASS (strict → fail). Remove their markers.
- When BUG-342 is fixed (cap removed), WOG-R-28 and WOG-R-37 will XPASS. WOG-R-27 and WOG-R-36 should keep passing.
- When BUG-343 is fixed (ORDER BY lower(name), id), WOG-R-26 and WOG-R-35 will XPASS. The passing set-based cases do not need to change.
- When dead lines 27–31 are removed, coverage should reach 100% branch coverage.
- The four 1000+/1001 cases insert about 1000 rows each through bulk insert. They take well under a second, but don't swap `mk_bulk` for per-row `mk`.
- WOG-R-09 uses the id 2147483000 and asserts it does not exist before the call.

## Revision history
- **Revision 2 (cases rev 2, source e48a092):** the cases file was re-issued against the same APPROVED spec with no cases added, changed or retired, and `work_order_generation.verify.md` (PASS) routed no `test-weakness` findings to the executor. No tests changed. Only the module docstring's revision reference was updated. I re-ran the file 3 times: 26 passed and 12 xfailed on every run. Branch coverage is unchanged at 88%, and the only miss is the dead L28–31 branch.
- **Revision 1:** initial implementation of all 38 cases.
