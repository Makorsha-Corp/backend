# Execution notes — `app/managers/po_return_inventory.py`

> Cases: `tests/unit/managers/po_return_inventory.cases.md` (revision 3) · Tests: `tests/unit/managers/test_po_return_inventory.py` · Source commit: e48a092
> Result: 65 passed · 3 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_po_return_inventory.py -q -p no:cacheprovider --cov=app.managers.po_return_inventory --cov-branch --cov-report=term-missing`

## Revision history
- **Fix round 2 (this pass):** applied the one finding from `po_return_inventory.verify.md`
  verify round 2 (verdict NEEDS WORK, 65 passed/3 xfailed, coverage 100% branch, mutation
  48/48 killed — this finding was a fidelity gap, not a surviving mutant).
  1. *Missing assertion* — PRI-P-10 (test lines 825–827) read
     `row = inv_rows_for(db, ri1)[0]` and asserted only `factory_id` and `quantity`, never
     the case's required "**one** ledger row for RI1 on F1d". Fixed by capturing
     `rows = inv_rows_for(db, ri1)` and asserting `len(rows) == 1` before indexing into
     `rows[0]`, matching the sibling machine case PRI-P-20's existing pattern. No case
     text, expected value, or marker was changed. Re-ran the full file 3 times after the
     fix: 65 passed, 3 xfailed each time, coverage unchanged at 100% branch (this is a
     mutation/fidelity fix, not a coverage fix).
- **Fix round 1:** applied both findings `po_return_inventory.verify.md` routed to
  the executor (verdict NEEDS WORK, mutation 98%, 1 survived mutant).
  1. *Weakened assertion (self-referential constant)* — PRI-P-01 and PRI-P-25 queried/seeded
     the already-posted / newly-written ledger row by importing the module's own
     `PO_RETURN_ITEM_SOURCE` constant for both the write side (seed, in P-25) and the read
     side (`inv_rows_for`'s default `source_type=`), so a mutant that changes the constant's
     value (L15 `'purchase_return_item'` -> `''`) stayed self-consistent and undetected.
     Fixed by: PRI-P-01 now calls `inv_rows_for(db, ri1, source_type='purchase_return_item')`
     (literal) to re-read the row the function itself wrote; PRI-P-25 now seeds its
     pre-existing posted row with an inline `inv_ledger_row(..., source_type='purchase_return_item', ...)`
     call instead of `posted_storage()` (which reads the constant), and re-reads with the
     same literal. Re-ran the mutation tool after the fix:
     `.venv/Scripts/python.exe tests/unit/_tools/mutate.py app/managers/po_return_inventory.py tests/unit/managers/test_po_return_inventory.py --timeout 180`
     → `Mutants: 48 · killed 48 · timeout 0 · survived 0 · score 100%` (was 47/48, 98%, with
     L15 `'purchase_return_item'` -> `''` surviving, before this fix).
  2. *Missing assertion* — PRI-P-33 asserted only `exc.value.detail.endswith(SUFFIX)`, not the
     case's required `raises 400`. Added `assert exc.value.status_code == 400` before the
     detail assertion.
  No case text, expected value, or marker was changed; both fixes are test-code-only. Full
  file re-run after the fix: 65 passed, 3 xfailed (identical to before), 100% branch coverage
  (unchanged — these fixes address mutation strength, not line/branch coverage). Stable across
  3 consecutive runs.

## How the tests are built

- **Conventions → fixtures/helpers** (top of the test file, each commented with its convention):
  - W1/W2 → `w1`, `w2` (`make_workspace`); U1/U2 → `u1`, `u2` (`make_profile`).
  - F1/F1d/F2, M1/M3/M1d/M2, I1/I2/IX → local `mk_factory`/`mk_machine`/`mk_item` plus
    fixtures `f1`, `f1d`, `f2`, `m1`, `m3`, `m1d`, `m2`, `i1`, `i2`, `ix` (one insert +
    flush each, so ids ascend in insertion order, matching the cases file's reliance on
    insertion order for some "latest" assertions).
  - PO / PL / R / RI → `mk_status` (a throwaway `Status` row — `current_status_id` is
    `NOT NULL` with no bearing on this module), `po_` (fixture factory taking
    `dest_type`/`dest_id`, always `po_number="PO-0012"`), `mk_line` (`PurchaseOrderItem`,
    `quantity_ordered=1000` so `quantity_remaining`/returnable checks never interfere),
    `mk_return` (`PurchaseOrderReturn`), `mk_ri` (`PurchaseOrderReturnItem`; `item_id`
    defaults to the paired line's `item_id` per the pairing convention, overridable).
  - **Timestamps (G2)** → fixture `clock`: `base = utcnow() - 1 day`, then
    `base + N minutes` on each call, strictly increasing. Every storage-ledger and
    machine-ledger seed row takes an explicit `performed_at` from `clock()` (or a
    hand-computed offset for P-43/P-46, which deliberately insert the earlier-timed row
    second). Rows the function itself writes get the real `performed_at` default
    (storage: DB `now()`; machine: Python `utcnow()`), which is always later than any
    seed and is never asserted.
  - **S(F, I) = n @ p / D(F, I) = n** → `S()` / `D()`: insert the `Inventory` snapshot
    row *and* the required G1 "opening" storage-ledger row (`source_type='test_seed'`,
    `source_id=1`, `qty_before=0`, `qty_after=n`, `avg_price_after=p`) via
    `mk_inventory_row` + `inv_ledger_row`. Cases needing a stock row that deliberately
    disagrees with the ledger (P-41/42/43/44/45) call `mk_inventory_row` and
    `inv_ledger_row` directly instead of `S()`, so the two can differ.
  - **MH(M, I) = n** → `MH()` (`MachineItem`). **ML(M, I, avg=p)** → `ML()`
    (`MachineItemLedger`, `source_type='test_seed'`, `source_id=1`); takes an optional
    explicit `performed_at` for P-46's out-of-order insert.
  - **Posted-row(ledger, RIk)** → `posted_storage()` / `posted_machine()`
    (`source_type=PO_RETURN_ITEM_SOURCE`, `source_id=ri.id`).
  - Raw rows for the `_machine_ledger_exists` / `_storage_ledger_exists` sections
    (arbitrary `source_type`/`source_id`, no stock semantics) → `seed_mledger()` /
    `seed_iledger()`.
  - **"No return rows"** → `no_return_rows(db, *ris)` (both ledgers, no workspace
    filter — matches the convention's "in any workspace" wording for the *absence*
    check; presence checks that must stay workspace-scoped pass `workspace_id=` to
    `inv_rows_for`/`mch_rows_for` explicitly, e.g. P-29).
  - Re-read → `reread_one_inventory` / `reread_inventory_rows` (asserts exactly one row
    for the "no duplicate created" cases) / `reread_machine_item`, all `expire_all()`
    then a fresh `SELECT`. `inv_rows_for` / `mch_rows_for` likewise re-query by
    `(source_type, source_id)`. `events_since(db, ws, before_id, machine=None)` captures
    the max activity-event id before the call and diffs by id afterwards (also used to
    assert *no* event was written).
  - `check(row, **expected)` asserts a named set of attributes with per-field failure
    messages (used throughout in place of one large `==` dict, so a wrong field is easy
    to spot in failure output).
  - Wrapper `qti(q, ident)` — inspects `inspect.signature(_quantity_to_int).parameters`
    once at import time and calls with `line_number=` if present, else `po_item_id=`,
    per the cases file's convention (keeps the PRI-QTI pass cases running after the
    BUG-802 rename).
- **Mocks:** none, per the spec's Externals and the cases file's Conventions
  ("Externals mocked: none"; "Race simulations: none"). `utcnow` is the real clock
  everywhere; only seeded rows get explicit timestamps.
- **xfail honesty:** `--runxfail` confirms each of the 3 xfails fails on the case's
  "fails today on" assertion: PRI-QTI-05 fails with `TypeError` (`_quantity_to_int()`
  has no `line_number` parameter today); PRI-P-32 (BUG-802, strict) fails on the detail
  string (`"...PO item {id}..."` vs the expected `"...PO line 2..."`); PRI-P-47
  (BUG-803, `strict=False` per the cases file) fails on `row3.qty_before` — expected
  `4`, got `7` in this run, i.e. line 3 re-synced from line 1's `10→7` row instead of
  line 2's `7→4` row, which is exactly the spec's own example of the bug (final stock
  ends at 4, not the intended 1). Because the tie is nondeterministic, a different run
  could instead get the intended `4` here by chance (XPASS, silently allowed since the
  marker is non-strict) or a different wrong value.
- **Database-error-shaped case (P-42):** no `pytest.raises`/`begin_nested` needed — the
  "insufficient stock" 400 is an ordinary `HTTPException`, not a DB-level error; the
  re-sync's overwrite of the stock row is asserted by reading the same row (`db.get`)
  after the exception propagates, with no rollback in between (the `db` fixture's own
  rollback happens only at test teardown).
- **PRI-P-32** guards `pl2.id != 2` and creates a throw-away line first if needed, so the
  renamed-kwarg assertion (`"PO line 2"`) is never coincidentally satisfied by `pl2.id`
  happening to equal 2 under today's (unfixed) `po_item_id`-based message.
- Stability: 3 runs, identical outcome (65 passed, 3 xfailed) — including PRI-P-47,
  which is nondeterministic by design (`strict=False`) but passed by chance in 0/3 runs
  here (XPASS is possible and would simply be a silent pass under `strict=False`, which
  is why it is not strict).

## Discrepancies
None. Every case's designed outcome (pass / xfail) matched the actual run.

## Coverage gaps
None — 100% branch coverage (40 statements, 14 branches, 0 partial). The three
deferred-rule cases (R17/HR-10/BUG-800, and BUG-801 — both deferred to other modules
per the cases file) and the retired PRI-P-04 (unobservable rounding, per spec R8b/G5)
account for everything the cases file does not ask this file to cover.

## Factories added
None to `tests/unit/factories.py` (batch mode: left untouched; only `make_workspace` and
`make_profile` were reused from it). **Promotion candidates for the merge pass:**
`mk_factory`, `mk_machine`, `mk_item`, `mk_status`, and the `PurchaseOrder`/line-item
builders (`mk_po`/`mk_line`-shaped) are now duplicated near-verbatim in
`tests/unit/managers/test_po_receive_inventory.py` (a sibling module over the same
models) — this is exactly the "a second test file needs the same model" trigger in
`factories.py`'s own docstring. Recommend promoting these as `make_factory`,
`make_machine`, `make_item`, `make_purchase_order` (with `destination_type`/
`destination_id`/`po_number` params) once both modules are reconciled in one pass, since
the two files' current signatures differ slightly (e.g. `mk_item` here has no `deleted`
param; the receive-side one does) and should be unified rather than merged blindly.

## Notes for maintainers
- **PRI-P-47 / BUG-803** is the only non-strict xfail; its outcome depends on which of
  two same-`performed_at` storage-ledger rows Postgres's `ORDER BY performed_at DESC`
  returns first within one transaction (ties broken by physical row order, which is not
  guaranteed). When BUG-803 is fixed (tie-break by `id` descending in
  `InventoryLedgerDAO.get_latest_entry`), this test will reliably pass; the marker can
  then be removed.
- **When BUG-802 is fixed** (`_quantity_to_int` takes `line_number` instead of
  `po_item_id` and the message changes), PRI-QTI-05 and PRI-P-32 will XPASS — remove
  their `xfail` markers. Note the `qti()` wrapper in this file auto-detects the
  parameter name, so no other test needs to change.
- **BUG-800 (R17) and BUG-801** are deferred to other modules per the cases file
  (`PurchaseOrderService.complete_return` / `inventory_movements`, and the return-start
  code path, respectively) — nothing in this file exercises them, by design.
- The storage-ledger "opening row" seeding (G1, via `S()`/`D()`) is load-bearing: a
  stock row inserted without a matching ledger row is always re-synced to qty 0 / avg
  null by R8a on the next deduction. Any future case that seeds storage stock must go
  through `S()`/`D()` (or replicate both rows manually, as P-41/42/43/44/45 do when the
  snapshot must deliberately disagree with the ledger).
- The 15 `SAWarning: GenericFunction … already registered` warnings under `--cov` come
  from coverage re-importing the SQLAlchemy Postgres dialect; unrelated to these tests
  (same as noted in `department_manager.notes.md`).
- The `datetime.utcnow()` `DeprecationWarning` in the `clock` fixture is pre-existing
  Python 3.12 noise from a stdlib-style call also used elsewhere in this test suite; not
  fixed here since it does not affect the seeded timestamps' correctness and the cases
  file's convention describes `T0` in exactly these terms.

## Decisions made
- All of this revision's "best-practice default, delegated by reviewer" items were
  decided in the cases file itself (rev 2/3), not newly by this execution pass: the
  `"latest" = performed_at desc, then id desc` tie-break (BUG-803, precedent BUG-664),
  the R17 unit-test deferral (BUG-800, G6), and the `qti()` wrapper's keyword-detection
  fallback. No new decisions were required during implementation; the existing test file
  (found already written, matching the cases file exactly) needed no behavioral changes
  — only verification (fresh 3x run, coverage, case-ID-to-test mapping audit).
