# Execution notes — `app/utils/notification_entity_label.py`

> Cases: `tests/unit/utils/notification_entity_label.cases.md` (revision 2) · Tests: `tests/unit/utils/test_notification_entity_label.py` · Source commit: e48a092
> Result: 54 passed · 28 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (target module)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/utils/test_notification_entity_label.py -q -p no:cacheprovider --cov=app.utils.notification_entity_label --cov=app.managers.attachment_manager --cov-branch --cov-report=term-missing`

## How the tests are built
- **W1 / W2** → fixtures `w1`, `w2` (`make_workspace`).
- **MISSING** → module constant `MISSING = 2000000000`.
- **FK-only rows** ("created in the same workspace as the entity") → `_deps(db, ws)`: one profile, status, factory, account and work-order type per workspace, created lazily and cached in `db.info["nel_deps"]` (the session is per-test, so the cache dies with the rollback).
- **Standard label values** → `STANDARD_LABEL`; **Type names (R3a)** → `TYPE_NAME`.
- **Local builder** `make_entity(db, ws, entity_type, label, **kw)` inserts one row of any of the 11 attachment types with its label field set to `label` and flushes. Extra kwargs are set on the row (used for `is_deleted=True` in NEL-R-13). `item` uses `_item(db, ws, sku=, name=)`; `project_component` creates a parent project too.
- **Call shape + "always a str"** → helper `call(db, ws_id, entity_type, entity_id)` which asserts `isinstance(result, str)` on every call; no exception is raised when the helper returns.
- Parametrized cases use pytest ids `NEL-R-NN-<type>` / `NEL-R-NN-<letter>` so every case/parameter set is individually visible. NEL-R-05 and NEL-R-06 share one function (ids `NEL-R-05`, `NEL-R-06`).
- **No mocks**, no time patching, no race simulations (Conventions: none).
- NEL-R-17: `Inventory` has no name column; per cases r2 the setup is any valid inventory, built as a storage inventory for an item named `"Main Warehouse Stock"`. The case only asserts the id form (`"inventory #<id>"`).
- NEL-R-23 (R9): pending state checked with `db.new`/`db.dirty`/`db.deleted`, row counts via `SELECT count(*)`, then `db.expire_all()` + `db.get` re-reads.
- BUG-200 xfails are `strict=True`; the NEL-R-08/10/12/15 assertions are the exact `"<type name> #<id>"` equality named in "fails today on".
- Flakiness: file run 3 times (r1 and again r2), identical results (54 passed, 28 xfailed).

## Discrepancies
None.

## Coverage gaps
`app/utils/notification_entity_label.py`: None — 100% branch coverage (13 stmts, 0 branches missed).

Collaborator `app/managers/attachment_manager.py` (measured for the lookup path the spec's branch map lists):

| Lines | Kind | What the code does there |
|---|---|---|
| 198 (`dao is None → return None` in `_fetch_entity_row`) | unreachable | Only `SCRATCH` lacks a DAO and it returns early at line 160; spec branch map already says so. |
| 228 (`return None` at end of `_extract_entity_label`) | unreachable | Every non-scratch enum value has its own branch above; spec branch map already says so. |
| All other missed lines (91–147, 250–812 etc.) | deferred | Other `AttachmentManager` callables; owned by the attachment manager spec, not this module. |

## Factories added
None (batch mode — `tests/unit/factories.py` not edited).

Worth promoting later to `tests/unit/factories.py`: `make_entity` (one row per attachment entity type with FK scaffolding — `make_purchase_order`, `make_sales_order`, `make_expense_order`, `make_transfer_order`, `make_work_order`, `make_project`, `make_project_component`, `make_machine`, `make_account_invoice`, `make_help_ticket`) and the per-workspace FK scaffolding (`make_status`, `make_factory`, `make_account`, `make_work_order_type`). The attachment manager and discussion tests will need the same builders.

## Notes for maintainers
- When BUG-200 is fixed, all 28 xfails (NEL-R-08 ×11, NEL-R-10 ×11, NEL-R-12 ×5, NEL-R-15) will XPASS → strict failure; remove the `xfail` markers. The paired passing cases (NEL-R-07/09/11/14) only assert "ends with the id", so they stay green before and after the fix.
- The fix must stay in this module; `AttachmentManager.resolve_entity_label` keeps its `<type>-<id>` fallback (spec Q1 resolution).
- Numbers/names in `_deps` use a module-level counter so repeated calls never collide on unique constraints.

## Revision history
- r1: initial implementation. Removed a precondition assertion (`row.is_deleted is True`) in NEL-R-13 that an earlier draft had added; the case does not ask for it.
- r2: cases revision 2 (NEL-R-17 setup no longer names the inventory). Updated only NEL-R-17's setup comment/item name to `"Main Warehouse Stock"`; assertion unchanged. Re-ran 3x + coverage: 54 passed, 28 xfailed, 100% branch. No other tests changed; no retired IDs.
