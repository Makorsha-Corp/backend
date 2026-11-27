# Test cases — `app/managers/expense_order_manager.py`

> **Spec:** `tests/unit/managers/expense_order_manager.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 1 — no spec change since the first pass. Completed the unfinished first pass: filled Counts and the per-callable line; Kind `schema` → `bug` (15 rows, not an allowed kind); added "nothing written" to 11 error cases (U-03, D-02, AI-05, UI-05, RI-03, AA-02, AA-08, AA-09, RAP-04, SA-04, SA-12); added a return-value convention; added SA-22 as the pass partner of xfail SA-19.
> **Revision:** 2 — spec Gap log closed G1–G10. G1: EO-U-23 now also asserts the `updated` event for a `required_approvals`-only change. G2: added EO-U-45 (`description: null` → 400). G3: added EO-U-46, EO-U-47 (all-null payload on a completed / voided order → 400). G4: added EO-FN-23 (week crossing a month end). G5: added EO-HL-45, EO-HL-46 (backslash in search). G6: Conventions Time now patches the two named targets; EO-AA-01 `assigned_at` and EO-LE-01 `created_at` (column defaults) are asserted by a real-clock window. G7: profile-missing branches marked unreachable — EO-LA-04, EO-AA-11, EO-RAP-09 retired; EO-LV-07 rewritten to the reachable variant (performer's profile deleted). G8: added EO-D-09 (completed + invoiced → completed error). G9: added EO-T-20 (whitespace-only override description). G10: fallback detail needs no case; EO-SA-11 unchanged.
> **Revision:** 3 — re-run after the spec's Gap log (G1–G10) was confirmed closed; no spec rule changed since revision 2. Full self-check re-run over the whole file: added EO-T-21 as the pass partner of xfail EO-T-10 (the "category becomes other" assertion holds today with a template cost center set, and was only checked inside the xfail case).
> **Revision:** 4 — no spec change (Gap log still G1–G10). Addressed verifier findings routed to the case designer: #2 EO-U-20 no longer has an approved approver (that path conflicted with BUG-740; the approved + unchanged-values path is xfail EO-U-22, now using U-20's two-field payload); #3 EO-U-06, U-08, U-29 now say "every column except `updated_by`" (BUG-740 is covered by xfail U-26/U-28); #9 EO-FN-16/17 Givens made realizable: invoices are voided through `invoice_status="voided"` and amounts are NOT NULL, so V3 paid 0, V5 `invoice_status="voided"`, V9 amount 0 / paid 0 (new gap G11). Also #1 (EO-C-27 setup): added a default create payload to the `create_expense_order` section so C-27…C-29 cannot lose F1 / description.
> **Revision:** 5 — no spec change (Gap log still G1–G10; G11 still open). Addressed verifier finding #14 (case-missing, surviving mutants L31:4 / :18 / :38 / :72): `update_expense_order` R9 names six detail fields but only `description` (U-21) and `expense_date` (U-25) had a pass case. Added one pass case per remaining field, each changing ONLY that field on an order with a recorded approval: EO-U-48 `account_id`, EO-U-49 `expense_category`, EO-U-50 `cost_center_id`, EO-U-51 `due_date`. Findings #11, #12, #13 are routed to the executor; no case row changed for them.
> **Revision:** 6 — (2026-11-01) spec `delete_expense_order` R5 split for BUG-1193 (owner, spec Q25): added EO-D-10…D-19, all strict xfail; added the AUDIT convention and one Deferred row. No existing case changed. One agent wrote the spec change, these rows and the tests, and had read the source first, so this revision is not black-box.
> **Counts:** 449 cases · 355 expected-to-pass · 94 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** helpers/validators (`_has_recorded_approvals` 5 · `is_approvable` 20 · `approvability_gap_reason` 15 (2 bug) · `_validate_order_allocation` 19 (2 bug) · `resolve_invoice_account_id` 4 · `reset_approvals` 5 · `_format_scalar_value` 12 · `_collect_field_changes` 7 · `_guard_confirmed_updates` 5 (1 bug) · `_guard_item_mutations` 3 (1 bug) · `_prepare_item_dict` + item schemas 17 (8 bug)) · `create_expense_order` 31 (8 bug) · `update_expense_order` 51 (23 bug) · `get_expense_order` 4 · hub list/count/stats/recent/snapshot 46 (4 bug) / 9 (1 bug) / 6 / 8 (2 bug) / 23 (2 bug) · `delete_expense_order` 19 (13 bug) · `add_item` 11 (2 bug) · `update_item` 21 (9 bug) · `remove_item` 10 (2 bug) · `get_items` 5 · `_recalc_totals` 3 · `list_approvers` 6 · `approval_summary` 7 (1 bug) · `approvals_met` 3 (1 bug) · `add_approver` 10 (2 bug) · `remove_approver` 8 (1 bug) · `set_approval` 22 (6 bug) · `log_event` 6 · `list_events` 7 · `create_expense_order_from_template` 21 (3 bug)
- **Notable design choices:**
  - No race simulations. Every HR-10 row-lock rule (BUG-741/742/743/744) is checked by **SQL capture** (a `SELECT … FOR UPDATE` on `expense_orders` during the action), as strict xfail. The concurrency *outcome* (loser gets the 400) is deferred to integration tests, and so is BUG-749's "two simultaneous creates both succeed" (lock and retry are both allowed, so a unit test cannot be written without picking one).
  - Removed schema fields (BUG-750 `order_template_id`, BUG-751 `invoice_id` / line `approved`) are checked by the field being absent from the schema's `model_fields`. That covers both "ignored" and "rejected with 422" (best-practice default, delegated by reviewer).
  - Schema-level rules (BUG-021, BUG-362, BUG-753's required fields reject `null`) build `ExpenseOrderItemCreate` / `ExpenseOrderItemUpdate` / `ExpenseOrderUpdate` directly. Boundaries that are accepted (2 decimals, 13 integer digits, qty 0.01, price 0, `required_approvals=0`) are pass cases.
  - Tie-order xfails (BUG-746 id tie, BUG-747, BUG-748) insert rows so that the expected order differs from insertion/id order. Their "fails today" still depends on Postgres returning unordered ties in a different order, which it does in practice but does not guarantee. If one of them XPASSes today, the executor reports it instead of weakening it.
  - Readiness cases (`is_approvable`, `approvability_gap_reason`) may need values that a NOT NULL column can refuse (`expense_category=""`/`None`, `expense_date=None`, `description=None`). The executor then sets that attribute on the loaded object inside `session.no_autoflush` (best-practice default, delegated by reviewer).
  - `update_expense_order` R9 has one pass case per detail field (U-21, U-25, U-48…U-51), each changing only that field, so dropping any one field from the reset list is caught. The category-only case (U-49) goes factory → `other` because that is the only category change that needs no second field; it does not assert `cost_center_id` or the exact `changes` list, which differ before and after BUG-752 (best-practice default, delegated by reviewer).
  - BUG-1193: EO-D-10…D-18 pass the new `user_id`, so today they all fail on the missing parameter, before any assertion runs; only EO-D-19 fails on behavior. Once the parameter exists, a refused case (D-15…D-17) XPASSes if no row is written, and that is the signal to remove its marker. EO-D-01…D-09 stay as written, without `user_id`: the fix must add it to those calls, or D-01…D-05 and D-09 go red and D-06…D-08 go on xfailing for the wrong reason.
  - `_collect_field_changes`, `_format_scalar_value`, the two guards, `resolve_invoice_account_id` and `_prepare_item_dict` are pure. They are called with transient `ExpenseOrder` objects or dicts, with no DB rows.
- **Needs a decision:** None blocking. G11 (spec R10/R11 describe an invoice `voided` flag and null amounts that the stored invoice cannot have) weakens EO-FN-16/17 only; decided by best-practice default (delegated by reviewer). All ten revision-1 gaps were closed by the spec's Gap log; the four intent answers (G2, G3, G9, G10) are best-practice defaults delegated by the reviewer.
  - `null` handling on update (G2, G3): `description: null` and an all-null payload on a frozen order are both 400s, tested as strict xfail BUG-753 (today: 200).

## Conventions for this module

**IDs.** `EO` = expense_order_manager. Method codes:
`HRA` `_has_recorded_approvals` · `IA` `is_approvable` · `GR` `approvability_gap_reason` · `VA` `_validate_order_allocation` · `RIA` `resolve_invoice_account_id` · `RA` `reset_approvals` · `FS` `_format_scalar_value` · `CF` `_collect_field_changes` · `GCU` `_guard_confirmed_updates` · `GIM` `_guard_item_mutations` · `PID` `_prepare_item_dict` (+ item schemas) · `C` `create_expense_order` · `U` `update_expense_order` · `G` `get_expense_order` · `HL` `list_expense_orders_for_hub` · `HC` `count_expense_orders_for_hub` · `HS` `expense_order_hub_stats` · `HR` `list_expense_orders_recent_for_hub` · `FN` `expense_order_financial_snapshot` · `D` `delete_expense_order` · `AI` `add_item` · `UI` `update_item` · `RI` `remove_item` · `GI` `get_items` · `RT` `_recalc_totals` · `LA` `list_approvers` · `AS` `approval_summary` · `AM` `approvals_met` · `AA` `add_approver` · `RAP` `remove_approver` · `SA` `set_approval` · `LE` `log_event` · `LV` `list_events` · `T` `create_expense_order_from_template`.

**Tenants and people.**
- W1, W2 = two workspaces.
- Profiles: U1 "Abid Hasan", U2 "Karim Ali", U3 "Rahim Uddin", U4 "Nadia Khan".
- Memberships (unless the case says otherwise): U1, U2, U3 are `active` members of W1 (U2 with position "Accountant", U1 and U3 with no position). U4 is an `active` member of W2 only.
- M = the manager instance, `session` = the test's real session. The actor (`user_id`) is U1 unless stated.

**Reference rows** (inserted only when a case names them):
- Factories: F1 = live, active factory of W1. FI = live but `is_active=False` factory of W1. FD = soft-deleted factory of W1. F2 = live factory of W2.
- Departments: D1, DI, DD, D2 = the same four variants for departments.
- Accounts: A1 = live account of W1 named "Acme Supplies". A2 = live account of W1 named "Beta Traders". AX = soft-deleted account of W1 named "Old Vendor". AW2 = live account of W2 named "Acme West".
- MISSING(table) = the highest existing id in that table + 1000.
- Y = `datetime.now().year` (system clock, not mocked).

**Order rows inserted directly** (not through the manager), in the order written, so ids increase in that order. Defaults:
- `workspace_id=W1`, `expense_number="EXP-2000-<n>"` with n = 101, 102, … in insertion order (year 2000, so it never collides with manager-generated current-year numbers). W2 orders use `EXP-2000-901`, `-902`, ….
- `expense_category="factory"`, `cost_center_id=F1`, `account_id=None`, `expense_date=2026-03-01`, `due_date=None`, `description="Rent"`, `required_approvals=None`, `invoice_id=None`, `voided=False`, `completed_at=None`, `subtotal=total_amount=0`, `created_by=U1`, `updated_by=None`, `created_at=T0`, `updated_at=None`.
- "completed" = `completed_at=T0`. "voided" = `voided=True`.
- **R** ("ready order") = a default order plus one line: `line_number=1`, description "Rent", `quantity=1`, `unit_price=100.00`, `line_subtotal=100.00`. The order totals are 100.00.
- Line defaults: `workspace_id` = the order's workspace, `line_number` as stated, `description="Line <n>"`, `quantity=1`, `unit=None`, `unit_price=10.00`, `line_subtotal=10.00`, `notes=None`. When a case inserts lines, it also sets the order totals to their sum unless it says otherwise.
- Approver rows: "U2 approved" = `approved=True`, `approved_at=T0`. "U2 pending" = `approved=False`, `approved_at=None`. Both use `assigned_by=U1`, `assigned_at=T0`, and the order's workspace.
- Invoices: "invoice I (status s)" = an account invoice of W1 linked by setting the order's `invoice_id`. It is not voided (`invoice_status` = `"draft"` unless the case says `"confirmed"`), has `payment_status` s, and `invoice_amount` / `paid_amount` as stated (both NOT NULL; never null). A "voided invoice" = `invoice_status="voided"` (the invoice has no separate `voided` column; see gap G11). "draft" and "confirmed" refer to the invoice's lifecycle status (`invoice_status`).

**Time.** T0 = `datetime(2026, 1, 1, 9, 0, 0)` (naive). `utcnow` is patched in every test at the two targets the spec names — `app.managers.expense_order_manager.utcnow` (`approved_at` in `set_approval`) and `app.dao.expense_order.utcnow` (today / due-date windows in `expense_order_financial_snapshot`) — to return **NOW = `datetime(2026, 3, 11, 10, 0, 0)`** (a Wednesday). Cases that need a different NOW say so. Column-default timestamps (event `created_at`, approver `assigned_at`) cannot be frozen: when a case asserts one written by the action, it checks `before <= value <= after`, where `before` / `after` are real-clock `app.utils.time.utcnow()` readings taken (unpatched) just before and just after the call. Cases that need a specific `created_at` / `assigned_at` (ordering) insert rows directly with that value, or set the column after creation and flush. `date.today()` and `datetime.now()` are not mocked.

**Checking results.**
- Errors: `HTTPException` with the exact `status_code` and `detail`.
- "Nothing written" = the order row (all columns), its lines, approvers and events are re-read after the call and are equal to a snapshot taken before the call. For a create that fails, it means there are no order, line, approver or event rows in W1.
- Re-read = expire the session, then query the DB again.
- "Events" = the order's event rows ordered by `id` ascending. `E(type, "desc")` means `event_type` and exact `description`. `performed_by` and `metadata` are checked only where the case states them.
- DB-error cases (`IntegrityError` or other `DBAPIError` at flush) run the action inside `session.begin_nested()`, roll back the savepoint, then re-read.
- **SQL capture:** a `before_cursor_execute` listener records the statements run during the action only. "LOCK" means at least one captured statement selects from `expense_orders` and contains `FOR UPDATE`.
- Schema cases construct the Pydantic model directly. "rejects" means it raises `pydantic.ValidationError`.
- **Return values** (every non-raising case, also when Then lists only DB state): `create_expense_order`, `create_expense_order_from_template`, `add_item`, `add_approver` and `log_event` return a new object whose `id` equals the re-read row's id. `update_expense_order` returns O (same id), with `_approvals_reset` `True` only where the case says so, otherwise `False`. `update_item` returns the edited line (same id). `remove_item` returns an object whose `line_number` and `expense_order_id` are those of the removed line. `set_approval` returns the acting user's approver row (same id). `delete_expense_order`, `remove_approver` and `reset_approvals` return `None`.

**Hub fixture H** (used by the hub/list cases). Rows are inserted in this order:

| Row | Number | WS | Category / cost center | Account | expense_date | total | State | created_at |
|---|---|---|---|---|---|---|---|---|
| O1 | EXP-2000-101 | W1 | factory / F1 | A1 "Acme Supplies" | 2026-03-01 | 100.00 | open, no invoice | T0 |
| O2 | EXP-2000-102 | W1 | department / D1 | none | 2026-03-05 | 200.00 | open, invoice I2 (unpaid, 200/0) | T0 |
| O3 | EXP-2000-103 | W1 | other / none | A2 "Beta Traders" | 2026-03-10 | 300.00 | completed, invoice I3 (paid) | T0 |
| O4 | EXP-2000-104 | W1 | factory / F1 | A1 | 2026-03-15 | 400.00 | voided, no invoice | T0 |
| O5 | EXP-2000-901 | W2 | factory / F2 | AW2 "Acme West" | 2026-03-05 | 500.00 | open, no invoice | T0 |

**Audit rows (BUG-1193).** AUDIT(X) = the `workspace_audit_logs` rows with `resource_type="expense_order"` and `resource_id=X.id`, re-read after the call. "audit:" checks the only row of AUDIT(X).

ALL = `exclude_complete=False, exclude_voided=False`. "list" means `list_expense_orders_for_hub(session, W1, …)` unless another workspace is stated. Results are compared as ordered lists of order ids.

**Race simulations.** None.

---

## `_has_recorded_approvals`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-HRA-01 | R1 | happy | order O; U1 pending, U2 approved | `_has_recorded_approvals(session, O.id, W1)` | returns `True` | pass |
| EO-HRA-02 | R2 | boundary | order O; U1 pending, U2 pending | call | returns `False` | pass |
| EO-HRA-03 | R2 | boundary | order O with no approver rows | call | returns `False` | pass |
| EO-HRA-04 | R3 | isolation | order O (W1); one approver row for O with `workspace_id=W2`, user U4, approved | `_has_recorded_approvals(session, O.id, W1)` | returns `False` | pass |
| EO-HRA-05 | R1 | isolation | orders O and P; P has U2 approved; O has U1 pending | call for O | returns `False` (P's approval does not count) | pass |

## `is_approvable`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-IA-01 | R6 | happy | ready order R | `is_approvable(session, R)` | returns `True` | pass |
| EO-IA-02 | R1 | error | R with `expense_category=""` | call | returns `False` | pass |
| EO-IA-03 | R1 | error | R with `expense_category=None` | call | returns `False` | pass |
| EO-IA-04 | R1 | error | R with `expense_date=None` | call | returns `False` | pass |
| EO-IA-05 | R2 | error | R with category factory, `cost_center_id=None` | call | returns `False` | pass |
| EO-IA-06 | R2 | error | R with category department, `cost_center_id=None` | call | returns `False` | pass |
| EO-IA-07 | R2, R6 | boundary | R with category other, `cost_center_id=None` | call | returns `True` | pass |
| EO-IA-08 | R3 | error | R with `description=None` | call | returns `False` | pass |
| EO-IA-09 | R3 | boundary | R with `description=""` | call | returns `False` | pass |
| EO-IA-10 | R3 | boundary | R with `description="   "` | call | returns `False` | pass |
| EO-IA-11 | R3 | boundary | R with `description="a"` | call | returns `True` | pass |
| EO-IA-12 | R4 | error | default order (no lines) | call | returns `False` | pass |
| EO-IA-13 | R5 | error | R plus line 2 with `description="  "`, qty 1 | call | returns `False` | pass |
| EO-IA-14 | R5 | error | R plus line 2 with `description=None`, qty 1 | call | returns `False` | pass |
| EO-IA-15 | R5 | boundary | R plus line 2 "Water", `quantity=0` | call | returns `False` | pass |
| EO-IA-16 | R5 | boundary | R plus line 2 "Water", `quantity=-5` | call | returns `False` | pass |
| EO-IA-17 | R5 | boundary | R plus line 2 "Water", `quantity=None` | call | returns `False` | pass |
| EO-IA-18 | R5, R6 | boundary | R plus line 2 "Water", `quantity=0.01` | call | returns `True` | pass |
| EO-IA-19 | R6 | boundary | R plus lines 2, 3, 4 "Water" qty 1 with `unit_price` 0, `None` and -100.00 | call | returns `True` (unit price not checked) | pass |
| EO-IA-20 | R4 | isolation | R has no lines of its own; a line with `expense_order_id=R.id` but `workspace_id=W2` exists | call | returns `False` (lines are loaded by id and workspace) | pass |

## `approvability_gap_reason`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-GR-01 | R5 | happy | ready order R | `approvability_gap_reason(session, R)` | returns `None` | pass |
| EO-GR-02 | R1 | error | R with `expense_category=""` | call | returns `'Set category and expense date before approvals can proceed'` | pass |
| EO-GR-03 | R1 | error | R with `expense_date=None` | call | returns `'Set category and expense date before approvals can proceed'` | pass |
| EO-GR-04 | R2 | error | R with factory, `cost_center_id=None` | call | returns `'Select a factory for this expense order before approvals can proceed'` | pass |
| EO-GR-05 | R2 | error | R with department, `cost_center_id=None` | call | returns `'Select a department for this expense order before approvals can proceed'` | pass |
| EO-GR-06 | R2 | boundary | R with other, `cost_center_id=None` | call | returns `None` | pass |
| EO-GR-07 | R3 | error | R with `description="   "` | call | returns `'Add a description before approvals can proceed'` | pass |
| EO-GR-08 | R3 | error | R with `description=None` | call | returns `'Add a description before approvals can proceed'` | pass |
| EO-GR-09 | R4 | error | default order (no lines) | call | returns `'Add at least one expense line before approvals can proceed'` | pass |
| EO-GR-10 | R1 before R2, R3 | boundary | order with `expense_date=None`, factory with no cost center, `description=None`, no lines | call | returns `'Set category and expense date before approvals can proceed'` | pass |
| EO-GR-11 | R2 before R3, R4 | boundary | factory with no cost center, `description=""`, no lines | call | returns `'Select a factory for this expense order before approvals can proceed'` | pass |
| EO-GR-12 | R3 before R4 | boundary | `description=None`, no lines | call | returns `'Add a description before approvals can proceed'` | pass |
| EO-GR-13 | R6 [BUG-758] | bug | R plus line 2 with `description="  "` | call | returns `'Every expense line needs a description and a quantity above 0 before approvals can proceed'` | xfail BUG-758 — fails today on: returns `None` |
| EO-GR-14 | R6 [BUG-758] | bug | R plus line 2 "Water", `quantity=0` | call | returns the BUG-758 line message (as GR-13) | xfail BUG-758 — fails today on: returns `None` |
| EO-GR-15 | R5 | boundary | R plus line 2 "Water", `quantity=0.01`, `unit_price=None` | call | returns `None` | pass |

## `_validate_order_allocation`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-VA-01 | R4 | happy | F1 | `_validate_order_allocation(session, W1, "factory", F1.id)` | returns `None` | pass |
| EO-VA-02 | R6 | happy | D1 | `(…, W1, "department", D1.id)` | returns `None` | pass |
| EO-VA-03 | R1 | error | — | category `"Factory"`, cost center F1 | 400 `'Invalid category: Factory. Must be factory, department, or other.'` | pass |
| EO-VA-04 | R1 | boundary | — | category `" factory"` | 400 `'Invalid category:  factory. Must be factory, department, or other.'` (two spaces after the colon) | pass |
| EO-VA-05 | R1 | boundary | — | category `""`, cost center `None` | 400 `'Invalid category: . Must be factory, department, or other.'` | pass |
| EO-VA-06 | R2 | happy | — | category `"other"`, cost center `None` | returns `None` | pass |
| EO-VA-07 | R2 | boundary | no factory or department has id 987654 | category `"other"`, cost center 987654 | returns `None` (no lookup, no error) | pass |
| EO-VA-08 | R3 | error | — | `"factory"`, `None` | 400 `'Select a factory for this expense order'` | pass |
| EO-VA-09 | R3 | error | — | `"department"`, `None` | 400 `'Select a department for this expense order'` | pass |
| EO-VA-10 | R4 | error | — | `"factory"`, MISSING(factories) | 404 `'Selected factory not found'` | pass |
| EO-VA-11 | R4 | isolation | F2 | `(…, W1, "factory", F2.id)` | 404 `'Selected factory not found'` | pass |
| EO-VA-12 | R5 [BUG-340] | bug | FD | `(…, W1, "factory", FD.id)` | 404 `'Selected factory not found'` | xfail BUG-340 — fails today on: no exception raised |
| EO-VA-13 | R5 | boundary | FI (inactive, live) | `(…, W1, "factory", FI.id)` | returns `None` | pass |
| EO-VA-14 | R6 | error | — | `"department"`, MISSING(departments) | 404 `'Selected department not found'` | pass |
| EO-VA-15 | R6 | isolation | D2 | `(…, W1, "department", D2.id)` | 404 `'Selected department not found'` | pass |
| EO-VA-16 | R6 [BUG-340] | bug | DD | `(…, W1, "department", DD.id)` | 404 `'Selected department not found'` | xfail BUG-340 — fails today on: no exception raised |
| EO-VA-17 | R6 | boundary | DI (inactive, live) | `(…, W1, "department", DI.id)` | returns `None` | pass |
| EO-VA-18 | R7 | boundary | no factory with id 0 | `"factory"`, `0` | 404 `'Selected factory not found'` (not the 400 for a missing cost center) | pass |
| EO-VA-19 | R4 | isolation | F1 exists; no department has F1's id (MISSING checked) | `"department"`, id of a factory that has no department with that id | 404 `'Selected department not found'` (a factory id is not accepted as a department) | pass |

## `resolve_invoice_account_id`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-RIA-01 | R1 | happy | transient order with `account_id=7` | `resolve_invoice_account_id(record)` | returns `7` | pass |
| EO-RIA-02 | R2 | error | transient order with `account_id=None` | call | 422 `'Set an account on the expense order before creating an invoice'` | pass |
| EO-RIA-03 | R2 | boundary | transient order with `account_id=0` | call | 422, same detail | pass |
| EO-RIA-04 | R1 | boundary | transient order with `account_id=1` | call | returns `1` | pass |

## `reset_approvals`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-RA-01 | R1, R2, R3 | happy | order O: U1 approved, U2 approved, U3 pending; order P: U1 approved | `reset_approvals(session, O.id, W1, U2.id)` | returns `None`; re-read O's approvers: U1 and U2 have `approved=False`, `approved_at=None`; U3 still pending (`assigned_at` T0 unchanged); P's U1 still approved with `approved_at=T0`; O events: exactly `E("approvals_reset", "Section unconfirmed (2 approval(s) cleared)")`, `performed_by=U2`, `metadata=None`; P has no events | pass |
| EO-RA-02 | R3 | side-effect | order O: U2 approved | `reset_approvals(…, O.id, W1, U1.id, reason="Order details edited")` | returns `None`; U2 not approved; events exactly `E("approvals_reset", "Order details edited (1 approval(s) cleared)")`, `performed_by=U1` | pass |
| EO-RA-03 | R4 | boundary | order O: U1 pending, U2 pending | call | returns `None`; approvers unchanged; 0 events | pass |
| EO-RA-04 | R4 | boundary | order O with no approvers | call | returns `None`; 0 events | pass |
| EO-RA-05 | R2 | isolation | order O (W1); approver row for O with `workspace_id=W2`, U4, approved | `reset_approvals(…, O.id, W1, U1.id)` | returns `None`; that row still `approved=True`, `approved_at=T0`; 0 events | pass |

## `_format_scalar_value`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-FS-01 | R1 | happy | — | `("due_date", None)` | `'—'` | pass |
| EO-FS-02 | R2 | happy | — | `("expense_date", date(2026, 3, 5))` | `'2026-03-05'` | pass |
| EO-FS-03 | R2 | boundary | — | `("x", datetime(2026, 3, 5, 14, 30, 0))` | `'2026-03-05T14:30:00'` | pass |
| EO-FS-04 | R3 | happy | — | `("x", Decimal("10.00"))` | `'10'` | pass |
| EO-FS-05 | R3 | boundary | — | `("x", Decimal("10.50"))` | `'10.5'` | pass |
| EO-FS-06 | R3 | boundary | — | `("x", Decimal("0.00"))` | `'0'` | pass |
| EO-FS-07 | R4 | happy | — | `("description", "  Rent  ")` | `'Rent'` | pass |
| EO-FS-08 | R4 | boundary | — | `("description", "   ")` | `'—'` | pass |
| EO-FS-09 | R4 | boundary | — | `("description", "")` | `'—'` | pass |
| EO-FS-10 | R4 | boundary | — | `("required_approvals", 0)` | `'0'` | pass |
| EO-FS-11 | R4 | boundary | — | `("x", False)` | `'False'` | pass |
| EO-FS-12 | R5 | boundary | — | `("account_id", 12)` and `("totally_unknown", 12)` | both return `'12'` | pass |

## `_collect_field_changes`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-CF-01 | R1, R2 | happy | transient order: `account_id=1`, category factory, `cost_center_id=5`, `expense_date=2026-03-01`, `due_date=None`, description "Rent", `required_approvals=None` | `update_dict` in reverse order: `{"required_approvals": 2, "description": "Rent April", "due_date": date(2026,3,31), "expense_date": date(2026,3,2), "cost_center_id": 6, "expense_category": "department", "account_id": 2}` | returns exactly 7 dicts in this order: `{field:"account_id", label:"Account", from_value:"1", to_value:"2"}`, `{"expense_category","Category","factory","department"}`, `{"cost_center_id","Cost center","5","6"}`, `{"expense_date","Expense date","2026-03-01","2026-03-02"}`, `{"due_date","Due date","—","2026-03-31"}`, `{"description","Description","Rent","Rent April"}`, `{"required_approvals","Required approvals","—","2"}` | pass |
| EO-CF-02 | R2 | boundary | same order | `{"description": "Rent", "account_id": 1}` (same values) | returns `[]` | pass |
| EO-CF-03 | R2 | boundary | same order | `{}` | returns `[]` | pass |
| EO-CF-04 | R2 | boundary | same order | `{"description": "Rent", "due_date": date(2026,4,1)}` | returns only the `due_date` entry | pass |
| EO-CF-05 | R3 | boundary | same order with `invoice_id=None` | `{"invoice_id": 9, "updated_by": 3}` | returns `[]` | pass |
| EO-CF-06 | R4 | boundary | same order | `{"description": "Rent "}` | returns `[{field:"description", label:"Description", from_value:"Rent", to_value:"Rent"}]` | pass |
| EO-CF-07 | R2 | boundary | order with `due_date=2026-03-31` | `{"due_date": None}` | returns `[{"due_date","Due date","2026-03-31","—"}]` | pass |

## `_guard_confirmed_updates`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-GCU-01 | R1 | error | transient order `completed_at=T0` | `update_dict={"description": "x"}` | 400 `'Expense order is complete and cannot be edited'` | pass |
| EO-GCU-02 | R2 | boundary | completed | `{}` | returns `None` | pass |
| EO-GCU-03 | R3 [BUG-754] | bug | transient order `voided=True`, not completed | `{"description": "x"}` | 400 `'Expense order is voided'` | xfail BUG-754 — fails today on: no exception raised |
| EO-GCU-04 | R4 | boundary | voided | `{}` | returns `None` | pass |
| EO-GCU-05 | R5 | happy | neither completed nor voided | `{"description": "x"}` | returns `None` | pass |

## `_guard_item_mutations`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-GIM-01 | R1 | error | transient order `completed_at=T0` | `_guard_item_mutations(record)` | 400 `'Expense order is complete'` | pass |
| EO-GIM-02 | R2 [BUG-754] | bug | transient order `voided=True` | call | 400 `'Expense order is voided'` | xfail BUG-754 — fails today on: no exception raised |
| EO-GIM-03 | R3 | happy | neither | call | returns `None` | pass |

## `_prepare_item_dict` and the item schemas

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-PID-01 | R1 | happy | — | `d = {"description": "Rent", "quantity": Decimal("3"), "unit_price": Decimal("33.33")}`; `_prepare_item_dict(d)` | returns `d` itself (`is d`); `d["line_subtotal"] == Decimal("99.99")`; other keys unchanged | pass |
| EO-PID-02 | R1 | boundary | — | `{"quantity": Decimal("2.5"), "unit_price": Decimal("4.10")}` | `line_subtotal == Decimal("10.250")` (exact product, not rounded) | pass |
| EO-PID-03 | R2 | boundary | — | `{"unit_price": Decimal("12.50")}` (no quantity key) | `line_subtotal == Decimal("12.50")` | pass |
| EO-PID-04 | R3 | boundary | — | `{"quantity": Decimal("4"), "unit_price": None}` | `line_subtotal == 0` | pass |
| EO-PID-05 | R3 | boundary | — | `{"quantity": Decimal("4")}` (no price key) | `line_subtotal == 0` | pass |
| EO-PID-06 | R3 | boundary | — | `{"quantity": Decimal("4"), "unit_price": Decimal("0")}` | `line_subtotal == 0` | pass |
| EO-PID-07 | R1 [BUG-021] | bug | — | `ExpenseOrderItemCreate(description="x", quantity=Decimal("1.005"), unit_price=Decimal("10"))` | rejects | xfail BUG-021 — fails today on: no ValidationError |
| EO-PID-08 | R1 [BUG-021] | bug | — | `ExpenseOrderItemCreate(description="x", quantity=Decimal("1"), unit_price=Decimal("33.333"))` | rejects | xfail BUG-021 — fails today on: no ValidationError |
| EO-PID-09 | R1 [BUG-021] | bug | — | `ExpenseOrderItemCreate(…, quantity=1, unit_price=Decimal("10000000000000.00"))` (14 integer digits) | rejects | xfail BUG-021 — fails today on: no ValidationError |
| EO-PID-10 | R1 | boundary | — | `ExpenseOrderItemCreate(…, quantity=Decimal("1.25"), unit_price=Decimal("9999999999999.99"))` (2 decimals, 13 integer digits) | builds; the values are kept as given | pass |
| EO-PID-11 | R1 [BUG-021] | bug | — | `ExpenseOrderItemUpdate(quantity=Decimal("1.005"))` and, separately, `ExpenseOrderItemUpdate(unit_price=Decimal("10000000000000"))` | both reject | xfail BUG-021 — fails today on: no ValidationError |
| EO-PID-12 | R1 [BUG-362] | bug | — | `ExpenseOrderItemCreate(description="x", quantity=0, unit_price=10)` | rejects | xfail BUG-362 — fails today on: no ValidationError |
| EO-PID-13 | R1 [BUG-362] | bug | — | `ExpenseOrderItemCreate(description="x", quantity=-5, unit_price=10)` | rejects | xfail BUG-362 — fails today on: no ValidationError |
| EO-PID-14 | R1 [BUG-362] | bug | — | `ExpenseOrderItemCreate(description="x", quantity=1, unit_price=Decimal("-0.01"))` | rejects | xfail BUG-362 — fails today on: no ValidationError |
| EO-PID-15 | R1 | boundary | — | `ExpenseOrderItemCreate(description="x", quantity=Decimal("0.01"), unit_price=0)` | builds | pass |
| EO-PID-16 | R1 [BUG-362] | bug | — | `ExpenseOrderItemUpdate(quantity=0)`, `ExpenseOrderItemUpdate(quantity=-1)`, `ExpenseOrderItemUpdate(unit_price=Decimal("-100"))` | each rejects | xfail BUG-362 — fails today on: no ValidationError |
| EO-PID-17 | R1 | boundary | — | `ExpenseOrderItemUpdate(quantity=Decimal("0.01"), unit_price=0)` | builds | pass |

## `create_expense_order`

Default payload for this section: unless the When states the field, `expense_category="factory"`, `cost_center_id=F1.id`, `description="A"`, no `account_id`, no `items`; F1 is always inserted. A When that lists only some fields (e.g. `account_id=AW2.id`) means "the default payload plus those fields" — never `cost_center_id=None` unless the When says so.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-C-01 | R3, R5, R7, R8, R9, R10 | happy | W1 has no orders; F1, A1 | `create_expense_order(session, ExpenseOrderCreate(expense_category="factory", cost_center_id=F1.id, account_id=A1.id, expense_date=date(2026,3,1), due_date=date(2026,3,31), description="March rent", items=[{description:"Rent", quantity:1, unit_price:5000.00}, {description:"Service charge", quantity:2, unit:"month", unit_price:250.50, notes:"Q1"}]), W1, U1.id)` | returns an order with an id; re-read: `workspace_id=W1`, `created_by=U1`, category factory, `cost_center_id=F1`, `account_id=A1`, dates as sent, description "March rent", `required_approvals=None`, `invoice_id=None`, `voided=False`, `completed_at=None`, `subtotal=total_amount=5501.00`; lines by line_number: 1 "Rent" qty 1 price 5000.00 subtotal 5000.00; 2 "Service charge" qty 2 unit "month" price 250.50 notes "Q1" subtotal 501.00; both `workspace_id=W1`, `expense_order_id`=order id; exactly 1 approver: `user_id=U1`, `assigned_by=U1`, `approved=False`, `approved_at=None`; events exactly `E("created", "Expense order created")`, `performed_by=U1`, `metadata=None` | pass |
| EO-C-02 | R6 | happy | W1 has no orders | create (factory F1, description "A") | re-read `expense_number == f"EXP-{Y}-001"` | pass |
| EO-C-03 | R6 | boundary | W1 has orders `EXP-{Y}-001`, `EXP-{Y}-002` | create | `expense_number == f"EXP-{Y}-003"` | pass |
| EO-C-04 | R6 | boundary | W1 has `EXP-{Y-1}-007` only | create | `expense_number == f"EXP-{Y}-001"` (other years ignored) | pass |
| EO-C-05 | R6 | isolation | W2 has `EXP-{Y}-005`; W1 has none | create in W1 | `expense_number == f"EXP-{Y}-001"` | pass |
| EO-C-06 | R6 | boundary | W1 has `EXP-{Y}-999` | create | `expense_number == f"EXP-{Y}-1000"` | pass |
| EO-C-07 | R6 [BUG-749] | bug | W1 has `EXP-{Y}-999` and `EXP-{Y}-1000` | create (inside savepoint) | returns an order; re-read `expense_number == f"EXP-{Y}-1001"` | xfail BUG-749 — fails today on: IntegrityError (retries `…-1000`) |
| EO-C-08 | R6 [BUG-749] | bug | W1 has `EXP-{Y}-001`; W2 has none | create in W2 (category other, description "B", actor U4) inside savepoint | returns an order; re-read W2 order `expense_number == f"EXP-{Y}-001"`; W1's order unchanged | xfail BUG-749 — fails today on: IntegrityError from the workspace-wide unique index |
| EO-C-09 | R6 | boundary | W1 has `EXP-{Y}-002` and `EXP-{Y}-010` (numeric max 10) | create | `expense_number == f"EXP-{Y}-011"` | pass |
| EO-C-10 | R1 | error | — | category `"Factory"`, cost center F1, description "A" | 400 `'Invalid category: Factory. Must be factory, department, or other.'`; nothing written | pass |
| EO-C-11 | R1 | error | — | category factory, `cost_center_id=None`, description "A" | 400 `'Select a factory for this expense order'`; nothing written | pass |
| EO-C-12 | R1 | error | F2 | category factory, `cost_center_id=F2.id` | 404 `'Selected factory not found'`; nothing written | pass |
| EO-C-13 | R1 [BUG-340] | bug | FD | category factory, `cost_center_id=FD.id`, description "A" | 404 `'Selected factory not found'`; nothing written | xfail BUG-340 — fails today on: order created |
| EO-C-14 | R1, R2 | boundary | — | category `"bogus"`, description `"   "` | 400 invalid-category detail (`'Invalid category: bogus. Must be factory, department, or other.'`), not `Description is required`; nothing written | pass |
| EO-C-15 | R2 | error | F1 | factory F1, `description=None` | 400 `'Description is required'`; nothing written | pass |
| EO-C-16 | R2 | boundary | F1 | factory F1, `description=""` | 400 `'Description is required'`; nothing written | pass |
| EO-C-17 | R2 | boundary | F1 | factory F1, `description="   "` | 400 `'Description is required'`; nothing written | pass |
| EO-C-18 | R2, R3 | boundary | F1 | factory F1, `description=" a "` | order created; re-read `description == " a "` (not trimmed) | pass |
| EO-C-19 | R3 | happy | — | category other, `cost_center_id=None`, description "Tea" | order created; re-read category other, `cost_center_id=None` | pass |
| EO-C-20 | R3, VA R2 | boundary | F1 | category other, `cost_center_id=F1.id`, description "Tea" | order created (no error); re-read category other | pass |
| EO-C-21 | R3 [BUG-752] | bug | F1 | category other, `cost_center_id=F1.id`, description "Tea" | re-read `cost_center_id is None` | xfail BUG-752 — fails today on: `cost_center_id == F1.id` |
| EO-C-22 | R4 | happy | F1 | factory F1, description "A", no `expense_date` | re-read `expense_date == date.today()` | pass |
| EO-C-23 | R9 | boundary | F1 | `items=None` | re-read `subtotal == 0`, `total_amount == 0`; 0 lines; 1 approver; 1 event | pass |
| EO-C-24 | R9 | boundary | F1 | `items=[]` | re-read `subtotal == total_amount == 0`; 0 lines | pass |
| EO-C-25 | R8 | side-effect | F1 | items `["Zeta" qty 1 price 1, "Alpha" qty 1 price 2, "Mid" qty 1 price 3]` (item without `quantity` omitted — see C-26) | lines 1 "Zeta", 2 "Alpha", 3 "Mid" (given order, not alphabetical); totals 6.00 | pass |
| EO-C-26 | R8, PID R2 | boundary | F1 | one item built as `ExpenseOrderItemCreate(description="Fee", unit_price=40)` (quantity not given) | line 1 `quantity == 1`, `line_subtotal == 40.00`; totals 40.00 | pass |
| EO-C-27 | R12 [BUG-750] | bug | F1; AW2 | factory F1, description "A", `account_id=AW2.id` | 404 `'Selected account not found'`; nothing written | xfail BUG-750 — fails today on: order created with W2's account |
| EO-C-28 | R12 [BUG-750] | bug | F1; AX | factory F1, description "A", `account_id=AX.id` | 404 `'Selected account not found'`; nothing written | xfail BUG-750 — fails today on: order created |
| EO-C-29 | R12 [BUG-750] | bug | F1 | factory F1, description "A", `account_id=MISSING(accounts)`, inside savepoint | 404 `'Selected account not found'` (an `HTTPException`); nothing written | xfail BUG-750 — fails today on: IntegrityError raised instead of HTTPException |
| EO-C-30 | Inputs [BUG-750] | bug | — | inspect `ExpenseOrderCreate.model_fields` | `"order_template_id" not in ExpenseOrderCreate.model_fields` | xfail BUG-750 — fails today on: field present |
| EO-C-31 | R1 | isolation | D2 | department `cost_center_id=D2.id` | 404 `'Selected department not found'`; nothing written | pass |

## `update_expense_order`

Default Given for this section: order O = default order with account A1, factory F1, `due_date=2026-03-31`, description "Rent March". "call(d)" = `update_expense_order(session, O.id, ExpenseOrderUpdate(**d), W1, U2.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-U-01 | R2, R7, R10 | happy | O; no approvals | call(`{"description": "Rent April"}`) | returns O (same id) with `_approvals_reset is False`; re-read: description "Rent April"; account A1, category factory, cost center F1, expense_date, due_date unchanged; events exactly `E("updated", "Order details updated")`, `performed_by=U2`, `metadata={"changes": [{"field":"description","label":"Description","from_value":"Rent March","to_value":"Rent April"}]}` | pass |
| EO-U-02 | R14 | side-effect | O | call(`{"description": "Rent April"}`) | re-read `updated_by == U2` | pass |
| EO-U-03 | R1 | error | O | `update_expense_order(session, MISSING(expense_orders), …{"description":"x"}, W1, U2.id)` | 404 `'Expense order with ID <missing> not found'`; nothing written (O unchanged, 0 events in W1) | pass |
| EO-U-04 | R1 | isolation | O5 = order of W2 | call on O5.id with W1, `{"description": "x"}` | 404 `'Expense order with ID <O5.id> not found'`; O5 unchanged (nothing written) | pass |
| EO-U-05 | R3 | error | O completed | call(`{"description": "x"}`) | 400 `'Expense order is complete and cannot be edited'`; nothing written | pass |
| EO-U-06 | R3 | boundary | O completed | call(`{}`) | returns O (same id), `_approvals_reset is False`; re-read: every column equal to the pre-call snapshot **except `updated_by`** (not asserted here — BUG-740, covered by xfail EO-U-28); lines and approvers unchanged; 0 events | pass |
| EO-U-07 | R3 [BUG-754] | bug | O voided | call(`{"description": "x"}`) | 400 `'Expense order is voided'`; nothing written | xfail BUG-754 — fails today on: no exception, description changed |
| EO-U-08 | R3, GCU R4 | boundary | O voided | call(`{}`) | returns O (same id), `_approvals_reset is False`; re-read: every column equal to the pre-call snapshot **except `updated_by`** (not asserted here — BUG-740); lines and approvers unchanged; 0 events | pass |
| EO-U-09 | R3, R13 [BUG-741] | bug | O; SQL capture on | call(`{"description": "Rent April"}`) | returns O; LOCK | xfail BUG-741 — fails today on: no captured `FOR UPDATE` |
| EO-U-10 | R4 | error | O | call(`{"expense_category": "Factory"}`) | 400 `'Invalid category: Factory. Must be factory, department, or other.'`; nothing written | pass |
| EO-U-11 | R4 | error | O; F2 | call(`{"cost_center_id": F2.id}`) | 404 `'Selected factory not found'`; nothing written | pass |
| EO-U-12 | R4 | happy | O; D1 | call(`{"expense_category": "department", "cost_center_id": D1.id}`) | re-read category department, cost center D1; `updated` event changes list = Category factory→department, then Cost center F1→D1 | pass |
| EO-U-13 | R4 | boundary | O (factory F1); D1 whose id ≠ F1's id and no department with F1's id | call(`{"expense_category": "department"}`) (stored cost center F1 merged in) | 404 `'Selected department not found'`; nothing written | pass |
| EO-U-14 | R4 | boundary | O (factory F1); a second live factory F3 of W1 | call(`{"cost_center_id": F3.id}`) | re-read cost center F3, category factory | pass |
| EO-U-15 | R5 | boundary | O (factory F1); then F1 is soft-deleted | call(`{"description": "Rent April"}`) | succeeds; description updated; cost center still F1 (allocation not re-checked) | pass |
| EO-U-16 | R4, R6 | happy | O (factory F1) | call(`{"expense_category": "other"}`) | returns O; re-read category other; no exception | pass |
| EO-U-17 | R6 [BUG-752] | bug | O (factory F1) | call(`{"expense_category": "other"}`) | re-read `cost_center_id is None` | xfail BUG-752 — fails today on: `cost_center_id == F1.id` |
| EO-U-18 | R6 [BUG-752] | bug | O (factory F1); D1 | call(`{"expense_category": "other", "cost_center_id": D1.id}`) | re-read category other, `cost_center_id is None` | xfail BUG-752 — fails today on: `cost_center_id == D1.id` |
| EO-U-19 | R7 | side-effect | O; A2 | call(`{"due_date": date(2026,4,15), "account_id": A2.id}`) | 1 `updated` event; `metadata["changes"]` = [Account `"<A1.id>"`→`"<A2.id>"`, Due date `"2026-03-31"`→`"2026-04-15"`] in that order | pass |
| EO-U-20 | R8, R10 | boundary | O; U3 pending (no approval recorded — an approved approver would hit BUG-740, see EO-U-22) (best-practice default, delegated by reviewer) | call(`{"description": "Rent March", "due_date": date(2026,3,31)}`) (same values) | returns O (same id) with `_approvals_reset is False`; re-read: every column equal to the pre-call snapshot **except `updated_by`** (BUG-740, not asserted); U3 still pending; 0 events of any type | pass |
| EO-U-21 | R9, R11 | side-effect | O; U3 approved, U2 pending | call(`{"description": "Rent April"}`) | returns O with `_approvals_reset is True`; re-read U3 `approved=False`, `approved_at=None`; U2 still pending; events exactly [`E("approvals_reset", "Order details edited (1 approval(s) cleared)")` `performed_by=U2`, then `E("updated", "Order details updated")`] | pass |
| EO-U-22 | R9, R10 [BUG-740] | bug | O; U3 approved | call(`{"description": "Rent March", "due_date": date(2026,3,31)}`) (unchanged values) | returns O with `_approvals_reset is False`; U3 still `approved=True`, `approved_at=T0`; 0 events | xfail BUG-740 — fails today on: U3 approval cleared |
| EO-U-23 | R8, R10 | boundary | O (`required_approvals=None`); U3 approved | call(`{"required_approvals": 2}`) | returns O with `_approvals_reset is False`; U3 still approved with `approved_at=T0`; re-read `required_approvals == 2`; events exactly `E("updated", "Order details updated")`, `performed_by=U2`, `metadata={"changes": [{"field":"required_approvals","label":"Required approvals","from_value":"—","to_value":"2"}]}` (no `approvals_reset` event) | pass |
| EO-U-24 | R10 | boundary | O; U3 pending (no approvals recorded) | call(`{"description": "Rent April"}`) | `_approvals_reset is False`; 0 `approvals_reset` events; 1 `updated` event | pass |
| EO-U-25 | R9 | side-effect | O; U3 approved | call(`{"expense_date": date(2026,3,2)}`) | `_approvals_reset is True`; U3 not approved | pass |
| EO-U-26 | R14 [BUG-740] | bug | O | call(`{}`) | returns O; re-read `updated_by is None` | xfail BUG-740 — fails today on: `updated_by == U2` |
| EO-U-27 | R14 [BUG-740] | bug | O | call(`{"description": "Rent March"}`) (same value) | re-read `updated_by is None` | xfail BUG-740 — fails today on: `updated_by == U2` |
| EO-U-28 | R14 [BUG-740] | bug | O completed | call(`{}`) | re-read `updated_by is None` | xfail BUG-740 — fails today on: `updated_by == U2` |
| EO-U-29 | R2 | boundary | O | call(`{}`) | returns O (same id), `_approvals_reset is False`; re-read: every column equal to the pre-call snapshot **except `updated_by`** (not asserted here — BUG-740, covered by xfail EO-U-26); lines and approvers unchanged; 0 events | pass |
| EO-U-30 | R2 [BUG-753] | bug | O (`due_date=2026-03-31`) | call(`{"due_date": None}`) | re-read `due_date is None`; 1 `updated` event with change Due date `"2026-03-31"`→`"—"` | xfail BUG-753 — fails today on: `due_date` still 2026-03-31 |
| EO-U-31 | R2 [BUG-753] | bug | O (account A1) | call(`{"account_id": None}`) | re-read `account_id is None` | xfail BUG-753 — fails today on: `account_id == A1.id` |
| EO-U-32 | R2, R4 [BUG-753] | bug | O (factory F1) | call(`{"cost_center_id": None}`) | 400 `'Select a factory for this expense order'` (an explicit null reaches the allocation check); nothing written | xfail BUG-753 — fails today on: no exception |
| EO-U-33 | R2 [BUG-753] | bug | — | `ExpenseOrderUpdate(expense_category=None)` | rejects | xfail BUG-753 — fails today on: no ValidationError |
| EO-U-34 | R2 [BUG-753] | bug | — | `ExpenseOrderUpdate(expense_date=None)` | rejects | xfail BUG-753 — fails today on: no ValidationError |
| EO-U-35 | R12 [BUG-750] | bug | O; AW2 | call(`{"account_id": AW2.id}`) | 404 `'Selected account not found'`; nothing written | xfail BUG-750 — fails today on: account changed to AW2 |
| EO-U-36 | R12 [BUG-750] | bug | O; AX | call(`{"account_id": AX.id}`) | 404 `'Selected account not found'`; nothing written | xfail BUG-750 — fails today on: account changed to AX |
| EO-U-37 | R12 [BUG-750] | bug | O | call(`{"account_id": MISSING(accounts)}`) inside savepoint | 404 `'Selected account not found'` (HTTPException); nothing written | xfail BUG-750 — fails today on: IntegrityError |
| EO-U-38 | R12 | happy | O; A2 | call(`{"account_id": A2.id}`) | re-read `account_id == A2.id` | pass |
| EO-U-39 | R12 [BUG-004] | bug | O | call(`{"description": "   "}`) | 400 `'Description is required'`; nothing written | xfail BUG-004 — fails today on: description stored as `"   "` |
| EO-U-40 | R12 [BUG-004] | bug | O | call(`{"description": ""}`) | 400 `'Description is required'`; nothing written | xfail BUG-004 — fails today on: description stored as `""` |
| EO-U-41 | R12 [BUG-362] | bug | — | `ExpenseOrderUpdate(required_approvals=-1)` | rejects | xfail BUG-362 — fails today on: no ValidationError |
| EO-U-42 | R12 | boundary | — | `ExpenseOrderUpdate(required_approvals=0)` | builds with `required_approvals == 0` | pass |
| EO-U-43 | Inputs [BUG-751] | bug | — | inspect `ExpenseOrderUpdate.model_fields` | `"invoice_id" not in ExpenseOrderUpdate.model_fields` | xfail BUG-751 — fails today on: field present |
| EO-U-44 | R4 | error | O | call(`{"expense_category": "department", "description": "New"}`) where no department has F1's id | 404 `'Selected department not found'`; description still "Rent March" (nothing written) | pass |
| EO-U-45 | R2, R12 [BUG-753] | bug | O (description "Rent March") | call(`{"description": None}`) | 400 `'Description is required'`; nothing written (description still "Rent March", `updated_by is None`, 0 events) (best-practice default, delegated by reviewer) | xfail BUG-753 — fails today on: no exception (returns O, description unchanged) |
| EO-U-46 | R3 [BUG-753] | bug | O completed (`due_date=2026-03-31`) | call(`{"due_date": None}`) | 400 `'Expense order is complete and cannot be edited'`; nothing written (`due_date` still 2026-03-31, `updated_by is None`, 0 events) (best-practice default, delegated by reviewer) | xfail BUG-753 — fails today on: no exception (returns O, `updated_by == U2`) |
| EO-U-47 | R3 [BUG-753] [BUG-754] | bug | O voided (`due_date=2026-03-31`) | call(`{"due_date": None}`) | 400 `'Expense order is voided'`; nothing written (`due_date` still 2026-03-31, `updated_by is None`, 0 events) (best-practice default, delegated by reviewer) | xfail BUG-753 — fails today on: no exception (returns O) |
| EO-U-48 | R9, R11 | side-effect | O (account A1); A2; U3 approved, U2 pending | call(`{"account_id": A2.id}`) (only this field) | returns O (same id) with `_approvals_reset is True`; re-read: `account_id == A2.id`; category factory, cost center F1, expense_date 2026-03-01, due_date 2026-03-31, description "Rent March" unchanged; U3 `approved=False`, `approved_at=None`; U2 still pending; events exactly [`E("approvals_reset", "Order details edited (1 approval(s) cleared)")` `performed_by=U2`, then `E("updated", "Order details updated")` `performed_by=U2`] | pass |
| EO-U-49 | R9, R11 | side-effect | O (factory F1); U3 approved, U2 pending | call(`{"expense_category": "other"}`) (only this field) | returns O (same id) with `_approvals_reset is True`; re-read: `expense_category == "other"`; account A1, expense_date, due_date, description unchanged (`cost_center_id` not asserted — BUG-752, covered by xfail EO-U-17); U3 `approved=False`, `approved_at=None`; U2 still pending; event types in order exactly [`approvals_reset`, `updated`], the first with description `"Order details edited (1 approval(s) cleared)"` and `performed_by=U2` (the `changes` list is not asserted — it gains a Cost center entry after BUG-752) | pass |
| EO-U-50 | R9, R11 | side-effect | O (factory F1); a second live factory F3 of W1; U3 approved, U2 pending | call(`{"cost_center_id": F3.id}`) (only this field) | returns O (same id) with `_approvals_reset is True`; re-read: `cost_center_id == F3.id`; category factory, account A1, expense_date, due_date, description unchanged; U3 `approved=False`, `approved_at=None`; U2 still pending; events exactly [`E("approvals_reset", "Order details edited (1 approval(s) cleared)")` `performed_by=U2`, then `E("updated", "Order details updated")`] | pass |
| EO-U-51 | R9, R11 | side-effect | O (`due_date=2026-03-31`); U3 approved, U2 pending | call(`{"due_date": date(2026,4,15)}`) (only this field) | returns O (same id) with `_approvals_reset is True`; re-read: `due_date == 2026-04-15`; account A1, category factory, cost center F1, expense_date, description unchanged; U3 `approved=False`, `approved_at=None`; U2 still pending; events exactly [`E("approvals_reset", "Order details edited (1 approval(s) cleared)")` `performed_by=U2`, then `E("updated", "Order details updated")`] | pass |

## `get_expense_order`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-G-01 | R1 | happy | order O in W1 | `get_expense_order(session, O.id, W1)` | returns O (id, number `EXP-2000-101`) | pass |
| EO-G-02 | R1 | soft-delete | O voided and completed | call | returns O | pass |
| EO-G-03 | R2 | error | — | `get_expense_order(session, MISSING(expense_orders), W1)` | 404 `'Expense order with ID <missing> not found'` | pass |
| EO-G-04 | R2 | isolation | O5 in W2 | `get_expense_order(session, O5.id, W1)` | 404 `'Expense order with ID <O5.id> not found'` | pass |

## `list_expense_orders_for_hub`

All cases use fixture H unless the Given says otherwise.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-HL-01 | R1, R7, R8, R12 | happy | H | list with no filters (defaults exclude complete and voided) | `[O2, O1]` | pass |
| EO-HL-02 | R7, R8, R12 | boundary | H | list ALL | `[O4, O3, O2, O1]` | pass |
| EO-HL-03 | R1 | isolation | H | `list_expense_orders_for_hub(session, W2)` | `[O5]` | pass |
| EO-HL-04 | R7 | boundary | H | `exclude_voided=False` (complete still excluded) | `[O4, O2, O1]` | pass |
| EO-HL-05 | R8 | boundary | H | `exclude_complete=False` | `[O3, O2, O1]` | pass |
| EO-HL-06 | R2 | happy | H | ALL, `expense_category="factory"` | `[O4, O1]` | pass |
| EO-HL-07 | R2 | boundary | H | ALL, `expense_category=""` | `[O4, O3, O2, O1]` | pass |
| EO-HL-08 | R2 | boundary | H | ALL, `expense_category=None` | `[O4, O3, O2, O1]` | pass |
| EO-HL-09 | R3 | happy | H | ALL, `account_id=A1.id` | `[O4, O1]` | pass |
| EO-HL-10 | R3 | boundary | H | ALL, `account_id=0` | `[]` | pass |
| EO-HL-11 | R3 | happy | H | ALL, `invoice_id=I2.id` | `[O2]` | pass |
| EO-HL-12 | R3 | boundary | H | ALL, `invoice_id=0` | `[]` | pass |
| EO-HL-13 | R4 | boundary | H | ALL, `date_from=2026-03-05`, `date_to=2026-03-10` | `[O3, O2]` (both ends inclusive) | pass |
| EO-HL-14 | R4 | boundary | H | ALL, `date_from=2026-03-06`, `date_to=2026-03-09` | `[]` | pass |
| EO-HL-15 | R4 | boundary | H | ALL, `date_from=2026-03-10` only | `[O4, O3]` | pass |
| EO-HL-16 | R4 | boundary | H | ALL, `date_to=2026-03-01` only | `[O1]` | pass |
| EO-HL-17 | R5 | happy | H | ALL, `status_ids=[1]` | `[O4, O1]` (draft = not completed, no invoice; voided included because exclude_voided is False) | pass |
| EO-HL-18 | R5 | happy | H | ALL, `status_ids=[2]` | `[O2]` | pass |
| EO-HL-19 | R5 | happy | H | ALL, `status_ids=[3]` | `[O3]` | pass |
| EO-HL-20 | R5 | boundary | H | ALL, `status_ids=[1, 3]` | `[O4, O3, O1]` | pass |
| EO-HL-21 | R5 | boundary | H | ALL, `status_ids=[99]` | `[O4, O3, O2, O1]` (unknown only, so no stage filter) | pass |
| EO-HL-22 | R5 | boundary | H | ALL, `status_ids=[2, 99]` | `[O2]` (unknown ignored) | pass |
| EO-HL-23 | R5 | boundary | H | ALL, `status_ids=[]` | `[O4, O3, O2, O1]` | pass |
| EO-HL-24 | R6 | happy | H | ALL, `invoice_filter="invoiced"` | `[O3, O2]` | pass |
| EO-HL-25 | R6 | happy | H | ALL, `invoice_filter="not_invoiced"` | `[O4, O1]` | pass |
| EO-HL-26 | R6 | boundary | H | ALL, `invoice_filter="bogus"` | `[O4, O3, O2, O1]` | pass |
| EO-HL-27 | R9 | happy | H | ALL, `search="CME S"` (middle of "Acme Supplies", different case) | `[O4, O1]` (O5's "Acme West" in W2 is not listed) | pass |
| EO-HL-28 | R9 | happy | H | ALL, `search="0-102"` (middle of the number) | `[O2]` (O2 has no account and still matches) | pass |
| EO-HL-29 | R9 | happy | H | ALL, `search="ACTOR"` | `[O4, O1]` (category factory) | pass |
| EO-HL-30 | R9 | happy | H | ALL, `search="Depart"` | `[O2]` | pass |
| EO-HL-31 | R9 | boundary | H | ALL, `search="   "` | `[O4, O3, O2, O1]` | pass |
| EO-HL-32 | R9 | boundary | H | ALL, `search=""` and, separately, `search=None` | both `[O4, O3, O2, O1]` | pass |
| EO-HL-33 | R9 | boundary | H | ALL, `search="  beta tr  "` | `[O3]` (text trimmed) | pass |
| EO-HL-34 | R9 | boundary | H | ALL, `search="zzz"` | `[]` | pass |
| EO-HL-35 | R10 | happy | H | ALL, `expense_category="factory"`, `account_id=A1.id`, `date_to=2026-03-10` | `[O1]` | pass |
| EO-HL-36 | R10 | boundary | H | defaults, `search="CME S"` | `[O1]` (O4 voided excluded before the search result) | pass |
| EO-HL-37 | R11 | happy | W1 orders: P1 account "100% Parts", P2 account "A_B Traders", P3 account "Plain Co" | ALL, `search="0% P"` | `[P1]`, with P1, P2, P3 on the same date and ordered by id desc | pass |
| EO-HL-38 | R11 [BUG-745] | bug | as HL-37 | ALL, `search="%"` | `[P1]` | xfail BUG-745 — fails today on: returns all three |
| EO-HL-39 | R11 [BUG-745] | bug | as HL-37 | ALL, `search="_"` | `[P2]` | xfail BUG-745 — fails today on: returns all three |
| EO-HL-40 | R12 | boundary | W1 orders (all open, no invoice) inserted in order: Q1 date 03-01 created T0; Q2 date 03-01 created T0+1h; Q3 date 03-01 created T0+1h; Q4 date 03-02 created T0 | list | `[Q4, Q3, Q2, Q1]` (date desc, created_at desc, id desc) | pass |
| EO-HL-41 | R12 | boundary | as HL-40 | `skip=1, limit=2` | `[Q3, Q2]` | pass |
| EO-HL-42 | R12 | boundary | 51 open orders in W1, all date 03-01, created T0 | list with no skip/limit | 50 orders, ids = the 50 highest ids in descending order | pass |
| EO-HL-43 | Errors | error | H | `list_expense_orders_for_hub(session, W1, foo=1)` | raises `TypeError` | pass |
| EO-HL-44 | R5, R7 | boundary | H | defaults, `status_ids=[1]` | `[O1]` (voided O4 excluded by default) | pass |
| EO-HL-45 | R11 [BUG-745] | bug | W1 open orders, same `expense_date`, inserted in order: B1 account named `Acme\Ltd` (one literal backslash), B2 account named `AcmeLtd` | ALL, `search="Acme\\Ltd"` (Python literal; the text is `Acme\Ltd`) | `[B1]` | xfail BUG-745 — fails today on: returns `[B2]` |
| EO-HL-46 | R11 [BUG-745] | bug | as HL-45 | ALL, `search="Acme\\"` (Python literal; the text is `Acme\`, trailing backslash) | `[B1]` | xfail BUG-745 — fails today on: returns `[]` |

## `count_expense_orders_for_hub`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-HC-01 | R1 | happy | H | `count_expense_orders_for_hub(session, W1)` | `2` | pass |
| EO-HC-02 | R1 | boundary | H | ALL | `4` | pass |
| EO-HC-03 | R1 | isolation | H | W2 | `1` | pass |
| EO-HC-04 | R1 | boundary | H | ALL, `search="zzz"` | `0` | pass |
| EO-HC-05 | R1 | boundary | 51 open orders in W1 | no filters | `51` (no paging) | pass |
| EO-HC-06 | R1 | happy | H | ALL, `search="CME S"`, `invoice_filter="not_invoiced"` | `2` | pass |
| EO-HC-07 | R1 [BUG-745] | bug | as HL-37 | ALL, `search="%"` | `1` | xfail BUG-745 — fails today on: `3` |
| EO-HC-08 | Errors | error | H | `foo=1` | `TypeError` | pass |
| EO-HC-09 | R1 | boundary | W1 with no orders | no filters | `0` (an int, not `None`) | pass |

## `expense_order_hub_stats`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-HS-01 | R1–R3 | happy | H | `expense_order_hub_stats(session, W1)` | `(2, Decimal("300.00"), 2, Decimal("300.00"), 1)` | pass |
| EO-HS-02 | R1–R3 | boundary | H | ALL | `(4, Decimal("1000.00"), 3, Decimal("700.00"), 2)` (open = O1, O2, O4; not invoiced = O1, O4) | pass |
| EO-HS-03 | R1 | isolation | H | W2 | `(1, Decimal("500.00"), 1, Decimal("500.00"), 1)` | pass |
| EO-HS-04 | R4 | boundary | H | ALL, `search="zzz"` | `(0, Decimal("0"), 0, Decimal("0"), 0)` | pass |
| EO-HS-05 | R2 | boundary | H | ALL, `status_ids=[3]` | `(1, Decimal("300.00"), 0, Decimal("0"), 0)` | pass |
| EO-HS-06 | Errors | error | H | `foo=1` | `TypeError` | pass |

## `list_expense_orders_recent_for_hub`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-HR-01 | R1 | boundary | 11 open orders in W1, each with `updated_at` = T0 + n minutes (n = 1…11 in insertion order) | `list_expense_orders_recent_for_hub(session, W1)` | 10 orders: n = 11 down to 2 | pass |
| EO-HR-02 | R1 | boundary | as HR-01 | `limit=2` | orders n=11, n=10 | pass |
| EO-HR-03 | R1 | happy | H with `updated_at` set: O1 T0+1h, O2 T0+2h, O4 T0+4h | defaults | `[O2, O1]` (complete and voided excluded) | pass |
| EO-HR-04 | R1 | isolation | as HR-03 | W2 | `[O5]` | pass |
| EO-HR-05 | R2 | happy | A: created T0, updated T0+2d; B: created T0, updated T0+1d | defaults | `[A, B]` | pass |
| EO-HR-06 | R2 [BUG-746] | bug | inserted in order: A created 2026-03-01, updated 2026-03-20; B created 2026-03-10, `updated_at=None`; C created 2026-03-15, `updated_at=None`; D created 2026-03-15, `updated_at=None` (D id > C id) | defaults | `[A, D, C, B]` | xfail BUG-746 — fails today on: first element is not A (never-updated orders sort first) |
| EO-HR-07 | R1 [BUG-745] | bug | as HL-37 | `search="_"` ALL | `[P2]` | xfail BUG-745 — fails today on: returns all three |
| EO-HR-08 | Errors | error | H | `foo=1` | `TypeError` | pass |

## `expense_order_financial_snapshot`

"FN(…)" = `expense_order_financial_snapshot(session, W1, …)`. Stage and category entries are compared as full dicts.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-FN-01 | R1 | happy | H | FN() | `category_breakdown == [{key:"department", label:"Department", count:1, total_value:200.00}, {key:"factory", label:"Factory", count:1, total_value:100.00}]` | pass |
| EO-FN-02 | R1 | boundary | H | FN(ALL) | `[{factory, "Factory", 2, 500.00}, {other, "Other", 1, 300.00}, {department, "Department", 1, 200.00}]` | pass |
| EO-FN-03 | R1 | boundary | one open W1 order with category `"office_supplies"` (direct insert), total 50.00 | FN() | `category_breakdown == [{key:"office_supplies", label:"Office Supplies", count:1, total_value:50.00}]` | pass |
| EO-FN-04 | R2 | boundary | H | FN(ALL, `search="zzz"`) | `category_breakdown == []`; `open_by_account == []` | pass |
| EO-FN-05 | R3 | happy | H | FN(ALL) | `stage_pipeline == [{key:"draft", label:"Draft", count:2, total_value:500.00}, {key:"invoiced", label:"Invoiced", count:1, total_value:200.00}, {key:"complete", label:"Complete", count:1, total_value:300.00}]` | pass |
| EO-FN-06 | R3 | boundary | H | FN() | `stage_pipeline == [{draft, "Draft", 1, 100.00}, {invoiced, "Invoiced", 1, 200.00}, {complete, "Complete", 0, Decimal(0)}]` | pass |
| EO-FN-07 | R3 | boundary | W1 with no orders | FN() | three stages, each count 0, `total_value == Decimal(0)` | pass |
| EO-FN-08 | R4, R5 | happy | H | FN() | `open_by_account == [{account_id:A1.id, account_name:"Acme Supplies", count:1, total_value:100.00}]` (O2 has no account) | pass |
| EO-FN-09 | R4 | boundary | H | FN(ALL) | `open_by_account == [{A1.id, "Acme Supplies", 2, 500.00}]` (completed O3 / A2 not listed) | pass |
| EO-FN-10 | R6 | boundary | 6 open W1 orders on 6 accounts with totals 100, 200, 300, 400, 500, 600 | FN() | 5 entries, totals `[600, 500, 400, 300, 200]` in that order | pass |
| EO-FN-11 | R6 [BUG-747] | bug | accounts inserted in order "delta", "Charlie", "bravo", "Alpha", "echo", "Foxtrot"; each has one open order with total 100.00 | FN() | `[e["account_name"] for e in open_by_account] == ["Alpha", "bravo", "Charlie", "delta", "echo"]` | xfail BUG-747 — fails today on: tie order differs |
| EO-FN-12 | R7, R8 | happy | NOW = 2026-03-11 (Wed). Open W1 orders inserted in order (numbers EXP-2000-101…): Q1 due 03-10 total 10; Q2 due 03-11 total 20; Q3 due 03-15 total 30; Q4 due 03-16 total 40; Q5 due 03-31 total 50; Q6 due 04-01 total 60; Q7 no due total 70; Q8 due 03-10 voided total 80; Q9 due 03-10 completed total 90; Q10 in W2 due 03-10 total 100 | FN(`expense_category="department"`) (filters must be ignored here) | `due_timeline` keys in order `overdue`, `due_this_week`, `due_later_this_month`, `no_due_date` with labels "Overdue", "Due this week", "Due later this month", "No due date"; counts / totals: 1 / 10.00, 2 / 50.00, 2 / 90.00, 1 / 70.00; Q6, Q8, Q9, Q10 in no bucket | pass |
| EO-FN-13 | R9 | side-effect | as FN-12 | FN() | samples: overdue `[{id:Q1.id, order_number:"EXP-2000-101", total_value:10.00, sublabel:"2026-03-10"}]`; this week `[Q2 "2026-03-11", Q3 "2026-03-15"]`; later `[Q4 "2026-03-16", Q5 "2026-03-31"]`; no due `[{id:Q7.id, …, sublabel:None}]` | pass |
| EO-FN-14 | R8 | boundary | NOW = 2026-03-15 (Sunday); open orders due 03-14, 03-15, 03-16 | FN() | overdue count 1 (03-14); due_this_week count 1 (03-15 only); due_later_this_month count 1 (03-16) | pass |
| EO-FN-15 | R9 | boundary | NOW 2026-03-11; open overdue orders inserted in order: S1 due 03-08 number EXP-2000-101; S2 due 03-05 number EXP-2000-103; S3 due 03-05 number EXP-2000-102; S4 due 03-01 number EXP-2000-104. Open no-due orders N1 EXP-2000-202, N2 EXP-2000-201, N3 EXP-2000-203, N4 EXP-2000-204 | FN() | overdue count 4; overdue sample ids `[S4, S3, S2]`; no_due count 4; no_due sample ids `[N2, N1, N3]` | pass |
| EO-FN-16 | R10, R11 | happy | open W1 orders with invoices: V1 unpaid 1000/0; V2 partial 800/300; V3 overdue 600/0; V4 paid 100/100; V5 unpaid 50/0 but invoice `invoice_status="voided"`; V6 completed order, invoice unpaid 70/0; V7 voided order, invoice unpaid 90/0; V8 no invoice; V9 unpaid 0/0 (amounts are NOT NULL, so the spec's "null counts as 0" is exercised only as a zero-outstanding invoice — gap G11) | FN(`expense_category="department"`) | `unpaid_pipeline` keys in order `unpaid`, `partial`, `overdue`, labels "Unpaid", "Partial", "Overdue"; unpaid count 2, `outstanding_value == 1000.00`; partial count 1, 500.00; overdue count 1, 600.00 | pass |
| EO-FN-17 | R12 | side-effect | as FN-16 | FN() | unpaid samples `[{id:V1.id, order_number:V1 number, total_value:1000.00, sublabel:"unpaid"}, {id:V9.id, …, total_value:0, sublabel:"unpaid"}]`; partial `[{V2, 500.00, "partial"}]`; overdue `[{V3, 600.00, "overdue"}]` | pass |
| EO-FN-18 | R12 | boundary | 4 open orders with unpaid invoices outstanding 100, 300, 200, 400 | FN() | unpaid count 4, outstanding 1000.00; sample totals `[400, 300, 200]` | pass |
| EO-FN-19 | R12 [BUG-748] | bug | open orders K1, K2, K3, K4 (inserted in that order); unpaid invoices of 100/0 each, inserted in order K4, K3, K2, K1 | FN() | unpaid sample ids `[K1, K2, K3]` | xfail BUG-748 — fails today on: tie order differs |
| EO-FN-20 | R13 | boundary | W1 with no orders | FN() | `due_timeline` has 4 buckets, each count 0, `total_value == Decimal(0)`, `samples == []`; `unpaid_pipeline` has 3 buckets, each count 0, `outstanding_value == Decimal(0)`, `samples == []`; `category_breakdown == []`; `open_by_account == []` | pass |
| EO-FN-21 | Errors | error | H | FN(`foo=1`) | `TypeError` | pass |
| EO-FN-22 | R7 | isolation | NOW 2026-03-11; W2 order due 03-10 only | FN() for W1 | overdue count 0 | pass |
| EO-FN-23 | R8, R9 | boundary | NOW = `datetime(2026, 3, 30, 10, 0, 0)` (Monday; coming Sunday 2026-04-05). Open W1 orders inserted in order: M1 due 03-29 total 10; M2 due 03-30 total 20; M3 due 03-31 total 30; M4 due 04-02 total 40; M5 due 04-05 total 50; M6 due 04-06 total 60 | FN() | overdue count 1, total 10.00; due_this_week count 4, total 140.00, sample ids `[M2, M3, M4]`; due_later_this_month count 0, `total_value == Decimal(0)`, `samples == []`; no_due_date count 0; M6 in no bucket | pass |

## `delete_expense_order`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-D-01 | R4, R5 | happy | order O with lines 1, 2, approvers U1, U2, 3 events; order P with 1 line, approver U1, 1 event | `delete_expense_order(session, O.id, W1)` | returns `None`; re-read: no order O, no lines / approvers / events with O's id; P and its line, approver, event unchanged; no new event anywhere | pass |
| EO-D-02 | R1 | error | order O with 1 line | `delete_expense_order(session, MISSING(expense_orders), W1)` | 404 `'Expense order with ID <missing> not found'`; nothing written (O and its line still exist) | pass |
| EO-D-03 | R1 | isolation | O5 in W2 with 1 line | `delete_expense_order(session, O5.id, W1)` | 404 `'Expense order with ID <O5.id> not found'`; O5 and its line still exist | pass |
| EO-D-04 | R2 | error | O completed, no invoice, 1 line | call | 400 `'Cannot delete a completed expense order'`; nothing written (order, line, approvers, events still exist) | pass |
| EO-D-05 | R4 | soft-delete | O voided, no invoice, 1 line | call | returns `None`; O and its line gone | pass |
| EO-D-06 | R3 [BUG-742] | bug | O (no invoice); SQL capture on | call | returns `None`; LOCK | xfail BUG-742 — fails today on: no captured `FOR UPDATE` |
| EO-D-07 | R4 [BUG-742] | bug | O with draft invoice I linked; 1 line | call | 400 `'Void the expense order instead'`; nothing written; invoice I still exists | xfail BUG-742 — fails today on: no exception, order deleted |
| EO-D-08 | R4 [BUG-742] | bug | O with confirmed invoice I linked | call | 400 `'Void the expense order instead'`; O still exists | xfail BUG-742 — fails today on: no exception, order deleted |
| EO-D-09 | R2, R4 | boundary | O completed with confirmed invoice I linked; 1 line | call | 400 `'Cannot delete a completed expense order'` (completed check wins); nothing written (order, line, approvers, events still exist); invoice I still exists | pass |
| EO-D-10 | R5a, R5 [BUG-1193] | bug | order O: `expense_number="EXP-2026-041"`, `created_by=U1`, `created_at=T0`, totals 1234.50; lines 1 (1000.00), 2 (234.50); U1 approved, U3 approved; 3 events | `delete_expense_order(session, O.id, W1, user_id=U2.id)` | 1. returns `None`. 2. re-read: no order O, no lines / approvers / events with O's id. 3. count: AUDIT(O) has exactly 1 row. 4. audit: `workspace_id == W1`, `user_id == U2.id`, `action == "expense_order_deleted"`, `resource_type == "expense_order"`, `resource_id == O.id`. 5. audit: `metadata_json == {"number": "EXP-2026-041", "total_amount": "1234.50", "created_by": U1.id, "created_at": "2026-01-01T09:00:00"}` | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-11 | R5a [BUG-1193] | boundary | order O, default totals 0, no lines | `delete_expense_order(session, O.id, W1, user_id=U2.id)` | 1. returns `None`. 2. count: AUDIT(O) has exactly 1 row. 3. audit: `metadata_json["total_amount"] == "0.00"` (not `"0"`) | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-12 | R5a [BUG-1193] | soft-delete | O voided, `expense_number="EXP-2026-042"`, totals 300.00, 1 line, no invoice | `delete_expense_order(session, O.id, W1, user_id=U2.id)` | 1. returns `None`. 2. re-read: no order O. 3. count: AUDIT(O) has exactly 1 row. 4. audit: `user_id == U2.id`, `metadata_json["number"] == "EXP-2026-042"`, `metadata_json["total_amount"] == "300.00"` | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-13 | R5a [BUG-1193] | isolation | orders O and P in W1, O5 in W2; audit rows already there: one in W1 and one in W2, each `action="member_added"`, `resource_type="member"`, `resource_id=7` | `delete_expense_order(session, O.id, W1, user_id=U2.id)` | 1. returns `None`. 2. count: audit rows in W1 = 2. 3. count: audit rows in W2 = 1. 4. count: AUDIT(O) has exactly 1 row, `workspace_id == W1`. 5. count: AUDIT(P) and AUDIT(O5) have 0 rows. 6. re-read: P and O5 still exist | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-14 | R5a [BUG-1193] | side-effect | order O; a savepoint is opened; a spy wraps the session's `commit` | `delete_expense_order(session, O.id, W1, user_id=U2.id)`, then roll the savepoint back | 1. returns `None`. 2. before the rollback, count: AUDIT(O) has exactly 1 row. 3. before the rollback, re-read: no order O. 4. mock called: `commit` never. 5. after the rollback, re-read: O exists. 6. after the rollback, count: AUDIT(O) has 0 rows | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter). Author: claude |
| EO-D-15 | R1, R5b [BUG-1193] | error | order O with 1 line | `delete_expense_order(session, MISSING(expense_orders), W1, user_id=U2.id)` | 1. 404 `'Expense order with ID <missing> not found'`. 2. count: `workspace_audit_logs` has as many rows as before the call. 3. re-read: O and its line still exist | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-16 | R1, R5b [BUG-1193] | isolation | O5 in W2 with 1 line | `delete_expense_order(session, O5.id, W1, user_id=U2.id)` | 1. 404 `'Expense order with ID <O5.id> not found'`. 2. count: `workspace_audit_logs` has as many rows as before the call. 3. re-read: O5 and its line still exist | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-17 | R2, R5b [BUG-1193] | error | O completed, no invoice; 1 line, U1 pending, 1 event | `delete_expense_order(session, O.id, W1, user_id=U2.id)` | 1. 400 `'Cannot delete a completed expense order'`. 2. count: `workspace_audit_logs` has as many rows as before the call. 3. count: AUDIT(O) has 0 rows. 4. nothing written (order, line, approver, event) | xfail BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-18 | R4, R5b [BUG-742, BUG-1193] | bug | O with draft invoice I linked; 1 line | `delete_expense_order(session, O.id, W1, user_id=U2.id)` | 1. 400 `'Void the expense order instead'`. 2. count: `workspace_audit_logs` has as many rows as before the call. 3. re-read: O and invoice I still exist | xfail BUG-742, BUG-1193 — fails today on: Then 1 (the call raises TypeError: no `user_id` parameter) |
| EO-D-19 | R5c [BUG-1193] | error | order O | `delete_expense_order(session, O.id, W1)` (no `user_id`) | 1. raises `TypeError`. 2. re-read: O still exists. 3. count: AUDIT(O) has 0 rows | xfail BUG-1193 — fails today on: Then 1 (no error: the order is deleted) |

## `add_item`

Default Given: order O with lines 1 ("Line 1", 100.00) and 3 ("Line 3", 50.00) (line 2 was removed earlier), totals 150.00. "add(d)" = `add_item(session, O.id, ExpenseOrderItemCreate(**d), W1, U2.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-AI-01 | R3, R4, R5, R6 | happy | O; no approvals | add(`{description:"Electricity", quantity:2, unit:"month", unit_price:1500.50, notes:"Q1"}`) | returns the line with an id; re-read line: `line_number=4`, description "Electricity", qty 2, unit "month", price 1500.50, notes "Q1", `line_subtotal=3001.00`, `workspace_id=W1`, `expense_order_id=O.id`; lines 1 and 3 unchanged; order `subtotal=total_amount=3151.00`; events exactly `E("item_added", "Line 4 added")`, `performed_by=U2`, `metadata={"line_number": 4}` | pass |
| EO-AI-02 | R3 | boundary | order O with no lines | add(`{description:"Fee", quantity:1, unit_price:10}`) | `line_number == 1`; order totals 10.00 | pass |
| EO-AI-03 | R4, PID R2 | boundary | O | add(`{description:"Fee", unit_price:25}`) (quantity default) | line quantity 1, subtotal 25.00 | pass |
| EO-AI-04 | R4, PID R3 | boundary | O | add(`{description:"Free", quantity:3}`) (no price) | line subtotal 0; order totals 150.00 | pass |
| EO-AI-05 | R1 | error | O | `add_item(session, MISSING(expense_orders), …)` | 404 `'Expense order with ID <missing> not found'`; nothing written (O still has 2 lines, totals 150.00, 0 events) | pass |
| EO-AI-06 | R1 | isolation | O5 in W2 | `add_item(session, O5.id, …, W1, U2.id)` | 404 `'Expense order with ID <O5.id> not found'`; O5 has no new line | pass |
| EO-AI-07 | R2 | error | O completed | add(`{description:"X", quantity:1, unit_price:1}`) | 400 `'Expense order is complete'`; nothing written (2 lines, totals 150.00, 0 events) | pass |
| EO-AI-08 | R2 [BUG-754] | bug | O voided | add(same) | 400 `'Expense order is voided'`; nothing written | xfail BUG-754 — fails today on: line added |
| EO-AI-09 | R2 [BUG-743] | bug | O; SQL capture on | add(same) | returns the line; LOCK | xfail BUG-743 — fails today on: no captured `FOR UPDATE` |
| EO-AI-10 | R7 | side-effect | O; U3 approved, U1 pending | add(`{description:"X", quantity:1, unit_price:1}`) | U3 `approved=False`, `approved_at=None`; events exactly [`E("item_added", "Line 4 added")`, `E("approvals_reset", "Expense items edited (1 approval(s) cleared)")` `performed_by=U2`] | pass |
| EO-AI-11 | R7 | boundary | O; U3 pending | add(same) | 0 `approvals_reset` events; U3 unchanged | pass |

## `update_item`

Default Given: order O with line L1 (line 1, "Paper", qty 2, unit "box", price 10.00, subtotal 20.00, notes "n") and line L2 (line 2, qty 1, price 5.00, subtotal 5.00); totals 25.00. "upd(d)" = `update_item(session, L1.id, ExpenseOrderItemUpdate(**d), W1, U2.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-UI-01 | R5, R6, R7, R8 | happy | O; no approvals | upd(`{quantity: 3}`) | returns L1; re-read L1 qty 3, price 10.00, `line_subtotal=30.00`, description / unit / notes unchanged; order totals 35.00; events exactly `E("item_updated", "Line 1 updated")`, `performed_by=U2`, `metadata=None` | pass |
| EO-UI-02 | R6 | boundary | O | upd(`{unit_price: 12.50}`) | L1 subtotal 25.00 (stored qty 2); totals 30.00 | pass |
| EO-UI-03 | R6 | boundary | O | upd(`{description: "Paper A4", unit: "ream", notes: "m"}`) | L1 description "Paper A4", unit "ream", notes "m"; `line_subtotal` still 20.00; totals 25.00; 1 `item_updated` event | pass |
| EO-UI-04 | R6 | boundary | O with L1 `unit_price=None`, subtotal 0, totals 5.00 | upd(`{quantity: 4}`) | L1 subtotal 0; totals 5.00 | pass |
| EO-UI-05 | R1 | error | O | `update_item(session, MISSING(expense_order_items), {quantity:9}, W1, U2.id)` | 404 `'Expense order item not found'`; nothing written (L1, L2, totals 25.00, 0 events) | pass |
| EO-UI-06 | R1 | isolation | order O5 in W2 with line L5 | `update_item(session, L5.id, {quantity:9}, W1, U2.id)` | 404 `'Expense order item not found'`; L5 unchanged | pass |
| EO-UI-07 | R2 | error | line LX with `workspace_id=W1` whose `expense_order_id` is O5 (W2) (inconsistent data) | `update_item(session, LX.id, {quantity:9}, W1, U2.id)` | 404 `'Expense order with ID <O5.id> not found'`; LX unchanged | pass |
| EO-UI-08 | R3 | error | O completed | upd(`{quantity: 3}`) | 400 `'Expense order is complete'`; nothing written | pass |
| EO-UI-09 | R3 [BUG-754] | bug | O voided | upd(`{quantity: 3}`) | 400 `'Expense order is voided'`; nothing written | xfail BUG-754 — fails today on: line changed |
| EO-UI-10 | R3 [BUG-743] | bug | O; SQL capture on | upd(`{quantity: 3}`) | returns L1; LOCK | xfail BUG-743 — fails today on: no captured `FOR UPDATE` |
| EO-UI-11 | R4 | boundary | O | upd(`{}`) | returns L1; all L1 fields unchanged; totals 25.00 | pass |
| EO-UI-12 | R4 [BUG-753] | bug | O | upd(`{notes: None}`) | re-read L1 `notes is None` | xfail BUG-753 — fails today on: notes still "n" |
| EO-UI-13 | R4, R6 [BUG-753] | bug | O | upd(`{unit_price: None}`) | re-read L1 `unit_price is None`, `line_subtotal == 0`; order totals 5.00 | xfail BUG-753 — fails today on: unit_price still 10.00 |
| EO-UI-14 | R4 [BUG-753] | bug | — | `ExpenseOrderItemUpdate(quantity=None)` | rejects | xfail BUG-753 — fails today on: no ValidationError |
| EO-UI-15 | R8 [BUG-740] | bug | O | upd(`{}`) | 0 events | xfail BUG-740 — fails today on: 1 `item_updated` event |
| EO-UI-16 | R8 [BUG-740] | bug | O | upd(`{quantity: 2, description: "Paper"}`) (same values) | 0 events | xfail BUG-740 — fails today on: 1 `item_updated` event |
| EO-UI-17 | R9 | side-effect | O; U3 approved | upd(`{quantity: 3}`) | U3 `approved=False`, `approved_at=None`; events include exactly one `E("item_updated", "Line 1 updated")` and one `E("approvals_reset", "Expense items edited (1 approval(s) cleared)")` `performed_by=U2` (order not asserted) | pass |
| EO-UI-18 | R9 [BUG-740] | bug | O; U3 approved | upd(`{}`) | U3 still `approved=True`, `approved_at=T0`; 0 `approvals_reset` events | xfail BUG-740 — fails today on: U3 approval cleared |
| EO-UI-19 | R9 | boundary | O; U3 pending | upd(`{quantity: 3}`) | 0 `approvals_reset` events | pass |
| EO-UI-20 | Inputs [BUG-751] | bug | — | inspect `ExpenseOrderItemUpdate.model_fields` | `"approved" not in ExpenseOrderItemUpdate.model_fields` | xfail BUG-751 — fails today on: field present |
| EO-UI-21 | R6 | boundary | O | upd(`{quantity: 3, unit_price: 4}`) | L1 subtotal 12.00; totals 17.00 | pass |

## `remove_item`

Default Given: order O with lines 1 (10.00), 2 (20.00), 3 (30.00); totals 60.00. "rm(L)" = `remove_item(session, L.id, W1, U2.id)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-RI-01 | R4, R5, R6 | happy | O; no approvals | rm(line 2) | returns an object with `line_number == 2` and `expense_order_id == O.id`; re-read: line 2 gone; lines 1 and 3 keep numbers 1 and 3; order totals 40.00; events exactly `E("item_removed", "Line 2 removed")`, `performed_by=U2` | pass |
| EO-RI-02 | R5 | boundary | order with a single line (10.00), totals 10.00 | rm(that line) | order `subtotal == total_amount == 0` | pass |
| EO-RI-03 | R1 | error | O | `remove_item(session, MISSING(expense_order_items), W1, U2.id)` | 404 `'Expense order item not found'`; nothing written (3 lines, totals 60.00, 0 events) | pass |
| EO-RI-04 | R1 | isolation | O5 in W2 with line L5 | `remove_item(session, L5.id, W1, U2.id)` | 404 `'Expense order item not found'`; L5 still exists | pass |
| EO-RI-05 | R2 | error | line LX (`workspace_id=W1`, order O5 in W2) | `remove_item(session, LX.id, W1, U2.id)` | 404 `'Expense order with ID <O5.id> not found'`; LX still exists | pass |
| EO-RI-06 | R3 | error | O completed | rm(line 2) | 400 `'Expense order is complete'`; nothing written (3 lines, totals 60.00, 0 events) | pass |
| EO-RI-07 | R3 [BUG-754] | bug | O voided | rm(line 2) | 400 `'Expense order is voided'`; nothing written | xfail BUG-754 — fails today on: line removed |
| EO-RI-08 | R3 [BUG-743] | bug | O; SQL capture on | rm(line 2) | LOCK | xfail BUG-743 — fails today on: no captured `FOR UPDATE` |
| EO-RI-09 | R7 | side-effect | O; U3 approved | rm(line 2) | U3 `approved=False`, `approved_at=None`; events exactly [`E("item_removed", "Line 2 removed")`, `E("approvals_reset", "Expense items edited (1 approval(s) cleared)")`] | pass |
| EO-RI-10 | R7 | boundary | O; U3 pending | rm(line 2) | 0 `approvals_reset` events | pass |

## `get_items`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-GI-01 | R2 | happy | order O; lines inserted in order line_number 3, 1, 2 | `get_items(session, O.id, W1)` | returns 3 lines with line_numbers `[1, 2, 3]` | pass |
| EO-GI-02 | R2 | boundary | order O without lines | call | `[]` | pass |
| EO-GI-03 | R1 | error | — | MISSING(expense_orders) | 404 `'Expense order with ID <missing> not found'` | pass |
| EO-GI-04 | R1 | isolation | O5 in W2 with lines | `get_items(session, O5.id, W1)` | 404 | pass |
| EO-GI-05 | R2 | isolation | order O with line 1 (W1) and a line 2 row for O with `workspace_id=W2` | call | returns only line 1 | pass |

## `_recalc_totals`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-RT-01 | R1 | happy | order O with totals 0; lines with `line_subtotal` 10.00, 20.50 and `None` | `_recalc_totals(session, O)` | re-read O `subtotal == total_amount == 30.50` | pass |
| EO-RT-02 | R1 | boundary | order O with totals 99.00, no lines | call | re-read `subtotal == total_amount == 0` | pass |
| EO-RT-03 | R1 | isolation | order O: line 10.00 (W1) and a line for O with `workspace_id=W2`, subtotal 500.00 | call | re-read totals 10.00 | pass |

## `list_approvers`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-LA-01 | R2, R3, R4 | happy | order O; approvers inserted U3 (assigned_at T0+2h), U2 (T0+1h), U1 (T0+3h) | `list_approvers(session, O.id, W1)` | 3 tuples in order U2, U3, U1; U2's tuple = (approver row of U2, profile U2, "Accountant"); U3's position `None` (member without position) | pass |
| EO-LA-02 | R4 | boundary | order O; approver U3 whose W1 membership status is `suspended` with position "Driver" | call | U3's position `"Driver"` | pass |
| EO-LA-03 | R4 | isolation | order O; approver U4 (member of W2 only, position "Clerk" there) | call | U4's tuple has profile U4 and position `None` | pass |
| EO-LA-05 | R5 | boundary | order O with no approvers | call | `[]` | pass |
| EO-LA-06 | R1 | error | — | MISSING(expense_orders) | 404 `'Expense order with ID <missing> not found'` | pass |
| EO-LA-07 | R1 | isolation | O5 in W2 | `list_approvers(session, O5.id, W1)` | 404 | pass |

## `approval_summary`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-AS-01 | R1, R3, R5 | happy | order O; U1 approved, U2 approved, U3 pending | `approval_summary(session, O)` | `(2, 3, False)` | pass |
| EO-AS-02 | R3, R5 | boundary | O; U1, U2 both approved | call | `(2, 2, True)` | pass |
| EO-AS-03 | R2, R5 | boundary | O `required_approvals=2`; U1, U2 approved, U3 pending | call | `(2, 2, True)` | pass |
| EO-AS-04 | R2, R5 | boundary | O `required_approvals=2`; U1 approved, U2, U3 pending | call | `(1, 2, False)` | pass |
| EO-AS-05 | R2 | boundary | O `required_approvals=0`; no approvers | call | `(0, 0, True)` | pass |
| EO-AS-06 | R4 [BUG-755] | bug | O `required_approvals=None`; no approvers | call | `(0, 1, False)` | xfail BUG-755 — fails today on: returns `(0, 0, True)` |
| EO-AS-07 | R1 | isolation | O: U1 pending; order P: U1 approved | call for O | `(0, 1, False)` | pass |

## `approvals_met`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-AM-01 | R1 | happy | as AS-02 | `approvals_met(session, O)` | `True` | pass |
| EO-AM-02 | R1 | boundary | as AS-01 | call | `False` | pass |
| EO-AM-03 | R1 [BUG-755] | bug | as AS-06 | call | `False` | xfail BUG-755 — fails today on: `True` |

## `add_approver`

"aa(u)" = `add_approver(session, O.id, u.id, W1, assigned_by=U1.id)`; O = default order with approver U1 approved.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-AA-01 | R4, R5, R6 | happy | O | aa(U3) | returns the row: `user_id=U3`, `assigned_by=U1`, `approved=False`, `approved_at=None`, `assigned_at` within the real-clock window (see Time); re-read: O has 2 approvers; U1 still `approved=True`, `approved_at=T0`; events exactly `E("approver_added", "Added Rahim Uddin as approver")`, `performed_by=U1`, `metadata={"user_id": U3.id, "user_name": "Rahim Uddin"}` | pass |
| EO-AA-02 | R1 | error | — | `add_approver(session, MISSING(expense_orders), U3.id, W1, U1.id)` | 404 `'Expense order with ID <missing> not found'`; no approver row for U3 and no event in W1 | pass |
| EO-AA-03 | R1 | isolation | O5 in W2 | `add_approver(session, O5.id, U3.id, W1, U1.id)` | 404; O5 has no new approver | pass |
| EO-AA-04 | R1 [BUG-756] | bug | O completed | aa(U3) | 400 `'Expense order is complete'`; nothing written | xfail BUG-756 — fails today on: approver added |
| EO-AA-05 | R1 [BUG-754] | bug | O voided | aa(U3) | 400 `'Expense order is voided'`; nothing written | xfail BUG-754 — fails today on: approver added |
| EO-AA-06 | R2 | error | profile U5 with no membership anywhere | aa(U5) | 400 `'User is not an active member of this workspace'`; nothing written | pass |
| EO-AA-07 | R2 | boundary | U3's W1 membership `suspended` | aa(U3) | 400 same detail; nothing written | pass |
| EO-AA-08 | R2 | boundary | U3's W1 membership `invited` | aa(U3) | 400 same detail; nothing written | pass |
| EO-AA-09 | R2 | isolation | U4 (active member of W2 only) | aa(U4) | 400 same detail; nothing written | pass |
| EO-AA-10 | R3 | error | O (U1 already approver) | aa(U1) | 409 `'User is already an approver for this order'`; still 1 approver; 0 events | pass |

## `remove_approver`

O = default order with approvers U1 approved and U3 pending.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-RAP-01 | R2, R3, R4 | happy | O | `remove_approver(session, O.id, U3.id, W1, performed_by=U1.id)` | returns `None`; re-read: U3 row gone; U1 still approved with `approved_at=T0`; events exactly `E("approver_removed", "Removed Rahim Uddin as approver")`, `performed_by=U1`, `metadata={"user_id": U3.id, "user_name": "Rahim Uddin"}` | pass |
| EO-RAP-02 | R3 | boundary | O | `remove_approver(session, O.id, U3.id, W1)` (no performed_by) | returns `None`; event `performed_by is None` | pass |
| EO-RAP-03 | R1 | error | O | remove U2 (not an approver) | 404 `'Approver not found'`; nothing written | pass |
| EO-RAP-04 | R1 | error | O | `remove_approver(session, MISSING(expense_orders), U1.id, W1)` | 404 `'Approver not found'`; nothing written (O's U1 and U3 rows unchanged, 0 events) | pass |
| EO-RAP-05 | R1 | isolation | O5 in W2 with approver U4 | `remove_approver(session, O5.id, U4.id, W1)` | 404 `'Approver not found'`; U4 row still exists | pass |
| EO-RAP-06 | R1 [BUG-756] | bug | O completed | remove U1 | 400 `'Expense order is complete'`; U1 row still exists; 0 events | xfail BUG-756 — fails today on: row deleted |
| EO-RAP-07 | R1 | boundary | O completed | remove U2 (not an approver) | 404 `'Approver not found'` (approver lookup first) | pass |
| EO-RAP-08 | R1 | soft-delete | O voided | remove U3 | returns `None`; U3 row gone; 1 `approver_removed` event | pass |

## `set_approval`

O = ready order R with approver U2 pending. "sa(u, v)" = `set_approval(session, O.id, u.id, W1, approved=v)`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-SA-01 | R6 | happy | O | sa(U2, True) | returns U2's row; re-read `approved=True`, `approved_at=NOW`; events exactly `E("approved", "Approved expense order")`, `performed_by=U2` | pass |
| EO-SA-02 | R7 | happy | O, U2 approved | sa(U2, False) | returns the row; re-read `approved=False`, `approved_at=None`; events exactly `E("approval_withdrawn", "Withdrew approval")`, `performed_by=U2` | pass |
| EO-SA-03 | R1 | error | O | sa(U3, True) (not an approver) | 403 `'You are not an assigned approver for this order'`; nothing written | pass |
| EO-SA-04 | R1 | boundary | O | `set_approval(session, MISSING(expense_orders), U2.id, W1, True)` | 403 `'You are not an assigned approver for this order'`; nothing written (U2 still pending, 0 events) | pass |
| EO-SA-05 | R1 | isolation | O5 in W2 with approver U4 | `set_approval(session, O5.id, U4.id, W1, True)` | 403; U4 still pending | pass |
| EO-SA-06 | R2 | error | approver row for U2 with `workspace_id=W1` and `expense_order_id` = O5 (W2) (inconsistent data) | `set_approval(session, O5.id, U2.id, W1, True)` | 404 `'Expense order with ID <O5.id> not found'`; row unchanged | pass |
| EO-SA-07 | R3 | boundary | O completed (still ready) | sa(U2, True) | returns the row; `approved=True` | pass |
| EO-SA-08 | R4 [BUG-754] | bug | O voided | sa(U2, True) | 400 `'Expense order is voided'`; nothing written | xfail BUG-754 — fails today on: approval recorded |
| EO-SA-09 | R4 | error | O with `description="   "` | sa(U2, True) | 400 `'Add a description before approvals can proceed'`; nothing written | pass |
| EO-SA-10 | R4 | error | O with all lines removed | sa(U2, True) | 400 `'Add at least one expense line before approvals can proceed'`; nothing written | pass |
| EO-SA-11 | R4 | error | O plus line 2 with `quantity=0` | sa(U2, True) | 400 (status only); nothing written | pass |
| EO-SA-12 | R4 [BUG-758] | bug | as SA-11 | sa(U2, True) | 400 `'Every expense line needs a description and a quantity above 0 before approvals can proceed'`; nothing written | xfail BUG-758 — fails today on: detail is `'Order is not ready for approval'` |
| EO-SA-13 | R4 [BUG-744] | bug | O; SQL capture on | sa(U2, True) | LOCK | xfail BUG-744 — fails today on: no captured `FOR UPDATE` |
| EO-SA-14 | R5 [BUG-744] | bug | O, U2 approved; SQL capture on | sa(U2, False) | LOCK | xfail BUG-744 — fails today on: no captured `FOR UPDATE` |
| EO-SA-15 | R5 | error | O completed, U2 approved | sa(U2, False) | 400 `'Cannot withdraw approval — order is complete'`; U2 still approved, `approved_at=T0`; 0 events | pass |
| EO-SA-16 | R3, R7 | soft-delete | O voided, U2 approved | sa(U2, False) | returns the row; `approved=False`; 1 `approval_withdrawn` event | pass |
| EO-SA-17 | R7 | boundary | O with `description=None` (not ready), U2 approved | sa(U2, False) | succeeds; `approved=False` (readiness not checked) | pass |
| EO-SA-18 | R6 [BUG-757] | bug | O, U2 approved (`approved_at=T0`) | sa(U2, True) | returns the row; re-read `approved=True`, `approved_at == T0`; 0 events | xfail BUG-757 — fails today on: `approved_at == NOW` |
| EO-SA-19 | R7 [BUG-757] | bug | O, U2 pending | sa(U2, False) | returns the row; `approved=False`; 0 events | xfail BUG-757 — fails today on: 1 `approval_withdrawn` event |
| EO-SA-20 | R6 | boundary | O, U2 approved | sa(U2, True) | returns the row; re-read `approved=True` (holds today and after the fix) | pass |
| EO-SA-21 | R6 | isolation | O with approvers U2 pending, U3 pending | sa(U2, True) | returns U2's row; U3 unchanged (pending) | pass |
| EO-SA-22 | R7 | boundary | O, U2 pending | sa(U2, False) | returns U2's row; re-read `approved=False`, `approved_at=None` (holds today and after the fix; pass partner of SA-19) | pass |

## `log_event`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-LE-01 | R1 | happy | order O | `log_event(session, O.id, W1, "note", "Called vendor", performed_by=U2.id, metadata={"k": 1})` | returns the event with an id; re-read: `workspace_id=W1`, `expense_order_id=O.id`, `event_type="note"`, description "Called vendor", `performed_by=U2`, `metadata={"k": 1}`, `created_at` within the real-clock window (see Time) | pass |
| EO-LE-02 | R1 | boundary | O | `log_event(session, O.id, W1, "note", "x")` | `performed_by is None`, `metadata is None` | pass |
| EO-LE-03 | R2 | boundary | O in W1 | `log_event(session, O.id, W2, "note", "x")` | succeeds; re-read event `workspace_id=W2`, `expense_order_id=O.id` | pass |
| EO-LE-04 | R2 | error | — | `log_event(session, MISSING(expense_orders), W1, "note", "x")` inside savepoint | raises `IntegrityError`; after rollback no event with that order id | pass |
| EO-LE-05 | R2 | boundary | O | `event_type="e"*50` | succeeds; `event_type == "e"*50` | pass |
| EO-LE-06 | R2 | error | O | `event_type="e"*51` inside savepoint | raises `sqlalchemy.exc.DBAPIError` (any subclass) (best-practice default, delegated by reviewer); after rollback 0 events for O | pass |

## `list_events`

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-LV-01 | R2, R3 | happy | order O; events inserted: E1 `created_at` T0 by U1; E2 T0+2h by U2; E3 T0+1h with `performed_by=None` | `list_events(session, O.id, W1)` | `[(E2, profile U2), (E3, None), (E1, profile U1)]` | pass |
| EO-LV-02 | R2 | boundary | O; E1 and E2 both `created_at` T0 (E2 id > E1 id) | call | `[E2, E1]` | pass |
| EO-LV-03 | R2 | boundary | O with no events | call | `[]` | pass |
| EO-LV-04 | R2 | isolation | O with E1; order P with E9 | call for O | only E1 | pass |
| EO-LV-05 | R1 | error | — | MISSING(expense_orders) | 404 `'Expense order with ID <missing> not found'` | pass |
| EO-LV-06 | R1 | isolation | O5 in W2 | `list_events(session, O5.id, W1)` | 404 | pass |
| EO-LV-07 | R3 | boundary | O; event E1 inserted with `performed_by=U3`; then U3's profile row is deleted and flushed (FK `ON DELETE SET NULL`) | call | re-read E1 `performed_by is None`; result `[(E1, None)]` | pass |

## `create_expense_order_from_template`

Template TPL of W1: name "Monthly rent", description "Rent for the plant", category factory, cost center F1, account A1, `is_active=True`, `requires_approval=True`, `auto_approve=False`, `default_approver_id=None`. Template lines inserted in order line_number 5 ("Service", qty 2, unit "month", price 250.00, notes "svc") then line_number 2 ("Rent", qty 1, price 5000.00). "ft(o)" = `create_expense_order_from_template(session, TPL.id, W1, U1.id, ExpenseOrderFromTemplateCreate(**o))`.

| ID | Rules | Kind | Given | When | Then | Expect |
|---|---|---|---|---|---|---|
| EO-T-01 | R3, R4, R7, R9, R10 | happy | TPL; W1 has no orders | ft(`{expense_date: 2026-04-01, due_date: 2026-04-30}`) | returns an order; re-read: account A1, category factory, cost center F1, expense_date 2026-04-01, due_date 2026-04-30, description "Rent for the plant", `order_template_id=TPL.id`, `required_approvals=None`, `expense_number=f"EXP-{Y}-001"`; lines: 1 "Rent" qty 1 price 5000.00 subtotal 5000.00; 2 "Service" qty 2 unit "month" price 250.00 notes "svc" subtotal 500.00; totals 5500.00; approvers exactly [U1 pending]; events exactly [`E("created", "Expense order created")`, `E("created_from_template", 'Generated from template "Monthly rent"')` `metadata={"order_template_id": TPL.id}`, `performed_by=U1`] | pass |
| EO-T-02 | R1 | error | — | template id MISSING(order_templates) | 404 `'Order template with ID <missing> not found'`; no order in W1 | pass |
| EO-T-03 | R1 | isolation | template TW2 of W2 | `create_expense_order_from_template(session, TW2.id, W1, U1.id, …)` | 404 `'Order template with ID <TW2.id> not found'`; no order in W1 | pass |
| EO-T-04 | R2 | error | TPL `is_active=False` | ft(`{}`) | 400 `'Template is inactive'`; no order in W1 | pass |
| EO-T-05 | R3 | boundary | TPL | ft(`{}`) | expense_date `date.today()`, `due_date is None` | pass |
| EO-T-06 | R3 | boundary | TPL | ft(`{description: "April rent"}`) | description "April rent" | pass |
| EO-T-07 | R3 | boundary | TPL | ft(`{description: ""}`) | description "Rent for the plant" | pass |
| EO-T-08 | R3 | boundary | TPL with category `None`, cost center `None` | ft(`{}`) | category "other", `cost_center_id is None` | pass |
| EO-T-09 | R3 | boundary | TPL with category `""`, cost center `None` | ft(`{}`) | category "other" | pass |
| EO-T-10 | R3 [BUG-752] | bug | TPL with category `None`, cost center F1 | ft(`{}`) | category "other", `cost_center_id is None` | xfail BUG-752 — fails today on: `cost_center_id == F1.id` |
| EO-T-11 | R3, C R2 | error | TPL with `description=None` | ft(`{}`) | 400 `'Description is required'`; no order in W1 | pass |
| EO-T-12 | R3, C R1 | error | TPL with cost center F2 (W2) | ft(`{}`) | 404 `'Selected factory not found'`; no order in W1 | pass |
| EO-T-13 | R5, R10 | happy | TPL `requires_approval=False`, `auto_approve=True` | ft(`{}`) | `required_approvals == 0`; approvers [U1 pending]; events exactly [`created`, `created_from_template`] (no `auto_approved`) | pass |
| EO-T-14 | R6, R9, R10 | happy | TPL `requires_approval=True`, `auto_approve=True` | ft(`{}`) | `required_approvals == 0`; approvers [U1]; events exactly [`E("created", …)`, `E("auto_approved", "Auto-approved — following template instructions")` `metadata={"order_template_id": TPL.id}` `performed_by=U1`, `E("created_from_template", …)`] | pass |
| EO-T-15 | R7, R9 | happy | TPL `default_approver_id=U3` (active) | ft(`{}`) | `required_approvals is None`; approvers U1 and U3; U3 `assigned_by=U1`, pending; events exactly [`created`, `E("approver_added", "Added Rahim Uddin as approver")` `performed_by=U1`, `created_from_template`] | pass |
| EO-T-16 | R7 | boundary | TPL `default_approver_id=U1` (the creator) | ft(`{}`) | approvers exactly [U1]; no `approver_added` event | pass |
| EO-T-17 | R8 [BUG-759] | bug | TPL `default_approver_id=U3`; U3's W1 membership `suspended` | ft(`{}`) | returns an order; approvers exactly [U1]; events exactly [`created`, `E("default_approver_skipped", "Default approver Rahim Uddin is not an active member and was skipped")` `metadata={"user_id": U3.id, "user_name": "Rahim Uddin"}` `performed_by=U1`, `created_from_template`] | xfail BUG-759 — fails today on: 400 `User is not an active member of this workspace` raised |
| EO-T-18 | R8 [BUG-759] | bug | TPL `default_approver_id=U4` (member of W2 only) | ft(`{}`) | order created; approvers [U1]; one `default_approver_skipped` event | xfail BUG-759 — fails today on: 400 raised |
| EO-T-19 | R4 | boundary | TPL with no lines | ft(`{}`) | order created with 0 lines, totals 0 | pass |
| EO-T-20 | R3, C R2 | error | TPL | ft(`{description: "   "}`) | 400 `'Description is required'` (override used as given, not replaced by the template's); no order, line, approver or event in W1 | pass |
| EO-T-21 | R3, VA R2 | boundary | TPL with category `None`, cost center F1 | ft(`{}`) | returns an order (no exception); re-read category "other", `order_template_id=TPL.id` (holds today and after the fix; pass partner of T-10) | pass |

## Deferred to other specs

| Rule | Owner | What must be tested there |
|---|---|---|
| `create_expense_order` R6 [BUG-749] race-safety | integration tests (two sessions) | Two concurrent creates in one workspace both succeed with distinct numbers |
| HR-10 locks (`update_expense_order` R3/R13, `delete_expense_order` R3, `add_item`/`update_item`/`remove_item`, `set_approval` R4/R5) | integration tests (two sessions) | The loser of a race sees the new state and gets the normal 400; totals equal the sum of the lines. The lock clause itself is unit-tested here by SQL capture |
| `create_expense_order` R6 [BUG-749] migration | alembic migration tests | `ix_expense_orders_expense_number` dropped; `uq_eo_workspace_number` kept |
| Schema 422s (BUG-021, BUG-362, BUG-753, BUG-751) | endpoint tests (`POST/PATCH /expense-orders…`) | The API returns 422 for the rejected payloads. The schemas themselves are unit-tested here |
| `delete_expense_order` R5c [BUG-1193] | `ExpenseOrderService.delete_expense_order`, `DELETE /expense-orders/{id}/` | The endpoint passes the current user and the service hands it on as `user_id`; a failure rolls back the delete and the audit row together |
| Overview: invoice drafting, completion, voiding, notifications, `items_updated_at` | `ExpenseOrderService`, `approval_notification_service` | Service-layer behavior built on this manager |

## Spec gaps

Revision-1 gaps G1–G10 closed by the spec's Gap log; see the Revision line.

| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| G11 | `expense_order_financial_snapshot` R10, R11 | R10 says an invoice counts when it "is not `voided`", and R11 says "null amounts count as 0". Verifier finding #9 reports that the invoice has no `voided` column (voiding is `invoice_status="voided"`) and that `invoice_amount` / `paid_amount` are NOT NULL. The spec should name the real field and state that the null-amount fallback is defensive and unreachable. | Weakens only, does not block. EO-FN-16/17 now use `invoice_status="voided"` for V5 and 0 instead of null for V3/V9 (best-practice default, delegated by reviewer). R11's null fallback has no case. |

## Retired IDs

- EO-LA-04 — `list_approvers` R3 profile-missing branch is unreachable with real FKs (approver `user_id` CASCADE); spec says no case required.
- EO-AA-11 — `add_approver` R5 `'User #<id>'` fallback is unreachable (membership `user_id` CASCADE); spec says no case required.
- EO-RAP-09 — `remove_approver` R3 `'User #<id>'` fallback is unreachable (approver `user_id` CASCADE); spec says no case required.

## Coverage matrix

| Callable | Rule / Error row | Cases |
|---|---|---|
| `_has_recorded_approvals` | R1 | HRA-01, HRA-05 |
| | R2 | HRA-02, HRA-03 |
| | R3 | HRA-04 |
| `is_approvable` | R1 | IA-02, IA-03, IA-04 |
| | R2 | IA-05, IA-06, IA-07 |
| | R3 | IA-08, IA-09, IA-10, IA-11 |
| | R4 | IA-12, IA-20 |
| | R5 | IA-13 … IA-18 |
| | R6 | IA-01, IA-07, IA-18, IA-19 |
| `approvability_gap_reason` | R1 | GR-02, GR-03, GR-10 |
| | R2 | GR-04, GR-05, GR-06, GR-11 |
| | R3 | GR-07, GR-08, GR-12 |
| | R4 | GR-09 |
| | R5 | GR-01, GR-15 |
| | R6 [BUG-758] | GR-13, GR-14 |
| `_validate_order_allocation` | R1 / Errors R1 | VA-03, VA-04, VA-05 |
| | R2 [BUG-752] | VA-06, VA-07 (the clearing is on the callers: C-21, U-17, U-18, T-10) |
| | R3 / Errors R3 | VA-08, VA-09 |
| | R4 / Errors R4 | VA-01, VA-10, VA-11 |
| | R5 [BUG-340] | VA-12, VA-13 |
| | R6 [BUG-340] / Errors R6 | VA-02, VA-14, VA-15, VA-16, VA-17, VA-19 |
| | R7 | VA-18 |
| `resolve_invoice_account_id` | R1 | RIA-01, RIA-04 |
| | R2 / Errors | RIA-02, RIA-03 |
| `reset_approvals` | R1, R2 | RA-01, RA-05 |
| | R3 | RA-01, RA-02 |
| | R4 | RA-03, RA-04 |
| `_format_scalar_value` | R1 | FS-01 |
| | R2 | FS-02, FS-03 |
| | R3 | FS-04, FS-05, FS-06 |
| | R4 | FS-07 … FS-11 |
| | R5 | FS-12 |
| `_collect_field_changes` | R1 | CF-01 |
| | R2 | CF-01 … CF-04, CF-07 |
| | R3 | CF-05 |
| | R4 | CF-06 |
| `_guard_confirmed_updates` | R1 / Errors | GCU-01 |
| | R2 | GCU-02 |
| | R3 [BUG-754] | GCU-03 |
| | R4 | GCU-04 |
| | R5 | GCU-05 |
| `_guard_item_mutations` | R1 / Errors | GIM-01 |
| | R2 [BUG-754] | GIM-02 |
| | R3 | GIM-03 |
| `_prepare_item_dict` | R1 | PID-01, PID-02 |
| | R1 [BUG-021] | PID-07, PID-08, PID-09, PID-11 (accepted boundary PID-10) |
| | R1 [BUG-362] | PID-12, PID-13, PID-14, PID-16 (accepted boundaries PID-15, PID-17) |
| | R2 | PID-03, C-26, AI-03 |
| | R3 | PID-04, PID-05, PID-06, AI-04 |
| `create_expense_order` | R1 / Errors R1 | C-10, C-11, C-12, C-13 [BUG-340], C-14, C-31 |
| | R2 / Errors R2 | C-14, C-15, C-16, C-17, C-18 |
| | R3 | C-01, C-18, C-19, C-20 |
| | R3 [BUG-752] | C-21 |
| | R4 | C-22 |
| | R5 | C-01 |
| | R6 | C-02, C-03, C-04, C-05, C-06, C-09 |
| | R6 [BUG-749] | C-07, C-08 (race part deferred) |
| | R7 | C-01 |
| | R8 | C-01, C-25, C-26 |
| | R9 | C-01, C-23, C-24 |
| | R10 | C-01 |
| | R11 [BUG-362] | PID-12 … PID-16 (schema) |
| | R12 [BUG-750] / Errors R12 | C-27, C-28, C-29 |
| | Inputs [BUG-750] `order_template_id` | C-30 |
| `update_expense_order` | R1 / Errors R1 | U-03, U-04 |
| | R2 | U-01, U-29 |
| | R2 [BUG-753] | U-30, U-31, U-32, U-33, U-34, U-45 |
| | R3 / Errors R3 | U-05, U-06, U-08 |
| | R3 [BUG-754] | U-07, U-47 |
| | R3 [BUG-753] (all-null payload) | U-46, U-47 |
| | R3, R13 [BUG-741] | U-09 |
| | R4 / Errors R4 | U-10, U-11, U-12, U-13, U-14, U-44 |
| | R5 | U-15 |
| | R6 [BUG-752] | U-16 (pass part), U-17, U-18 |
| | R7 | U-01, U-12, U-19 |
| | R8 | U-20, U-23 |
| | R9 | U-21 (description), U-25 (expense_date), U-48 (account_id), U-49 (expense_category), U-50 (cost_center_id), U-51 (due_date) |
| | R9 [BUG-740] | U-22 |
| | R10 | U-01, U-20, U-22, U-23, U-24 |
| | R11 | U-21, U-48, U-49, U-50, U-51 |
| | R12 [BUG-750] / Errors R12 | U-35, U-36, U-37, U-38 |
| | R12 [BUG-004] / Errors R12 | U-39, U-40, U-45 |
| | R12 [BUG-362] | U-41, U-42 |
| | R14 | U-02 |
| | R14 [BUG-740] | U-26, U-27, U-28 |
| | Inputs [BUG-751] `invoice_id` | U-43 |
| `get_expense_order` | R1 | G-01, G-02 |
| | R2 / Errors | G-03, G-04 |
| `list_expense_orders_for_hub` | R1 | HL-01, HL-03 |
| | R2 | HL-06, HL-07, HL-08 |
| | R3 | HL-09 … HL-12 |
| | R4 | HL-13 … HL-16 |
| | R5 | HL-17 … HL-23, HL-44 |
| | R6 | HL-24, HL-25, HL-26 |
| | R7 | HL-02, HL-04, HL-44 |
| | R8 | HL-02, HL-05 |
| | R9 | HL-27 … HL-34 |
| | R10 | HL-35, HL-36 |
| | R11 | HL-37 |
| | R11 [BUG-745] | HL-38, HL-39, HL-45, HL-46, HC-07, HR-07 |
| | R12 | HL-40, HL-41, HL-42 |
| | Errors (TypeError) | HL-43 |
| `count_expense_orders_for_hub` | R1 | HC-01 … HC-06, HC-09 |
| | Errors | HC-08 |
| `expense_order_hub_stats` | R1–R3 | HS-01, HS-02, HS-03, HS-05 |
| | R4 | HS-04 |
| | Errors | HS-06 |
| `list_expense_orders_recent_for_hub` | R1 | HR-01 … HR-04, HR-07 |
| | R2 | HR-05 |
| | R2 [BUG-746] | HR-06 |
| | Errors | HR-08 |
| `expense_order_financial_snapshot` | R1 | FN-01, FN-02, FN-03 |
| | R2 | FN-04, FN-20 |
| | R3 | FN-05, FN-06, FN-07 |
| | R4 | FN-08, FN-09 |
| | R5 | FN-08 |
| | R6 | FN-10 |
| | R6 [BUG-747] | FN-11 |
| | R7 | FN-12, FN-22 |
| | R8 | FN-12, FN-14, FN-23 |
| | R9 | FN-13, FN-15, FN-23 |
| | R10 | FN-16 |
| | R11 | FN-16 |
| | R12 | FN-17, FN-18 |
| | R12 [BUG-748] | FN-19 |
| | R13 | FN-20 |
| | Errors | FN-21 |
| `delete_expense_order` | R1 / Errors R1 | D-02, D-03 |
| | R2 / Errors R2 | D-04, D-09 |
| | R3 [BUG-742] | D-06 |
| | R4 | D-01, D-05, D-09 |
| | R4 [BUG-742] / Errors R4 | D-07, D-08 |
| | R5 | D-01 |
| | R5a [BUG-1193] | D-10, D-11, D-12, D-13, D-14 |
| | R5b [BUG-1193] | D-15, D-16, D-17, D-18 |
| | R5c [BUG-1193] / Errors R5c | D-19 |
| `add_item` | R1 / Errors R1 | AI-05, AI-06 |
| | R2 / Errors R2 | AI-07 |
| | R2 [BUG-754] | AI-08 |
| | R2 [BUG-743] | AI-09 |
| | R3 | AI-01, AI-02 |
| | R4 | AI-01, AI-03, AI-04 |
| | R5 | AI-01, AI-02 |
| | R6 | AI-01 |
| | R7 | AI-10, AI-11 |
| `update_item` | R1 / Errors R1 | UI-05, UI-06 |
| | R2 / Errors R2 | UI-07 |
| | R3 / Errors R3 | UI-08 |
| | R3 [BUG-754] | UI-09 |
| | R3 [BUG-743] | UI-10 |
| | R4 | UI-11 |
| | R4 [BUG-753] | UI-12, UI-13, UI-14 |
| | R5 | UI-03 |
| | R6 | UI-01, UI-02, UI-03, UI-04, UI-21 |
| | R7 | UI-01, UI-02, UI-21 |
| | R8 | UI-01, UI-03 |
| | R8 [BUG-740] | UI-15, UI-16 |
| | R9 | UI-17, UI-19 |
| | R9 [BUG-740] | UI-18 |
| | Inputs [BUG-751] `approved` | UI-20 |
| `remove_item` | R1 | RI-03, RI-04 |
| | R2 | RI-05 |
| | R3 | RI-06 |
| | R3 [BUG-754] | RI-07 |
| | R3 [BUG-743] | RI-08 |
| | R4 | RI-01 |
| | R5 | RI-01, RI-02 |
| | R6 | RI-01 |
| | R7 | RI-09, RI-10 |
| `get_items` | R1 / Errors | GI-03, GI-04 |
| | R2 | GI-01, GI-02, GI-05 |
| `_recalc_totals` | R1 | RT-01, RT-02, RT-03 |
| `list_approvers` | R1 / Errors | LA-06, LA-07 |
| | R2 | LA-01 |
| | R3 | LA-01 (profile-missing branch unreachable per spec Notes) |
| | R4 | LA-01, LA-02, LA-03 |
| | R5 | LA-05 |
| `approval_summary` | R1 | AS-01, AS-07 |
| | R2 | AS-03, AS-04, AS-05 |
| | R3 | AS-01, AS-02 |
| | R4 [BUG-755] | AS-06 |
| | R5 | AS-01 … AS-05 |
| `approvals_met` | R1 | AM-01, AM-02, AM-03 [BUG-755] |
| `add_approver` | R1 / Errors R1 | AA-02, AA-03 |
| | R1 [BUG-756] | AA-04 |
| | R1 [BUG-754] | AA-05 |
| | R2 / Errors R2 | AA-06 … AA-09 |
| | R3 / Errors R3 | AA-10 |
| | R4 | AA-01 |
| | R5 | AA-01 (`'User #<id>'` fallback unreachable per spec Notes) |
| | R6 | AA-01 |
| `remove_approver` | R1 / Errors | RAP-03, RAP-04, RAP-05, RAP-07, RAP-08 |
| | R1 [BUG-756] | RAP-06 |
| | R2 | RAP-01 |
| | R3 | RAP-01, RAP-02 (`'User #<id>'` fallback unreachable per spec Notes) |
| | R4 | RAP-01 |
| `set_approval` | R1 / Errors R1 | SA-03, SA-04, SA-05 |
| | R2 / Errors R2 | SA-06 |
| | R3 | SA-07, SA-16 |
| | R4 / Errors R4 | SA-09, SA-10, SA-11 |
| | R4 [BUG-754] | SA-08 |
| | R4 [BUG-758] | SA-12 |
| | R4 [BUG-744] | SA-13 |
| | R5 / Errors R5 | SA-15 |
| | R5 [BUG-744] | SA-14 |
| | R6 | SA-01, SA-20, SA-21 |
| | R6 [BUG-757] | SA-18 |
| | R7 | SA-02, SA-16, SA-17, SA-22 |
| | R7 [BUG-757] | SA-19 |
| `log_event` | R1 | LE-01, LE-02 |
| | R2 | LE-03, LE-04, LE-05, LE-06 |
| `list_events` | R1 / Errors | LV-05, LV-06 |
| | R2 | LV-01 … LV-04 |
| | R3 | LV-01, LV-07 |
| `create_expense_order_from_template` | R1 | T-02, T-03 |
| | R2 | T-04 |
| | R3 | T-01, T-05 … T-09, T-11, T-12, T-20, T-21 |
| | R3 [BUG-752] | T-10 |
| | R4 | T-01, T-19 |
| | R5 | T-13 |
| | R6 | T-14 |
| | R7 | T-15, T-16 |
| | R8 [BUG-759] | T-17, T-18 |
| | R9 | T-01, T-14, T-15 |
| | R10 | T-01, T-13, T-14 |
