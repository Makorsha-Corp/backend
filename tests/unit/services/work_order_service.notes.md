# Execution notes — `app/services/work_order_service.py`

> Cases: `tests/unit/services/work_order_service.cases.md` (revision 4, 2026-11-22) · Tests: `tests/unit/services/test_work_order_service.py` · Source commit: e48a092
> Result: 228 passed · 39 xfailed (all strict, bugs) · 0 open discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_work_order_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **Layout.** One test per card, in card order. The file covers 267 case IDs, each exactly once.
  - Three groups are parametrized: C-18…C-21 (machine status), V-07/V-08 (W2 / W0 invoice) and I-21/I-22 (zero / negative cost).
  - A `# Then N` comment marks the checks of each Then line.
- **Standing rows.** The namespace fixture `s` (`s.W1`, `s.U2`, `s.M1`, `s.A1`, …) builds them in the Conventions order.
- **Given rows.**
  - Orders: `mk_order(db, s, n, ws=, outside=, started=, completed=, voided=, gone=, **cols)`.
  - Invoices: `inv(…, ws=, confirmed=, voided_inv=, linked=)`, plus `invl` and `pay` (a voided payment).
  - People: `approver(…, approved=)` and `assignee` / `completer(…, ws=)`.
  - Other rows: `line(…, gone=)`, `stock` (= S(I, q, p)), `status_row`, `wo_event`, `ran`, `template` with `WEEKLY`, `tapprover`.
  - Requests: `CR`, `SHEET`, `ITEM`.
- **BUG-664 rule.** Stock is seeded only through `stock()`: one `Inventory` row plus one opening `InventoryLedger` row at T0, so it is past-dated. Nothing is posted in setup.
- **Commit point and checks.**
  - `commit_point(db)` commits (a savepoint release). It returns the "nothing written" counts of the 13 tables, which include `inventory` (rev 3), and the event marks `mark_wo` and `mark_mae`.
  - `committed:` lines run after one `db.rollback()`.
  - Re-reads go through `db.expire_all()`. `snap()` / `snap_id()` read every column of the row from its table.
  - X is `make_workspace(db)`, flushed and not committed. Read cards check `X in db`; R-14 checks `X in db` and `not db.new`.
  - Write error cards (rev 4, TC3) check `X not in db` right after the raise, before any re-read or test rollback. One error card per write method runs the call inside **spies**, placed inside the `pytest.raises`, and checks `rb.call_count >= 1`.
- **Patched.** Nothing else is mocked.
  - `app.managers.work_order_manager.utcnow`, through the autouse `clock` fixture, NOW naive.
  - The commit / rollback / refresh spies and their failing variants, through `patch.object(db, …)`.
  - `app.services.work_order_service.<notify fn>` for the "failing notify" cards.
  - `…work_order_service.utcnow` with `create=True` (I-30).
  - The manager-return patches of the `Author: claude` cards (U-06, B-04, SB-02) and the `create_invoice` spy (I-31).
- **Statement recorder.** A `before_cursor_execute` listener runs around the When only.
  - `lock()` holds when the first `SELECT` whose `FROM` names `work_orders` matches `FOR UPDATE( OF work_orders)?\s*$`.
  - `lock_first()` holds when that statement comes before the first statement naming `account_invoices` and before any `INSERT` / `UPDATE` / `DELETE`.
  - Recorder cards with `db.expunge_all()` read `W1.id` / `U2.id` before expunging, because detached standing rows cannot be read afterwards.

## Checks run (revision 4)
- **Collection and IDs.** 267 collected. Every case ID appears exactly once (267 / 267). The 39 xfail cards map one-to-one to the 39 strict `xfail` markers.
- **3 plain runs.** Each gave `228 passed, 39 xfailed`.
- **`--runxfail`** (scratch `tools/thenline_plugin.py` + `tools/check_thenline.py`): 39 failures, 0 mismatches.
- **Reference plugin** (scratch `tools/ref_plugin.py`, unchanged since rev 3): `-p ref_plugin --runxfail` gave **267 passed**.
  - It fixes BUG-627, 628, 639, 1272, 1279, 2916, 2917, 2923, 2931, 3222, 3223, 3224, 3225, 3226, 3227, 3228 and 3229.
