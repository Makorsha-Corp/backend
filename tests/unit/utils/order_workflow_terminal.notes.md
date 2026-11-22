# Execution notes — `app/utils/order_workflow_terminal.py`

> Cases: `tests/unit/utils/order_workflow_terminal.cases.md` (revision 3) · Tests: `tests/unit/utils/test_order_workflow_terminal.py` · Source commit: e48a092
> Result: 31 passed · 0 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_order_workflow_terminal.py -q -p no:cacheprovider --cov=app.utils.order_workflow_terminal --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → helpers** (top of the test file):
  - W1, W2 → fixtures `w1`, `w2` using `tests.unit.factories.make_workspace`.
  - WF-A / WF-B / WF-C → local builder `make_order_workflow(db, workspace, *, status_sequence, type, name)` plus thin wrappers `wf_a` (W1, `'purchase'`, "PO flow"), `wf_b` (W1, `'sales'`, "SO flow"), `wf_c` (W2, `'purchase'`, "PO flow"). The builder adds and flushes.
  - `status_sequence` is assigned the raw Python value; the column type `JSONEncodedList` does `json.dumps` on write / `json.loads` on read, so the stored JSON is exactly the value in the case (`14.0` stays a JSON float, `True` → `true`, `{"a": 1}` / `"14"` stored as non-list JSON).
  - MISSING → `missing_id(db)` = `max(order_workflows.id) + 1000` (computed after setup rows are flushed).
  - Helper `call(db, workspace, ids)` makes the keyword-only call and asserts the result is a `dict` (Conventions: every T case). Equality is always `==` against the exact dict.
  - Helper `check(mapping, wf, status)` for `is_order_terminal`: deep-copies the map before the call; each O case asserts `is True` / `is False` and `m == before`.
- **Mocks:** none (spec: no externals, no race simulations, time not mocked).
- **Read-only check (OWT-T-01):** `db.expire_all()`, re-read WF-A with `db.get`, assert sequence/name/type/workspace, and count `order_workflows` rows in W1.
- `is_order_terminal` tests take no `db` fixture (pure).
- Stability: 3 runs, identical outcome (31 passed).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (21 statements, 10 branches).

## Factories added
None (batch mode: `tests/unit/factories.py` not edited). Candidate for promotion: `make_order_workflow(db, workspace, *, status_sequence, type="purchase", name=None)` — any manager/DAO test touching purchase/sales order workflows (inventory incoming-stock summary, PO/SO managers) will need it. When promoting, generate a unique `type` from the counter by default so several workflows per workspace don't hit `uq_order_workflows_workspace_type`.

## Notes for maintainers
- Two workflows in one workspace must use distinct `type` values (unique `(workspace_id, type)`); the wrappers use `'purchase'` and `'sales'`.
- OWT-T-17 depends on Python treating `bool` as `int` (`isinstance(True, int)`); if the code is tightened to exclude booleans, the spec R9 boolean note must be revised first and this case flips.
- OWT-T-15 relies on `json.loads("14.0")` returning a float; if the column type ever normalises numbers, revisit.

## Revision history
- **2026-09-29 — cases revision 3.** The cases are unchanged from revision 2: no IDs were added, retired or renumbered, and `order_workflow_terminal.verify.md` (PASS) sent no findings to the executor. The test file was not changed. It was re-run 3 times with the same result each time (31 passed), and branch coverage is still 100% (21 stmts, 10 branches). The coverage report also lists `app\utils\profile_auth.py` because the harness imports it; this does not affect this module's numbers.
