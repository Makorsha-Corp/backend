# Execution notes — `app/managers/order_template_manager.py`

> Cases: `tests/unit/managers/order_template_manager.cases.md` (revision 3) · Tests: `tests/unit/managers/test_order_template_manager.py` · Source commit: e48a092
> Result: 111 passed · 94 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_order_template_manager.py -q -p no:cacheprovider -o addopts="" --cov=app.managers.order_template_manager --cov-branch --cov-report=term-missing` (private `COVERAGE_FILE`)

## How the tests are built
- Normal mode (no local model): 205 tests, one per card, in card order, each under `# [claude] <ID>`; `# Then N` marks the checks of the card's Then line N. No card is `Author: claude` in revision 2 (DT-06 builds the spec's minimal `ExpenseOrder` directly).
- **Standing rows** — the autouse fixture `s` builds W0, W1, W2, then UO, UA, UG, UX, UZ, then the four member rows, in the Conventions order; card names map to `s.w1`, `s.uo`, …
- **Given rows** — `tpl`, `line`, `account`, `factory`, `dept` insert and flush one row each with the card's "but" columns as keywords; `INACTIVE(s)`, `CLOSED(s)`, `DELETED(s)` spell the named variants (combined as `**{**INACTIVE(s), "template_name": "Lease"}`). `pending_p` adds the unflushed P.
- **Named checks** — `rt` / `rl` / `reread` (expire_all + SELECT), `lines(db, tpl_id)` (ordered by `line_number`, `id`), `snap` (every column read from the table; `unchanged` compares two snaps), `written` (`order_templates`, `order_template_items` counts, all workspaces), `count(db, Model, *where)`.
- **rolled back** — `sp = db.begin_nested()`, the call inside `patch.object(db, "commit", wraps=db.commit)`, the "(inside)" lines and the spy check, `sp.rollback()`, then the "(after)" lines.
- Refusals use plain `pytest.raises` with no savepoint, as Conventions say. The cards whose call raises `IntegrityError` (CT-30, CT-42) or `DataError` (UI-24, UI-26) today fail inside the `with` block of Then 1, as their "Fails today on" lines say.
- Nothing is mocked; `created_at` / `updated_at` come from the model clock and are only compared with `is not None` / `!= T1` / `== T1`.

## Verification
- **`--runxfail`** with the executor's own failson plugin (`<scratch>/failson.py`, maps the failing line to its `# Then N` block): all 94 strict xfails fail, each in the Then line its card names (0 mismatches). Failure kinds (revision 2): 49 `DID NOT RAISE HTTPException` (Then 1), 25 `DID NOT RAISE ValidationError` (Then 1), 2 `IntegrityError`, 2 `DataError` (Then 1), and 15 value assertions on the named field (e.g. UT-18 `updated_by is None`, CT-23 `cost_center_id is None`, UI-15 `line_subtotal == 0.00`).
- **Reference plugin** (`<scratch>/ref_otm.py`, in-process only, never in `app/`): replaces the four schemas (trimmed 1–255 names, `recurrence_type` / `unit` ≤ 50, category trimmed / lower-cased in {factory, department, other}, explicit null refused for required update fields, line quantity > 0 / price ≥ 0 with ≤ 2 decimals and ≤ 13 integer digits, half-up total < 10^13) and four manager methods (R11 order 403 → 400 → account 404 → cost centre 404 → approver 404; owner = `owner_user_id` or an active `owner` member row; explicit null clears; stamped only on a real change; `update_item` 422 `Line total is too large`, a sent 0 / null price used; `get_items` 404). With `--runxfail -p ref_otm`: 205 passed (and the service file's 31).
- **3 plain runs**: 111 passed, 94 xfailed each time — not flaky.
- `ruff check` clean (file-level `noqa: FURB157`: the cards write `Decimal("0")`, kept as written, as in `tests/unit/dao/test_order_template.py`); `ruff --select F841,F811` and an AST pass for unused test arguments clean; LF line endings.
- `<scratch>` = `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\tple\otm\`.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (84 statements, 18 branches).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its strict xfails XPASS (red): remove those markers. The marker constants at the top (`BUG_1014` … `BUG_2366`) carry the titles from `docs/testing/bugs.md`. BUG-2347's fix must read the caller's role itself (`owner_user_id` or an active `owner` member row of *this* workspace); grants held in W0 / W2 and a suspended `owner` row must not count (Q22-08 … Q22-11, Q22-17).
- CT-62, UT-42, UT-43 pin the order of refusals: once BUG-2347 and BUG-2361 are fixed, the 403 must still come before the 400, and the template's own 404 before both.
- CT-37 / CT-38 / UT-40 / UT-41 insert a department / factory with the explicit ids 880000001 / 880000002; if the sequences of those tables ever pass those values in the test database, the builders fail with a unique violation (setup error, not a test result).
- `OrderTemplateItemCreate.quantity` defaults to the int `1`; `model_dump()` then logs a `PydanticSerializationUnexpectedValue` warning in CT-12 / AI-13. The value stored is right (1.00); the warning goes away when the schema default becomes `Decimal("1")` (part of BUG-2363's fix).

## Useful for the coming permissions / notifications / payment features
- **Permissions (BUG-2347, OQ-22)**: only the workspace owner may create a template with `requires_approval=False` or `auto_approve=True`, or change either flag (in either direction, Q22-13); "owner" = `workspaces.owner_user_id == user_id` or an active `owner` member row in that workspace. Re-sending the stored values and the defaults need no role (Q22-12, Q22-15); other fields of a template that already skips approval stay open to any member (Q22-16). A refused flag change writes none of the other fields (Q22-14). Everything else on templates and lines is open to any active member.
- **Approver** must be an active member of the workspace (BUG-1216): no-workspace, other-workspace owner and suspended members are refused with `Profile with ID … not found` — the same membership test the permissions feature will need for "who can be asked to approve".
- **Notifications**: templates write no activity events; a recurring-generation notification would have nothing to hook into here (recurrence fields are stored unchecked, Q11).
- **Payments / money**: line subtotals are the exact product rounded by the `Numeric(15, 2)` column, half away from zero (0.125 → 0.13); totals of 10^13 or more overflow (BUG-2349). Any plan-limited money feature reusing these lines should check the total before flush.

## Revision history
- **2026-11-09 — Revision 2** (first execution): 203 cases → 110 passed · 93 xfailed (all strict), no discrepancies.
- **2026-11-09 — Revision 3** (`order_template_manager.verify.md` Finding 1): added OTMG-UI-27 (only `quantity=10000` sent onto a stored price 1 000 000 000.00 → 422 `LTL`, strict xfail BUG-2349; `--runxfail`: fails in Then 1 with `DataError` 22003 at flush, as its card says) and OTMG-UI-28 (only `quantity=1.01` onto 9900990099009.89 → 9999999999999.99, pass). No test changed or removed. `ref_otm.py` needed no change: its `update_item` already checks the total whenever `quantity` or `unit_price` is sent (205 passed under it). 3 plain runs 111 passed · 94 xfailed; coverage still 100% branch; ruff clean; LF.