- **Coverage.** 318 statements, 66 branches, **100%**.
- **Lint.** `ruff check` is clean; LF line endings.
- **Rollback strip (TC3).** The plugin is my own: scratch `tools/strip_rollback_plugin.py`. It follows the method of the coordinator's `tc3method.py`, which I read but did not run.
  - It loads `app/services/work_order_service.py` in-process, with `self._rollback_transaction(db)` inside ONE method replaced by `None`. The repo file is read, never written.
  - Command: `STRIP_METHOD=<m> PYTHONPATH=<scratch>/tools … -p strip_rollback_plugin`.
  - Every write method fails at least one test (plain run):

  | Method stripped | Failing tests |
  |---|---|
  | `create_work_order` | E-02 |
  | `create_work_order_from_template` | T-03 |
  | `update_work_order` | U-08, U-09 |
  | `bulk_delete_future_recurrence_drafts` | B-04 |
  | `sheet_entry` | SE-03, SE-04 |
  | `delete_work_order` | X-02 |
  | `start_work_order` | S-02 |
  | `complete_work_order` | C-06, C-08, C-16, C-22, C-24 |
  | `complete_work_order_as_planned` | P-07, P-08, P-14, P-16, P-17, P-19 |
  | `void_work_order` | V-05, V-11, V-13, V-15 |
  | `create_invoice_for_work_order` | I-09, I-18, I-32, I-36 |
  | `add_approver` | AA-04, AA-09 |
  | `remove_approver` | RA-02 |
  | `approve_as_me` | AP-02 |
  | `unapprove_as_me` | UA-02 |
  | `add_item` | AI-03, AI-04 |
  | `update_item` | UI-03 |
  | `remove_item` | RI-02 |

## Discrepancies
| ID | Case | Status (revision 4) |
|---|---|---|
| DISCREPANCY-1 | read cards with X | **Resolved**: the cards now check `X in db` (and R-14 also `not db.new`). The unflushed `mk_x_pending` helper was removed. |
| DISCREPANCY-2 | R-03 | **Resolved** (G9): the card was rebuilt on a soft-deleted type (`Retired service`), and the type keeps its name. Passes. |
| DISCREPANCY-3 | U-07 | **Resolved** (G8, U4a): the card expects the title unchanged. Passes. |
| DISCREPANCY-4 | SB-01…03 | **Resolved** (G10): the cards read `b.approvers.approvers[0]` / `b.approvers.summary`, and SB-01 also checks the `WorkOrderApproversList` type. |
| DISCREPANCY-5 | SB-01, SB-04, GI-01 | **Resolved**: lines are compared as sets (BUG-1272), and the non-strict markers were removed. |
| DISCREPANCY-6 | AA-03 | **Resolved** (G9): the order is not ready because of `title "   "`, and the gap text is `Work order setup is incomplete`. Passes. |
| DISCREPANCY-7 | V-03 | **Resolved** (G7): V-03 is a strict xfail BUG-3229 on Then 3. The pass companion V-19 was added, and X-06 / X-08 / X-09 / X-11 now check the invoice id. |
| DISCREPANCY-8 | S-02 Then 9 | **Resolved in revision 4**: the card now names the `qty` column. |

## Coverage gaps
None — 100% branch coverage.

## Factories added
None.

## Notes for maintainers
- **When a bug is fixed**, its strict xfails will XPASS; remove those markers then.

  | Bug | Cards |
  |---|---|
  | 1279 | G-07, I-34 |
  | 2931 | AA-07, RA-03, AP-03 |
  | 2917 | AP-04 |
  | 628 | C-12 |
  | 639 | V-04 |
  | 627 | I-31 |
  | 2916 | C-27 |
  | 3222 | P-21, V-18, I-37 |
  | 3223 | P-04…P-06 |
  | 3224 | V-09, V-12, V-14 |
  | 3225 | I-12, I-13, I-15, I-16 |
  | 3226 | I-30 |
  | 3227 | B-05, B-07, B-09, B-10, B-12, SE-06, SE-08 |
  | 3228 | I-20…I-22 |
  | 2923 | X-06, X-08, X-09, X-11 |
  | 3229 | V-03 |
