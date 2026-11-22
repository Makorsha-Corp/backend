# Execution notes — `app/services/transfer_order_service.py`

> Cases: `tests/unit/services/transfer_order_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_transfer_order_service.py` · Source commit: e48a092
> Result: 106 passed · 8 xfailed · 0 discrepancies · 0 errors — branch coverage 100% (137 statements, 0 missed)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_transfer_order_service.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- **Standing rows** are built by the fixture `s` (a `SimpleNamespace`): W0 < W1 < W2, U1 … U5 with the card names, the five `WorkspaceMember` rows, S0/S1/S2, F0/F1/FB/F2, M1 (`id=XID(1)`), I1/I2/IX. Each row is flushed as it is added.
- **Given rows**: `order` / `order_o0` / `order_o9` (keyword overrides are the card's "but" columns), `completed(s)`, `looped(s)`, `line`, `apr` (+ `APPROVED`), `ev`, `ho` / `add_ho` (HO; `ho` is unsaved for the `add_all` cards). `CREATE`, `ITEM`, `UPD`, `IU`, `DEL` follow the Conventions. `DEL` adds `user_id=U2.id` only when the signature has it.
- **Commit point**: `commit_point(db)` runs `db.commit()` (this only releases the fixture's savepoint) and returns the "nothing written" counts of the seven tables. `unchanged(X)` is `snap(db, Model, id)`, a Core SELECT of every column, taken right after the commit point. X = `mk_x(db)`, a flushed, uncommitted workspace. `x_gone` / `committed:` lines start with `db.rollback()`.
- **Ids into locals**: the commit expires every ORM object. Cards that patch `db.commit` or `db.refresh`, or run spies, read the ids they need into locals at the commit point, so a lazy reload never runs inside the patched block. The recorder cards (U-13, AI-11) must do this anyway, because they `expunge_all()`.
- **Patches** (all from Conventions): `app.managers.transfer_order_manager.utcnow` → NOW (autouse `clock`); `M.to_dao.get_next_number` → TNUM (`nump`); `app.managers.transfer_order_manager.post_transfer_order_inventory` (`pm_patch`, with `probe_ok` / `probe_err` for MC-04 / MC-07); `app.services.transfer_order_service.handle_order_update_notifications` / `handle_add_approver` (`nu` / `na` with `nprobe`); commit / rollback spies, failing commit and failing refresh as in the other service suites.
- **Lock first** (U-13, AI-11): `record_sql` listens to `before_cursor_execute` on the session's connection. `locked_before_items` collapses the whitespace of each statement. It looks for a SELECT `FROM transfer_orders` that ends in exactly `FOR UPDATE OF transfer_orders` and comes before the first SELECT `FROM transfer_order_items`. `no_nowait` forbids `NOWAIT` / `SKIP LOCKED`. Both assertions sit under `# Then 2`.
- Stamps are compared with `stamp(v)` (tzinfo removed), per the Conventions.
- **xfail verification** (`--runxfail --tb=line`): each strict xfail fails under the `# Then N` comment the card names. U-12 / AA-08 / RA-05 fail with `DID NOT RAISE` (Then 1), U-13 / AI-11 on `locked_before_items` (Then 2), U-14 on `approved is False` (Then 2), and D-06 on `"user_id" in params` (Then 1). D-05 fails on the call itself (`TypeError: unexpected keyword argument 'user_id'`). The card's "Fails today on: Then 1" says exactly that, so the `# Then 1` comment sits above the call.
- **Reference plugin** (scratch only, `…/svc2e/transfer_order_service/tos_reference.py`, loaded with `-p tos_reference --runxfail`): it patches the intended behaviour for BUG-3142 (`FOR UPDATE OF transfer_orders` pre-read), BUG-1194 (required `user_id` + audit row), BUG-2899 (merged-route check), BUG-2903 (approval wipe + `approvals_reset`) and BUG-2897 (completed order refuses approver add / remove). Result: 108 passed, 1 deselected. TOS-U-11 is deselected on purpose: its card is tagged "retire when BUG-2899 is fixed", and with that fix its edit is refused.
- **Stability**: the file was run plain 6 times at Revision 2 and 3 times at Revision 4, with identical outcomes every time (Revision 4: 106 passed, 8 xfailed).

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 | TOS-HF-01 … HF-04 | — | — | **Resolved in Revision 3**: the cards now call `svc._hub_filter_kwargs(...)`, and the tests use that exact form. | — |

## Coverage gaps
None. 100% (137 statements; coverage.py counts no branch arcs in this file, because the only decisions are the two conditional expressions in `_hub_filter_kwargs`, and HF-02 / HF-03 / HF-04 exercise both arms of each).

## Factories added
None. All builders are local to the test file.

## New bugs
None. BUG-3079 … BUG-3081 were not used.

## Notes for maintainers
- When **BUG-3142** is fixed, U-13 and AI-11 XPASS: remove their markers. The companion pass cards (U-04 … U-08, AI-02 … AI-05) must stay green.
- When **BUG-1194** is fixed, D-05 and D-06 XPASS. `DEL` then passes `user_id=U2.id` automatically.
- When **BUG-2899** is fixed, U-12 XPASS and **U-11 fails**. Retire U-11 as its card says (no replacement card, spec G4).
- When **BUG-2903** is fixed, U-14 XPASS. U-09 stays green: it checks only `required_approvals` and the notes.
- When **BUG-2897** is fixed, AA-08 and RA-05 XPASS.
- Fragile spots: HS-01 / HS-02 rely on the DAO's highlight rules (an order with a line → "Planned", `source_location_id=0` → "Draft"). LP ordering relies on `created_at` descending. Both are owned by `dao/transfer_order.cases.md`.
- The hub DAO emits `SAWarning: Coercing Subquery object into a select() for use in IN()` (`app/dao/transfer_order.py:256` and `:315`). It does no harm today, but it is a deprecation path the DAO owner should clean up.

## Revision history
- **Revision 3 (2026-11-22).** HF-01…04: calls changed from `TransferOrderService._hub_filter_kwargs(svc, …)` to the cards' `svc._hub_filter_kwargs(…)` (values unchanged); the section comment and the unused `TransferOrderService` import were removed. DISCREPANCY-1 resolved. Re-checked: `--runxfail` (8 failed, as designed), reference plugin 108 passed + U-11 deselected, 3 plain runs `101 passed, 8 xfailed`, coverage 100%, ruff clean, LF.
- **Revision 4 (2026-11-22)**, from verifier findings 1–6.
  - (1) D-02, D-03, UI-02, UI-03, RI-03, RI-04, RA-03, SA-03, SA-04 now bind `x` from `mk_x` and assert `x not in db` as the new Then 4, right after the call; the later Then numbers shifted by one.
  - (2) New G-03 and AS-03, W0 twins of G-02 and AS-02.
  - (3) New HF-05: `source_location_type=""` with `destination_location_type="all"`.
  - (4) HS-02 now calls with `exclude_complete=False`; it expects (2, 1, 1), machine count 2 and recent orders `{A, C}`. It keeps C's handle for that last check.
  - (5) U-13 now runs on the plain routed order O (F1 → FB) with a line and `UPD(description="New text")`. It gains Then 3: some recorded SELECT is FROM `transfer_order_items`. Under `--runxfail` it still fails on Then 2.
  - (6) New U-19 and AI-14: MISSING id → 404 with `X not in db`, nothing written, and `x_gone`.
  - Re-checked: 114 case IDs ↔ 114 tests; `--runxfail` gives 8 failed, as designed; the reference plugin gives 113 passed with U-11 deselected; 3 plain runs gave `106 passed, 8 xfailed`; coverage 100%; ruff clean; LF.
