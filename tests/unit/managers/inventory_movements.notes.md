# Execution notes — `app/managers/inventory_movements.py`

> Cases: `tests/unit/managers/inventory_movements.cases.md` (revision 5) · Tests: `tests/unit/managers/test_inventory_movements.py` · Source commit: e48a092
> Result: 121 passed · 30 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_inventory_movements.py -q -p no:cacheprovider --cov=app.managers.inventory_movements --cov-branch --cov-report=term-missing`

## How the tests are built

All 152 cases across the 11 callables (`item_name`, `weighted_avg_price`,
`inventory_type_for_location`, `_storage_out`, `_storage_in`,
`ensure_machine_item`, `get_machine_unit_cost`, `_machine_out`, `_machine_in`,
`post_stock_out`, `post_stock_in`) are implemented, one test per case ID
(`test_invm_<id>__<slug>`), in callable order matching the cases file.

**Conventions -> fixtures/helpers** (all at the top of the file, built
incrementally across the batch):
- `T0`/`T1`/`NOW`/`NOID`/`S50`/`S51` — module constants per the cases file's
  Conventions section.
- `_freeze_now` (autouse) — patches the `arg` callable on
  `MachineItemLedger.performed_at`'s column default and
  `MachineActivityEvent.created_at`'s column default to return `NOW`. This
  module has no `utcnow` of its own; factory-ledger `performed_at` is the DB's
  `now()` and is asserted "not None and > T1" instead, never frozen.
- `w1/w2`, `u1/u2` — two workspaces, two profiles (`make_workspace`/
  `make_profile` from `tests/unit/factories.py`).
- `f1/f1b/f2/f3`, `m1/m1b/m2/m3`, `i1/i2/ix/i_off` — local model fixtures (not
  promoted to `factories.py`; see "Factories added" below) for factories,
  machines and items per the cases file's Actors-and-rows convention. `f3`/`m3`
  are soft-deleted; `i_off` is `is_active=False`; `ix` lives in `w2`.
- `mk_inventory`/`mk_inv_ledger`/`mk_machine_item`/`mk_machine_ledger` — raw
  row builders used directly (not as fixtures) whenever a case's Given needs a
  bucket/ledger pair that doesn't match the `S`/`MS` shorthand (e.g. a bucket
  whose qty/avg disagrees with its one ledger row, for R3a-sync and BUG-664
  tie cases).
- `S`/`MS` fixtures — implement the cases file's `S(F,I,TYPE,q,p)` /
  `MS(M,I,q,p)` shorthand: one stock row + one matching "opening" ledger row
  dated `T0`.
- `so_kwargs`/`si_kwargs`/`mo_kwargs`/`mi_kwargs`/`pso_kwargs`/`psi_kwargs` —
  per-callable default-call-argument builders (cases state only what differs).
- `reread_inventory`/`reread_machine_item`/`inventory_rows`/`ledger_rows`/
  `ledger_rows_any_type`/`machine_item_rows`/`machine_ledger_rows`/
  `machine_events`/`rows_matching` — re-read helpers, all calling
  `db.expire_all()` first per the "re-read" convention. `rows_matching` ORs
  several column-equality checks for "no row with factory_id X or item_id Y
  anywhere" assertions (PSO/PSI R6 check-order cases).
- `assert_no_events` — zero `machine_activity_events` rows across the given
  workspaces ("No events" convention).
- `SqlCapture` — a `before_cursor_execute` listener for the BUG-660/661 lock
  cases, following the `payment_transaction_manager` RR-08 pattern.

**Race simulations:** none (per Conventions).

**Mocks:** none beyond the `_freeze_now` column-default patches above — no
DAO, session or manager method is mocked anywhere in this file.

**DB-error / IntegrityError cases:** every case expecting `IntegrityError` or
`DataError`, and every xfail case whose today-behavior is one of those, runs
inside `db.begin_nested()` so the session stays usable for the re-read
assertions afterward.

**Error-path flush:** cases marked "(flush)" in the cases file call
`db.flush()` after catching the exception and before re-reading, to make an
in-memory bucket create/restore/sync visible.

**BUG-664 tie cases** (SO-18, SI-15, MUC-05): three ledger rows with the same
`performed_at` are inserted one after another in the cases file's Tie
insertion order — row B (db-assigned id), then row C with an **explicit id**
= `nextval(pg_get_serial_sequence('<table>', 'id')) + 1_000_000` (peeked via
the local `_next_id_plus` helper just before the insert), then row A
(db-assigned id) — so `id(B) < id(A) < id(C)` regardless of query plan. The
assertions encode the *intended* (bug-fixed) behavior — sync/lookup from C —
and are marked `xfail(strict=True)`, since today's code (`ORDER BY
performed_at DESC` with no id tiebreak) returns either B (physically-first
plan) or A (highest-TID / backward-index-scan plan) depending on the plan;
both are observed as the "fails today on" value across runs, never C, so the
xfail is no longer plan-dependent. `mk_inv_ledger`/`mk_machine_ledger` both
take an optional `row_id` to support the explicit-id insert. SO-19 (the
spec's three-postings-in-one-save example) is retired per cases revision 4 —
see Revision history below.

**xfail reasons:** one `BUG_xxx` string constant per bug (`BUG_660`..`BUG_666`),
used verbatim as the `xfail(reason=...)` so every xfailed test names its bug.

## Discrepancies
None. Every case's designed outcome (`pass` / `xfail BUG-NNN`) matched the
actual run outcome; no test needed a `DISCREPANCY-n` marker.

## Coverage gaps
None — 100% branch coverage (120 statements, 34 branches, 0 missed) on
`app/managers/inventory_movements.py`.

## Factories added
None. All model builders for this module (`_mk_factory`, `_mk_machine`,
`_mk_item`, `mk_inventory`, `mk_inv_ledger`, `mk_machine_item`,
`mk_machine_ledger`, and the `S`/`MS` fixtures) are local to
`test_inventory_movements.py` per batch-mode rules (`tests/unit/factories.py`
not edited this run). Worth promoting later if other manager/DAO test
modules need factory/machine/item builders with soft-delete / inactive
variants:
- `_mk_factory(db, ws, name, *, deleted=False)` -> candidate `make_factory`
- `_mk_machine(db, ws, factory, name, *, deleted=False)` -> candidate `make_machine`
- `_mk_item(db, ws, name, *, active=True)` -> candidate `make_item`
- `mk_inventory`/`mk_inv_ledger` -> candidate `make_inventory` / `make_inventory_ledger`
- `mk_machine_item`/`mk_machine_ledger` -> candidate `make_machine_item` / `make_machine_item_ledger`

## Decisions made (best-practice default, delegated by reviewer)
These were already flagged as such in the cases file's Reviewer summary and
Conventions (not new decisions made during execution):
- Error-path re-reads call `db.flush()` explicitly before asserting, so a
  bucket create/restore/sync that happened before the exception is observable.
- `dest_id`/`source_loc_id` use real ids (e.g. `F1b.id`, `M1.id`) even where
  the column has no FK, to keep values meaningful.

## Notes for maintainers
- **BUG-660/661 (row locks)** — unit-tested only via `SqlCapture` SQL-text
  inspection (`SELECT ... FOR UPDATE` on `inventory` / `machine_items`); the
  real two-session race is Deferred to integration tests per the cases file.
  When fixed, `test_invm_so_14`, `test_invm_si_12`, `test_invm_mo_14`,
  `test_invm_mi_12` will XPASS — drop their `xfail` markers.
- **BUG-662/663 (soft-deleted factory/machine accepted)** — fix by having
  `factory_dao.get_by_id_and_workspace` / `machine_dao.get_by_id_and_workspace`
  filter `is_deleted == False` (or the manager check it). Affects
  `test_invm_so_13`, `test_invm_si_11`, `test_invm_mo_13`, `test_invm_mi_11`.
- **BUG-664 (tie-break by insertion order, not id)** — fix by adding a
  secondary `ORDER BY id DESC` to `inventory_ledger_dao.get_latest_entry` and
  `machine_item_ledger_dao.get_latest_entry`. Affects `test_invm_so_18`,
  `test_invm_si_15`, `test_invm_muc_05`. If fixed, these three tests XPASS.
- **BUG-665 (qty < 1 accepted)** — `post_stock_out`/`post_stock_in` never
  validate `qty`. Fix by adding a `qty < 1` check (checked first, per the
  cases file's R6 check-order). Affects 8 tests: `test_invm_pso_11/12/13/14`,
  `test_invm_psi_09/10/11/12`.
- **BUG-666 (item never checked to belong to the workspace)** — every
  `_storage_out`/`_storage_in`/`_machine_out`/`_machine_in` call trusts
  `item_id` without an `item_dao.get_by_id_and_workspace` check; a foreign or
  unknown item either silently succeeds (FK satisfied by another workspace's
  row) or raises a raw `IntegrityError`/`DataError` instead of a 404. Affects
  10 tests across both callables and both `post_stock_*` dispatchers
  (`test_invm_so_15/16`, `test_invm_si_13/14`, `test_invm_mo_15/16`,
  `test_invm_mi_13/14`, `test_invm_pso_20/23`). Fixing this bug will also flip
  the currently-`pass` inactive-item-accepted cases' *item lookup*, but not
  their *is_active* outcome — those (`*_21`/`*_16`/`*_17`/`*_15` boundary
  cases) only assert that an inactive item is still accepted, which is
  intended behavior (`item_name` R3 / Coverage matrix) and is independent of
  BUG-666.
- **BUG-1040 (money rounds half up, HR-15)** — fix by passing `ROUND_HALF_UP` to every `quantize` in `app/managers/inventory_movements.py`. `test_invm_wap_04` will XPASS, so drop its marker; `test_invm_wap_05` passes before and after. The `total_cost` lines (`_storage_out`, `_storage_in`, `_machine_out`, `_machine_in`) have no midpoint case here.
- **Fragile spots:** none. The BUG-664 tie tests no longer depend on which
  plan Postgres picks for same-timestamp rows: row C's id is pinned 1,000,000
  above the sequence, so *every* plan (physically-first or highest-TID)
  returns a wrong row (B or A), and only the fixed `ORDER BY performed_at
  DESC, id DESC` returns C. Verified flake-free over 8 full-file runs plus 6
  isolated reruns of `so_18`/`si_15`/`muc_05` (revision 4 fix for the
  verify.md flakiness finding). All money/avg assertions compare `Decimal`
  after `db.expire_all()` re-reads, so there is no float-precision concern.

## Revision history

**Revision 4** (this run) — cases file bumped to revision 4 (spec Gap log G6)
and `inventory_movements.verify.md` routed four findings here:
1. **Tie insertion order (case designer's part of finding 2, carried into the
   executor's rewrite):** SO-18, SI-15 and MUC-05 now insert their three tied
   ledger rows as B, then C (explicit id = `nextval(...) + 1_000_000`, via the
   new `_next_id_plus` helper), then A — per the cases file's rewritten Tie
   insertion convention — instead of the old A/B/C-by-autoincrement order.
   This makes the "fails today" result deterministic (B or A, never C) instead
   of flaky; see "Fragile spots" above. SO-19 (the three-postings-in-one-save
   strict xfail) is **removed** — the cases file retires it as flaky-by-design
   (restore as a plain pass case once BUG-664 is fixed). SO-20 (already
   present, unaffected) continues to cover the no-tie two-postings case.
2. **Finding 1 (MO-15 dishonest xfail):** `test_invm_mo_15` referenced the
   module-level `u1` fixture *function* instead of a test parameter (crashed
   with `AttributeError` under `--runxfail`), and never created the ledger row
   its Given (`MS(M1, IX, 10, 4.00)`) requires. Fixed by adding `u1`/`MS` as
   test parameters and building the row through the `MS` fixture, which
   creates both the `machine_items` row and its matching ledger row. Verified
   under `--runxfail`: now fails honestly on `DID NOT RAISE HTTPException`.
3. **Finding 3 (SI-13/MI-13 begin_nested vacuous after fix):** both dropped
   the `db.begin_nested()` savepoint wrapper and now just catch, then
   `db.flush()`, per the cases file's "(flush)" convention (a savepoint would
   roll back the very bucket/machine-item row the "item check ran before
   create" assertion needs to find once BUG-666 is fixed). Verified under
   `--runxfail`: both still fail honestly on `DID NOT RAISE HTTPException`.
4. **Finding 4 (PSI-08 weakened assertion):** now asserts
   `ledger_rows_any_type(db, w1.id, f1.id, i1.id) == []` instead of filtering
   to `STORAGE` only, matching the case's "no `inventory_ledger` rows ...
   (any type)".
- Finding 5 (incomplete mutation run) is the verifier's to re-run, not an
  executor change.
- No case's designed outcome (`pass`/`xfail BUG-NNN`) changed; all four fixes
  are setup/assertion corrections, not new discrepancies. Full-file result
  after the fixes: 151 collected (down from 152: SO-19 retired), 122 passed,
  29 xfailed (down from 30: SO-19's xfail removed), 100% branch coverage,
  reproduced stable across 8 full-file runs.

**Revision 4, finding fix** (this run) — `inventory_movements.verify.md`'s
re-verification routed one finding to the executor: MO-15, MI-13 and PSO-23
all create a W2 workspace (via the `ix` fixture, which depends on `w2`), but
each called `assert_no_events(db, w1)` instead of `assert_no_events(db, w1,
w2)`, so the "No events = zero rows in W1 **and** W2" convention was only
half-checked (MO-12 and MI-10 already did this correctly). Fixed by adding
`w2` to each test's parameters and passing it to `assert_no_events`. Cases
file unchanged (still revision 4; no case content changed, so no cases-file
edit was needed). Verified under `--runxfail -k "mo_15 or mi_13 or pso_23"`:
all three still fail honestly on their original "fails today on" assertion
(`DID NOT RAISE HTTPException` for MO-15/MI-13, `assert 400 == 404` for
PSO-23) — the `assert_no_events` line is never reached in the xfail path, so
this was a pure fidelity fix with no effect on pass/fail outcome. Full-file
result unchanged: 151 collected, 122 passed, 29 xfailed, 100% branch
coverage, reproduced stable across 3 full-file reruns after the fix.

**Revision 5** (2026-10-30) — owner ruling BUG-1040: all money rounds half away
from zero (HR-15). Spec R2 split into R2 and R2a [BUG-1040]; cases revision 5.
- `test_invm_wap_04` renamed `__midpoint_rounds_half_up`, expects `0.03`, strict
  xfail BUG-1040. Under `--runxfail` it fails on
  `assert Decimal('0.02') == Decimal('0.03')`, as its card says.
- `test_invm_wap_05` renamed `__midpoint_never_rounds_down`, docstring reworded,
  expected value `0.04` unchanged, stays a plain pass: 0.035 gives `0.04` under
  half up and half even alike, so a strict xfail would XPASS and fail the file.
- Result: 121 passed, 30 xfailed, 100% branch coverage (120 statements, 34
  branches). With half up simulated (`decimal` context set to `ROUND_HALF_UP` by
  a throw-away plugin, `app/` untouched) only `test_invm_wap_04` changes: it
  XPASSes and strict-fails, which is what the fix should cause.