- **I-30** depends on the machine's real date not being 2026-03-10.
- **Lock check.** The check accepts `FOR UPDATE OF work_orders` as a lock. A fix that combines joined eager loading with `.first()` wraps the query in a subquery, so the clause is no longer at the end of the statement and the check fails. The reference plugin uses `.one_or_none()`.
- **Shared test DB.** Other agents use the same test DB. Every test rolls back; IDs and `TAG` keep rows apart, and "nothing written" counts are taken in the test's own transaction.
- **BUG-3229 register row.** If it is not merged yet, this is the row: `| BUG-3229 | audit-value-read-after-mutation | app/services/work_order_service.py (void_work_order) | Voiding a work order with a draft invoice logs the unlink event without the invoice id | delete_invoice runs before old_invoice_id = wo.invoice_id is read; the FK SET NULL clears the link, so the invoice_voided event stores {"invoice_id": null} (verified, WOS-V-03) | Read the invoice id before deleting the invoice (spec V4a; as BUG-3070) | spec V4a | open |`

## Revision history
- **Revision 2 run (2026-11-22).** First implementation: 263 tests. Result: 218 passed, 38 bug xfails, and 7 discrepancies — 4 strict, plus 3 flaky tests marked non-strict.
- **Revision 3 (2026-11-22).** Cases moved to revision 3 (264 cases: 225 pass, 39 strict xfail).
  - **Markers.** All DISCREPANCY markers were removed, both strict and non-strict, along with the `DISC_*` / `FLAKY_ORDER` constants and `mk_x_pending`.
  - **Rewritten:** R-03 (soft-deleted type), U-07 (title dropped, description and end date saved), AA-03 (blank title, new gap text), SB-01 (nested accessor plus type check, set compare), SB-04 and GI-01 (set compare).
  - **Then lines added:** X-08 (Then 8–9), X-09 (Then 9–10), X-11 (Then 6–7) and S-02 (Then 7, `inventory` rows).
  - **V-03** is now `xfail(3229)`, and BUG-3229 is in `BUGS`.
  - **New test:** V-19.
  - **"Nothing written"** now also counts `inventory`.
  - **Read cards** check `X in db`.
  - **Reference plugin:** only its docstring changed.
  - **Re-checked:** `--runxfail` 39 failures, 0 mismatches; reference plugin 264 passed; 3 plain runs `225 passed, 39 xfailed`; branch coverage 100%; ruff clean; LF.
- **Revision 4 (2026-11-22).** Cases moved to revision 4 after the verifier's findings (267 cases: 228 pass, 39 strict xfail).
  - **TC3 `X not in db`.** 43 error cards now check `X not in db` right after the raise, before any re-read or test rollback. Their later `# Then N` comments were renumbered. The tests take `X, x_id = mk_x(db)`.
  - **Spied error cards.** 18 cards, one per write method, run the call in `spies` inside the `pytest.raises` and check `rb.call_count >= 1`: E-02, T-03, U-09, B-04, SE-03, X-02, S-02, C-16, P-14, V-11, I-18, AA-04, RA-02, AP-02, UA-02, AI-03, UI-03, RI-02.
  - **New tests:** LE-14 (frozen dataclass, field order; `import dataclasses`), SB-13 (completed order listed by default) and SB-14 (`exclude_completed=True`).
  - **S-02** Then 9 is now the `qty` check, which resolves DISCREPANCY-8.
  - **Reference plugin** unchanged. The new rollback-strip plugin was added.
  - **Re-checked:** `--runxfail` 39 failures, 0 mismatches; reference plugin 267 passed; 3 plain runs `228 passed, 39 xfailed`; branch coverage 100%; ruff clean; LF; rollback strip catches all 18 write methods.
