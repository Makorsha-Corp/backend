# Execution notes — `app/managers/expense_order_manager.py`

> Cases: `tests/unit/managers/expense_order_manager.cases.md` (revision 6) · Tests: `tests/unit/managers/test_expense_order_manager.py` · Source commit: e48a092
> Result: 355 passed · 94 xfailed · 0 discrepancies · 0 errors — branch coverage 99% (338 stmts / 114 branches; 1 stmt + 1 partial branch missed, both explained below)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_expense_order_manager.py -q -p no:cacheprovider --cov=app.managers.expense_order_manager --cov-branch --cov-report=term-missing`

This file picks up a test file that a previous pass had already built through
`_recalc_totals` (345 of 435 cases, matching the cases file's coverage matrix
exactly up to that point). A second pass added the remaining 90 cases —
`list_approvers`, `approval_summary`, `approvals_met`, `add_approver`,
`remove_approver`, `set_approval`, `log_event`, `list_events`, and
`create_expense_order_from_template` (including EO-T-21, the only case added
in cases-file revision 3) — and re-verified the whole file end to end.

## Revision history

**2026-11-01 (cases revision 6, BUG-1193)** added EO-D-10…D-19 for `delete_expense_order` R5a, R5b, R5c: 10 strict xfails, existing tests untouched. Result 355 passed / 94 xfailed, coverage unchanged (99%, misses 294 and 653->659). **This was one agent doing the spec change, the cases and the tests, which is lighter than an independent round:** the agent had read the source before writing the cases, so the cases are not black-box, and no separate verifier has looked at them.

- **Checked:** `--runxfail` 94 failed, 355 passed. Of the new tests, D-10…D-18 fail on `TypeError` (no `user_id` parameter) and D-19 on `DID NOT RAISE TypeError`, as their rows say. 3 plain runs and 1 coverage run gave the same result. Forced plans `enable_seqscan=off`, `enable_indexscan=off` + `enable_bitmapscan=off`, and seq + bitmap off gave 355 passed / 94 xfailed each, no XPASS; `SHOW enable_seqscan` confirmed the setting arrives. Ruff: nothing in the new block; the 192 findings it reports for the file are all in older lines.
- **The assertions were run, not only the failure.** Since D-10…D-18 stop at the call today, `C:\Users\User\AppData\Local\Temp\claude\E--Projects-Makorsh-Corp-backend\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\exp1193\refimpl.py` replaces the method at run time in that one pytest process (`app/` is not edited) with a version that follows R5a, R5b, R5c plus the BUG-742 lock and invoice check. All 10 passed with `--runxfail`. Of 14 deliberately wrong versions, 13 were caught, among them a row written before each refusal, the creator as `user_id`, two rows, an extra metadata key, an optional `user_id`, a commit, and float or normalized totals. The one not caught is plain `str(total_amount)`, which is correct on a value read from the database (it has 2 decimals), so EO-D-11 does not force a formatting call. This is a scratch check, not `mutate.py`, which skips xfail tests.
- **When BUG-1193 is fixed:** EO-D-01…D-09 still call the method without `user_id`. With the scratch version, D-01…D-05 and D-09 went red (6 failed) and D-06…D-08 stayed xfailed on `TypeError`, which hides BUG-742 instead of testing it. Add `user_id` to those nine calls and to their rows in the same change. D-15…D-17 then XPASS (strict, so red): remove their markers. D-18 needs BUG-742 fixed too.

**Latest pass (cases revision 5)** fixed the open executor findings in
`expense_order_manager.verify.md` and added the four new cases. Result 355 passed /
84 xfailed, coverage unchanged (99%).

- **Finding #11** - EO-U-06, U-08, U-29 now seed a pending approver, assert
  `result.id == o.id`, and compare lines and approvers to a pre-call snapshot
  (`lines_approvers_snap`) besides the business-field snapshot and 0 events.
- **Finding #12** - EO-FN-17 now inserts V4 (paid), V5 (voided invoice), V6
  (completed order), V7 (voided order) and V8 (no invoice), so the samples are
  checked against the exclusions (same pattern as FN-13/FN-16).
- **Finding #13** - EO-C-27, C-28, C-29 use the section default payload (factory +
  `cost_center_id=F1`, description "A"); C-27 no longer sends `expense_date`; all
  three check `ws_counts` (orders, lines, approvers, events) instead of orders only.
- **Finding #14 (case designer, now in cases rev 5)** - added EO-U-48 (account_id),
  U-49 (expense_category), U-50 (cost_center_id), U-51 (due_date), each a single-field
  change on an order with U3 approved; shared helpers `_reset_case` / `_assert_reset_ok`.

**This pass** picked up cases-file revision 4 and `expense_order_manager.verify.md`'s
NEEDS WORK verdict and fixed every finding routed to the executor (#1, #4–#8;
#2/#3/#9 were the case designer's to fix and are reflected in the revision-4
cases text; #10 is the verifier's mutation re-run, not the executor's). No
test's recorded Expect (pass/xfail-BUG) changed; only setup and assertion
completeness changed. Re-ran the full file 2× after the fixes (on top of the
3× already recorded from the previous pass) — 351 passed / 84 xfailed both
times, no flakiness, and `--runxfail` still shows exactly 84 failures (none
XPASS).

- **Finding #1 (EO-C-27, dishonest xfail)** — the test sent `cost_center_id=None`
  with category `factory`, so the call failed on the factory-required check
  (400) before ever reaching the account-workspace check the case is testing.
  Fixed per the cases-file revision 4 default payload: `cost_center_id=f1.id`.
  Confirmed with `--runxfail`: now fails with `DID NOT RAISE HTTPException`
  (an order is silently created with W2's account), matching the case's
  "fails today on: order created with W2's account".
- **Findings #2/#3 (EO-U-20/U-22/U-06/U-08/U-29 case conflicts)** — the case
  designer resolved these in cases-file revision 4 (U-20's Given now uses a
  *pending* U3 instead of an approved one, with a new xfail U-22 covering the
  approved-U3 combination via U-20's same two-field payload; U-06/U-08/U-29's
  Then now says "every column except `updated_by`" explicitly). This pass
  rewrote U-20 and U-22 to match: U-20 is a plain pass test again (no
  special-cased `result is not None` weakening), asserting
  `business_fields_unchanged` + U3 still pending + 0 events; U-22 now sends
  `{"description": "Rent March", "due_date": date(2026,3,31)}` instead of only
  `description`. U-06/U-08/U-29 already used `business_fields_unchanged`
  (which excludes `updated_by` with a comment explaining why) — no code
  change needed there, since the cases text now states the same exclusion.
- **Finding #4 (EO-FN-13, wrong setup)** — the Given is "as FN-12", which
  includes Q8 (voided), Q9 (completed), Q10 (W2), all due the same day as the
  one legitimate overdue order (Q1). The test only inserted Q1–Q7, so the
  exclusion of voided/completed/foreign-workspace orders from the samples was
  never exercised. Added Q8/Q9/Q10 (same values as FN-12) and an explicit
  `overdue["count"] == 1` assertion (would be 4 if the exclusion were broken).
- **Finding #5 (EO-U-21, missing assertion)** — added
  `assert events[0].performed_by == u2.id` for the `approvals_reset` event.
- **Finding #6 (weakened "nothing written")** — brought each listed test up to
  the Conventions' full definition (order + lines + approvers + events):
  - `create_expense_order` C-10, C-11, C-12, C-13, C-14, C-15, C-16, C-17,
    C-31: switched from `ws_order_count()` (orders only) to the pre-existing
    `ws_counts()` 4-tuple (orders, lines, approvers, events).
  - `update_expense_order` U-05, U-10, U-11, U-13: added
    `lines_of/approvers_of/events_of(db, o.id) == []` alongside the existing
    `order_snap` comparison.
  - U-44: was comparing only `description`; now takes a full `order_snap`
    before/after plus the lines/approvers/events-empty checks.
  - `update_item` UI-05, UI-08: both now re-read **both** lines (L1 and L2),
    not just the one named in the case's When, plus 0 events.
  - `set_approval` SA-09, SA-10, SA-11: added `events_of(...) == []`; SA-10
    additionally gained the missing `exc.value.detail` and `approver_row`
    assertions (previously only `status_code` was checked).
  - `add_approver` AA-06…AA-09: added `events_of(O_aa.id) == []`.
- **Finding #7 (missing detail assertion)** — AI-06, RI-04, D-03 now assert
  `exc.value.detail` (the exact "not found" message), not just `status_code`.
- **Finding #8 (in-memory only)** — AI-03, SA-07, SA-16, SA-17 now re-read via
  `reread_item` / `reread_approver` after the call instead of asserting on the
  object `set_approval`/`add_item` happened to return.
- **Finding #9 (EO-FN-16/17 unrealizable Given)** — already resolved in the
  test code carried over from the previous pass (V3 amount 600/paid 0, not
  "paid null"; V5 `invoice_status="voided"`, not a `voided` column; V9 amount
  0/paid 0, not null); the cases-file revision 4 text now states the same
  substitutions explicitly (gap G11). No test change was needed.
- **Finding #10 (incomplete mutation run)** — routed to the verifier (re-run
  `mutate.py` over lines 343–664), not applicable to this stage.

## How the tests are built

Conventions → fixtures (all pre-existing except where noted as added this pass):

- **W1/W2, U1..U5, M** — `w1`/`w2` (`make_workspace`), `u1`..`u4` (`make_profile` +
  a local `_member` helper that inserts a `WorkspaceMember` row; U1/U2/U3 active
  in W1, U2 with position "Accountant"; U4 active in W2 only), `u5` (profile with
  no membership anywhere), `M` (`ExpenseOrderManager()`).
- **F1/FI/FD/F2, D1/DI/DD/D2, A1/A2/AX/AW2** — one fixture per reference row,
  inserted directly against the model with the exact `is_active`/`is_deleted`
  flags the cases file names.
- **Order/line/approver/event/invoice/template rows** — `order_factory`,
  `line_factory`, `approver_factory`, `event_factory`, `invoice_factory`,
  `template_factory`, `template_item_factory`: one `_mk(...)` closure per model,
  defaults matching the cases file's "Order rows inserted directly" /
  "Line defaults" / "Approver rows" / "Invoices" conventions, flushed so ids
  increase in insertion order. `R` builds the "ready order" (one line, category
  factory/cost-center F1 by default); `O` / `O5` are the plain-order shorthands.
  This pass added **no new model-row fixtures** — `approver_factory`,
  `event_factory`, `template_factory`, `template_item_factory` already existed
  (built by the previous pass, apparently in anticipation of these sections)
  and were reused as-is.
- **New local fixtures this pass**: `O_aa` (order + U1 approved, for
  `add_approver`), `O_rap` (order + U1 approved / U3 pending, for
  `remove_approver`), `O_sa` / `O_sa_approved` (ready order + U2
  pending/approved, for `set_approval`), `TPL` / `tpl_lines` (the template
  fixture + its two template lines, for `create_expense_order_from_template`).
  None of these are reused by another module, so none were promoted to
  `tests/unit/factories.py` (batch mode also forbids editing that file).
- **Helpers added this pass**: `aa(db, M, o, w1, user, assigned_by)` and
  `sa(db, M, o, w1, user, approved)` — one-line wrappers mirroring the cases
  file's `aa(u)` / `sa(u, v)` call-shorthand so each test reads like the cases
  table. `ft(db, M, tpl, w1, u1, **over)` does the same for
  `create_expense_order_from_template`'s `ft(o)`.
- **Time** — the existing autouse `_utcnow` fixture patches both
  `app.managers.expense_order_manager.utcnow` and `app.dao.expense_order.utcnow`
  to `NOW` for every test. Column-default timestamps that can't be frozen
  (`assigned_at` on a fresh `add_approver` row, `created_at` on a fresh
  `log_event` row) are checked against a real-clock window using the
  pre-existing `real_window()` helper (`before = real_window()(); ...; after =
  real_window()()`, then `before <= value <= after`).
- **SQL capture** — the pre-existing `SQLCapture` context manager (a
  `before_cursor_execute` listener on the session-scoped `engine` fixture) is
  reused for the two new HR-10 lock xfails in this pass (SA-13, SA-14); `cap.
  locked` checks for a captured statement selecting from `expense_orders` with
  `FOR UPDATE`.
- **DB-error cases** — LE-04 (FK violation on a missing order id) and LE-06
  (51-char `event_type` over the `VARCHAR(50)` column limit) both run the call
  inside `db.begin_nested()` and assert `IntegrityError` / `DBAPIError`
  respectively, then re-read to confirm no event was left behind after the
  savepoint rolled back.
- **Profile deletion (LV-07)** — a throwaway profile (not one of U1..U5, to
  avoid disturbing their workspace memberships) is given one event as
  performer, then the profile row itself is deleted and flushed; the event's
  `performed_by` FK is `ON DELETE SET NULL`, so `list_events` must show that
  event paired with `None`.
- **No new mocks beyond what the file already declared**: the two `utcnow`
  patches (autouse) and the `SQLCapture` listener. Nothing else is mocked —
  not the session, not any DAO — per the cases file's "No race simulations"
  note.

## Discrepancies

None. Every case ended as designed: 355 cases designed `pass` passed; 84 cases
designed `xfail BUG-NNN` ended `xfailed` (confirming the named bug is still
present); 0 cases needed a `DISCREPANCY-n` marker. Re-ran the full file three
times back to back in the previous pass, plus twice more in this pass after
the verifier-routed fixes (see Notes for maintainers), with identical results
each time, including the tie-order bug cases (BUG-746/747/748) and the two
SQL-capture lock xfails (SA-13/SA-14) — no flakiness observed. `--runxfail`
confirms all 84 xfails genuinely fail (none XPASS).

## Coverage gaps

| Lines | Kind | What the code does there |
|---|---|---|
| 294 (`list_expense_orders`, whole method body) | dead | The hub endpoint and `ExpenseOrderService` both call `list_expense_orders_for_hub` instead; `docs/testing/dead-code-removal-checklist.md`-staged entry already flags this method as unreachable (spec review Q24). No case exercises it, matching the cases file's Coverage matrix (it has no row for `list_expense_orders`). |
| 653→659 (`create_expense_order_from_template`, the `if not existing:` branch inside the `elif template.default_approver_id and ... != user_id` arm never takes its *false* path) | unreachable | This is a defensive re-check of whether `template.default_approver_id` is already an approver on the just-created order. Within one call of `create_expense_order_from_template`, the only approver that can exist at this point is `user_id` (added a few lines above, inside `create_expense_order`) — and the `elif` guard one line above already requires `default_approver_id != user_id`. So `existing` can never be truthy here; the `not existing` branch is always taken. Not listed as a case in the cases file's Coverage matrix or Spec gaps, and not worth a test that would have to fabricate an impossible prior state (e.g. inserting an approver row by hand before calling the method, which is not what any case's Given describes). |

No `spec-gap` or `deferred` misses: every reachable branch not covered by a
listed case above is otherwise exercised by at least one of the 439 cases.

## Factories added

None. All row builders needed by this module's own models (`ExpenseOrder`,
`ExpenseOrderItem`, `ExpenseOrderApprover`, `ExpenseOrderEvent`,
`WorkspaceMember`, `OrderTemplate`, `OrderTemplateItem`, `AccountInvoice`) are
local fixtures in the test file, per the batch-mode instruction not to touch
`tests/unit/factories.py`. If a second module later needs the same shape of
row, these are worth promoting:

- `_member(db, ws, profile, *, position=None, status="active")` →
  `make_workspace_member` (any manager test touching workspace membership
  status/position will want this).
- `approver_factory` / `event_factory` → `make_expense_order_approver` /
  `make_expense_order_event`, if another module ever needs an
  `ExpenseOrderApprover` or `ExpenseOrderEvent` row directly (unlikely outside
  this manager and its service layer).
- `template_factory` / `template_item_factory` → `make_order_template` /
  `make_order_template_item`, which `tests/unit/managers/order_template_manager`
  tests (not yet written) will need verbatim.

## Notes for maintainers

- **Fragile spots**: none beyond what the cases file already calls out. The
  tie-order xfails (HL-38/39/45/46, HC-07, HR-06/07, FN-11/19) depend on
  Postgres returning unordered ties in a stable-but-unspecified order; this
  pass re-ran the suite 3× with no flips (see Discrepancies). The two new lock
  xfails (SA-13/14) use the same `SQLCapture` pattern as the pre-existing ones
  (U-09, D-06, AI-09, UI-10, RI-08) and are equally deterministic since the
  capture only inspects statement text, not timing.
- **When a BUG-NNN is fixed**, the xfail tests naming it will XPASS (strict) and
  fail the run — remove the `xfail` marker (and, for BUG-757/SA-18/SA-19 and
  BUG-752/T-10, double check the paired "pass partner" tests SA-20/SA-22/T-21
  still hold, since they assert the pre-fix behavior is *also* correct
  post-fix; they should keep passing unchanged).
- **BUG-759** (T-17/T-18) is the one case in this pass where the test body
  calls the method expecting it to *succeed* with a specific event trail; today
  it instead raises `HTTPException(400, 'User is not an active member of this
  workspace')` from inside `add_approver`, so the test fails on that
  unhandled exception rather than on a specific assertion — this is expected
  and is what "fails today on: 400 ... raised" in the cases file describes.
- **`O_sa` / `O_sa_approved`** both build a fresh `R()` (ready order) rather
  than sharing one, so mutating one in a test (e.g. SA-07's `completed_at =
  T0`) never leaks into another test — each fixture call makes its own row.
- **EO-U-22's assertion order**: `result._approvals_reset is False` is checked
  before the `u3_row.approved`/`approved_at` re-read, so today's `--runxfail`
  failure is `assert True is False` on that first line, not on the u3_row
  line the xfail reason's "U3 approval cleared" names directly. Both
  assertions fail for the same reason (BUG-740 resets the approval and flips
  `_approvals_reset`), so this is still an honest xfail — if BUG-740 is fixed,
  both lines pass. Don't reorder the assertions to "fix" which one fails
  first; it doesn't change what the test proves.
