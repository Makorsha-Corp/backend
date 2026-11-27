# Execution notes — `app/managers/po_receive_inventory.py`

> Cases: `tests/unit/managers/po_receive_inventory.cases.md` (revision 5) · Tests: `tests/unit/managers/test_po_receive_inventory.py` · Source commit: e48a092
> Result: 119 passed · 23 xfailed · 0 discrepancies · 0 errors — branch coverage 98% (52 branches, 2 unreachable per spec)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_receive_inventory.py -q -p no:cacheprovider --cov=app.managers.po_receive_inventory --cov-branch --cov-report=term-missing`

## How the tests are built

- **World fixture `w`:** one `SimpleNamespace` fixture builds every actor named in
  the cases file's Conventions once per test (W1, W2, U1, U2, items X/Y/Xd/Z2,
  factories A/B/Ad/F2, machines M1/M2/Md/M9, PO P with lines L1/L2, PO P2). Local
  row builders (`make_item`, `make_factory`, `make_machine`, `make_status`,
  `make_po`, `make_line`, `make_event`, `make_event_item`) are module-local per
  the batch-mode rule — `tests/unit/factories.py` was not touched. `make_status`
  exists only because `PurchaseOrder.current_status_id` is a required FK; it is
  not part of the Conventions and carries no assertions.
- **Shorthand builders → Conventions:** `posted`, `legacy`, `reversed_`,
  `legacy_reversed` wrap a shared `_seed_ledger` helper that inserts one bare
  `InventoryLedger` or `MachineItemLedger` row depending on whether `loc` is a
  `Factory` or `Machine`. `stock(...)` / `mstock(...)` insert the `Inventory` /
  `MachineItem` row plus a trailing `source_type='test_seed'` ledger row at T1
  (inserted last, per Conventions "ledger wins"). `return_` / `pending_return`
  build a `PurchaseOrderReturn` + `PurchaseOrderReturnItem` via `mk_return_item`,
  with `return_` additionally writing the matching `purchase_return_item` ledger
  row in the same ledger/location as the original posting (spec R6a / G3).
- **Call wrappers:** `call_post`, `call_reverse_item`, `call_reverse_legacy`,
  `call_reverse_po` thread `w.db`, `w.w1.id`, `w.u1.id` and the default `po=w.p`
  per the Conventions ("every call uses workspace_id=W1, user_id=U1 unless
  stated").
- **Read-back helpers:** `rows_for_source` (fresh query filtered by workspace/
  type/id, after `db.expire_all()`), `reread_stock` / `reread_mstock` (assert
  exactly one row and return it), `new_rows` / `assert_nothing_written`
  (snapshot max id before, assert no row with a higher id after, for both
  ledgers and `MachineActivityEvent`), `new_activity` (new activity rows for one
  machine). `assert_cols(row, **expected)` asserts a named subset of columns
  with a readable failure message, used for the "Ledger row = {…}" case tables.
- **Mocks:** no external dependency is mocked (spec: "Externals to mock:
  none"). The only patches are the three listed race simulations (BUG-680 R1a):
  `race_simulation(target_type)` returns two `patch(...)` context managers for
  `app.managers.po_receive_inventory._storage_ledger_exists` /
  `_machine_ledger_exists`, each a selective side effect that answers `False`
  only for the named `source_type` and otherwise delegates to the real function
  (imported under `_real_storage_ledger_exists` / `_real_machine_ledger_exists`
  before patching, so the real check is still available during the patch).
  PRI-P-30/31, PRI-RE-17, PRI-RL-14 use this, each inside
  `with p1, p2: with pytest.raises(IntegrityError): with db.begin_nested(): <call>`.
  Since today's code has no unique index, the simulated "no existing row" branch
  is taken and the call succeeds without raising — the `pytest.raises` block
  itself never completes, so these are `xfail(strict=True)` on BUG-680, exactly
  as designed ("fails today on: no exception raised").
- **Database-error cases (PRI-IDX-01/02):** no manager call — two raw ledger
  inserts in the same `(workspace_id, source_type, source_id)` at different
  locations, the second inside `db.begin_nested()`. Since no partial unique
  index exists today, the insert succeeds and `pytest.raises(IntegrityError)`
  is never satisfied, so these are `xfail(strict=True)` on BUG-680 too.
  PRI-IDX-03/04 (pass) confirm today's actual behavior: legacy `purchase_order`
  rows (not in R1a's source-type list) and cross-workspace rows are never
  expected to conflict, index or no index.
- **BUG-682 netting (PRI-V-10..18):** `reverse_po_receive_inventory` today has
  no netting parameter, so every xfail case there asserts the *post-fix*
  expectation (e.g. "reversal quantity 7", "stock ends at 0/20") while today's
  code reverses the full receive-line quantity — the assertions fail on the
  literal numbers named in the cases file's "fails today on" column, which is
  what makes them a faithful record of BUG-682's effect rather than a weakened
  substitute.

## Fixes made to the test file (none changed the designed expectations)

The test file already existed (apparently from earlier work on this module) and
covered all 115 case IDs with the expected pass/xfail split; the pipeline-standard
check-run on it here found one test-construction bug, not a product bug:

- `_seed_ledger`'s `InventoryLedger` branch left `unit_cost` as `None` by
  default (the `MachineItemLedger` branch already defaulted it to `Decimal("0")`).
  `_reverse_legacy_line_posting` unconditionally does
  `Decimal(str(storage_entry.unit_cost))` on the found legacy row (the result is
  computed but never actually passed into `post_stock_out`, which derives its
  own unit cost from the destination's current average — so this local variable
  is effectively dead output, not a reachable product bug), and `Decimal(str(None))`
  raises `decimal.InvalidOperation`. Every `legacy(...)` helper call that landed
  in `inventory_ledger` therefore crashed outside any case's control flow. Fixed
  by defaulting `unit_cost` to `Decimal("0")` in the `InventoryLedger` branch too
  (matching the machine branch), and setting it explicitly on the one place a
  test built an `InventoryLedger` row by hand (PRI-RL-12a). No case's Given/
  When/Then changed; this only supplies a NOT-reachable-in-production value the
  helper had omitted. 10 tests were affected (PRI-RL-01, RL-03, RL-04, RL-06b,
  RL-09, RL-10, RL-11, RL-12a, RL-12b, PRI-V-06); all pass as designed after the
  fix.

## Revision history
- **Revision 5 (this pass).** The cases file added 6 new ±1-boundary cases
  (PRI-D-05 parametrized ×2, PRI-P-34, PRI-P-35, PRI-RE-21, PRI-RE-22) per
  verify.md finding 1 (surviving mutants #77, #83, #85, #91, #96, #98, #103:
  no prior case used a delta of exactly ±1, so the `qty <= 0`, `delta == 0`
  and `delta > 0` boundaries were only checked on one side). All 6 implemented
  as designed, all `pass`, each asserting direction (`transaction_type`,
  `qty_before`/`qty_after`) so a dropped or misdirected 1-unit delta fails.
  Also fixed the 9 executor-side test-weakness findings verify.md routed here
  (findings 2–10), none of which changed any case's designed expectation:
  - **Finding 2 (PRI-V-10).** `pending_return()` no longer passes
    `status="pending"` to `mk_return_item` — the parent return keeps the
    default `"completed"` status (spec R6a: status is not consulted), so the
    missing ledger row is now the *only* reason PRI-V-10 is not netted. A
    BUG-682 fix that wrongly keyed off `status` instead of the ledger row
    would now fail this test, as it should.
  - **Findings 3–6, 9, 10 (PRI-P-01, P-16, P-22, P-27, P-28, PR-02, RE-19).**
    Each now asserts the full "nothing written" convention (both ledgers +
    `MachineActivityEvent`, via `snapshot_ids`/`assert_nothing_written`) or
    the full re-read stock row, instead of a partial check. PRI-PR-02
    additionally asserts there is no row for the zero-delta pair's source id
    and that exactly the one expected new row exists.
  - **Finding 7 (PRI-P-24).** `pytest.raises(Exception)` + a manual
    `isinstance` check replaced with `pytest.raises(InvalidOperation)`
    directly (`InvalidOperation` now imported at module level), matching the
    house rule of naming a specific exception type, as PRI-RE-14 already did.
    Also added the missing ledger snapshot.
  - **Finding 8 (PRI-P-18).** The other-workspace row's columns are now
    snapshotted before the call and compared column-for-column after
    (`assert_cols`), not just checked for existence.
  No test's designed `pass`/`xfail` outcome changed; every fix only completes
  an under-asserted Then clause or removes a setup detail the case didn't ask
  for. Full suite re-run 2× after the changes: `119 passed, 23 xfailed` both
  times; `--runxfail` reproduces the same 23 failures on their named
  assertions as before. Coverage unchanged at 98% branch (same 2 unreachable
  lines, 117 and 239).

## Discrepancies
None. Every case's designed outcome (`pass` or `xfail BUG-NNN`) matches the
actual run.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 117 (`_post_event_item_delta`, body of `if qty <= 0: return False`) | unreachable | Per the spec's branch map: unreachable because a non-zero whole delta (the only way to reach this line past the R3 zero-delta check) always has `abs(delta) >= 1`, so `qty` is never ≤ 0 here. |
| 239 (`_reverse_event_item_posting`, body of `if qty <= 0: return False`) | unreachable | Same reasoning, per the spec's branch map (`_reverse_event_item_posting` R4 note: "not reachable in practice: zero deltas are never posted, so R2 returns first"). |

Branch coverage is 98% (52 branches, 2 unreachable) — no line or branch is
missing from a *reachable* path through the module; the two gaps are exactly
the two defensive branches the spec's Branch map calls out as unreachable. No
test was added beyond the cases file to chase the remaining 2%.

## Factories added
None. All row builders needed (`make_item`, `make_factory`, `make_machine`,
`make_status`, `make_po`, `make_line`, `make_event`, `make_event_item`,
`_seed_ledger` and its `posted`/`legacy`/`reversed_`/`legacy_reversed`/`stock`/
`mstock`/`return_`/`pending_return` wrappers, `mk_return_item`) are local to
this test file per the batch-mode instruction (`tests/unit/factories.py` is a
shared file merged later by one agent and was not edited).

**Worth promoting to `tests/unit/factories.py` later** (used only by this
module today, but general enough for other inventory/PO modules):
- `make_item(db, workspace_id, name, *, active=True)` — minimal `Item` row.
- `make_factory(db, workspace_id, name, *, deleted=False)` / `make_machine(db,
  workspace_id, factory_id, name, *, deleted=False)` — minimal `Factory` /
  `Machine` rows with soft-delete support; several other PO/inventory modules
  will need these.
- `make_po(db, workspace_id, user_id, *, destination_type, destination_id,
  po_number)` / `make_line(db, po, item_id, *, line_number, unit_price)` —
  minimal `PurchaseOrder` / `PurchaseOrderItem` rows (the former also needs
  `make_status`, since `current_status_id` is a required FK with no sensible
  module-specific default).

## Notes for maintainers
- **BUG-680 fix lands:** once the partial unique index exists, PRI-P-30/31,
  PRI-RE-17, PRI-RL-14, PRI-IDX-01, PRI-IDX-02 will XPASS (their
  `pytest.raises(IntegrityError)` will start succeeding) — remove the
  `xfail(strict=True, reason=BUG_680)` markers on those 6 test functions (23
  parametrized items across them, once IDX-01/02's 3 source-type params each
  are counted).
- **BUG-681 fix lands (in `app/schemas/purchase_order.py`, not here):** no test
  in this file changes — `_location_for_po` R3 / `_post_event_item_delta` R2
  are specified as staying exact string comparisons; PRI-LOC-04 and PRI-P-21
  are `pass`-designed and assert today's (and tomorrow's) exact-comparison
  behavior, not a bug.
- **BUG-682 fix lands:** `reverse_po_receive_inventory` gains a netting
  parameter per the spec's G2/G3 resolution. PRI-V-11 through PRI-V-15 and
  PRI-V-18 (6 tests) will XPASS — remove their `xfail(strict=True,
  reason=BUG_682)` markers. PRI-V-10, PRI-V-16, PRI-V-17 are already
  `pass`-designed (they test that netting correctly does *not* apply) and
  should keep passing unchanged.
- **BUG-683 fix lands:** PRI-RE-18/19/20 and PRI-RL-13/15 (5 tests) will XPASS
  — remove their `xfail(strict=True, reason=BUG_683)` markers. PRI-RE-01
  (`same location, pass`) is unaffected.
- **BUG-684 fix lands:** PRI-P-29/32 (2 tests) will XPASS — remove their
  `xfail(strict=True, reason=BUG_684)` markers.
- **Fragile spots:** none identified — all monetary/quantity assertions use
  `Decimal` literals matching the spec's stated weighted-average formula
  exactly (no floating-point comparisons), and the two ordering-sensitive cases
  (PRI-V-03, PRI-V-04) assert on `source_id` sequences read fresh after
  `db.expire_all()`, not on cached ORM state.

## Deferred to other specs (not implemented here, per the cases file)
| Rule | Owner | What must be tested there |
|---|---|---|
| P R1a / RE R1a / RL R1a: "surfaced as HTTPException 409" | `app/core/exceptions.py` (global integrity-error handler, BUG-462) | A unique violation (pgcode 23505) becomes 409, never 500. |
| P R1a etc.: true two-session concurrency | integration test (two connections) | Two concurrent voids/receives for the same source: exactly one ledger row, the loser gets 409. |
| `_location_for_po` R3 / P R2 [BUG-681] | `app/schemas/purchase_order.py` | `destination_type` trimmed/lower-cased; only `storage`/`machine`/`project` accepted (422 otherwise). |
| Overview: lines belong to the PO; the PO is not already voided | `PurchaseOrderService.create_receive_event` / `void_purchase_order` | Callers enforce these; this module does not check them. |
| Q2: a void that fails on insufficient stock leaves the PO un-voided | `PurchaseOrderService.void_purchase_order` | A 400 from `reverse_po_receive_inventory` rolls back and the PO status is unchanged. |

## Decisions made
None in this execution pass — the cases file's own "best-practice default,
delegated by reviewer" decisions (BUG-682 netting mechanism, BUG-684 error
wording, "completed return" ledger definition) were already resolved by the
case designer and implemented faithfully as designed; no new judgment calls
were needed to turn the cases into tests.
