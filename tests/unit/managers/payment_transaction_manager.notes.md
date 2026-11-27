# Execution notes — `app/managers/payment_transaction_manager.py`

> Cases: `tests/unit/managers/payment_transaction_manager.cases.md` (revision 5) · Tests: `tests/unit/managers/test_payment_transaction_manager.py` · Source commit: e48a092
> Result: 108 passed · 64 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_payment_transaction_manager.py -q -p no:cacheprovider --cov=app.managers.payment_transaction_manager --cov-branch --cov-report=term-missing`

## How the tests are built
- **Conventions → helpers** (top of the test file, each commented with its convention):
  - W1/W2 → fixtures `w1`, `w2` (`make_workspace`). U1 → `u1` (`make_profile(name="Rahim Uddin", email="rahim@example.com")` plus an `owner` `WorkspaceMember` row in W1). U2 → `u2` (default profile, member of W2). The manager never checks membership; the rows are there only so the fixtures match "a profile in W1/W2".
  - A26/B26/C26/D26 → constants. NOW, V0, and T's `updated_at` (UPD0) → constants.
  - T → `mk_txn(db, ws, user, tran_id=A26, **overrides)`: one insert + flush, T's default values. `failed_reason`/`outcome_verified` are passed only by the BUG-026 cases. They raise `TypeError` at construction today, as the cases file expects. Fixtures: `t` (T in W1, AVR/RR sections) and `t2` (T in W2, FIN/MTW sections).
  - OK → module constant `OK`. "OK with X" → `ok(**overrides)` (`dataclasses.replace`). `invalid(tran_id)` builds the INVALID_TRANSACTION answer. `unattempted` is the default `query_by_tran_id` side effect. `query_map({tran_id: result | exception})` builds per-candidate side effects for the sweep.
  - H → fixture `h` / `make_h(db, ws, user, clock)`: `_apply_validation_result(OK with risk_level=1, "Suspicious card")` runs with `clock.return_value = V0`, then the clock is set back to NOW. H* → `make_h_star` (direct insert with `outcome_verified=True`, BUG-026 only). The untagged RISK_HOLD setups (FIN-08, FIN-12, REC-02) use `to_risk_hold`.
  - Events → `events(db, txn_id)` (expire_all, then query by id order). `ev_tuples` + `E(txn_id, ws_id, type, desc, performed_by=None, metadata=None)` check type, description, txn id, workspace, performer and metadata together. "Events after setup" is done by recording `n_setup = len(events(...))` before the action and slicing.
  - Return values (revision 4) → `_apply_validation_result` / `finalize_from_gateway` / `mark_terminal_without_validation` / `resolve_risk` cases assert identity (`ret is t`, `is t2`, `is h`, `is hs`). `initiate_payment` cases use `assert_returns_reread(db, res, ws_id, status)`: the ids of the re-read txns in the workspace equal `[res.id]` (W1 is empty before the call, so this is "the re-read txn"), and `res.status` equals the given status. INIT-14/15 compare `[res1.id, res2.id]` with the two re-read rows' ids. Sweep cases compare `ids(res)` with the expected list.
  - Re-read → `reread(db, id)` (`expire_all()` + `db.get`). Counts → `n_txns`, `n_events` (both expire first).
  - SQL capture → `SqlCapture(engine)`, a `before_cursor_execute` listener on the session-scoped `engine` fixture, attached only around the action. `has_select_for_update_on_txns()` looks for a statement that starts with SELECT, mentions `payment_transactions` and contains `FOR UPDATE`.
- **Patch targets** (from the spec's Overview): `app.managers.payment_transaction_manager.utcnow` (autouse fixture `clock`, returns NOW), `app.managers.payment_transaction_manager.get_sslcommerz_client` (autouse fixture `gw`: a `MagicMock(spec=SSLCommerzClient)` with the Conventions' defaults), and `app.managers.payment_transaction_manager.secrets.token_hex` (only GEN-02..05 and INIT-17). Model-default `utcnow`s are not patched. "No gateway client method called" means `gw.method_calls == []`.
- **Race simulation:** only REC-07. The `query_by_tran_id` side effect for A loads B with `db.get`, sets `VALIDATED_SUCCESS`, flushes, and returns UNATTEMPTED.
- **DB-error cases** (LOG-04, INIT-16, MTW-11): `pytest.raises(...)` wraps `with db.begin_nested():`. The context manager rolls the savepoint back, then the test re-reads. REC-29 is an xfail with no savepoint (per the case). Today the `DataError` escapes the call and the `db` fixture teardown cleans up.
- **REC-06:** the 201 candidates are added and flushed in one batch, with `tran_id = f"{i:026x}"`.
- **xfail honesty:** checked with `--runxfail`. Every xfail fails because of the bug named in its case. Most fail on the exact "fails today on" assertion. Some fail one assertion earlier in the Then order, from the same root cause:
  - FIN-15, FIN-19, FIN-21: the first Then assertion (`validate` called once) fails. The duplicate path is taken, so `validate` is never called. That is the same cause as "status stays CANCELLED/EXPIRED".
  - INIT-09..12 and INIT-15: `HTTPException 502` is raised from `payment_transaction_manager.py:86`.
  - The BUG-026 insert cases fail with `TypeError: 'outcome_verified' is an invalid keyword argument`. The BUG-026 read cases fail with `AttributeError: no attribute 'outcome_verified'`.
  - RR-08 fails on the FOR UPDATE check. REC-09 fails on `call(A26, val_id_hint=None) != call(A26)`. REC-29 fails with `DataError` (varchar(50)).

## Revision history
- **Revision 5 (2026-10-31)**: added commit spies LOG-05, INIT-32, AVR-44, FIN-28, MTW-16, RR-12, REC-30 (`commit_spy`, savepoint, re-read after rollback), under `# [claude] <ID>` at the end of the file. Each runs a success path. Result 108 passed, 64 xfailed, 100% branch. No discrepancy.
- **Lint only (2026-10-31)** — no case or test body changed. Comments added so ruff is clean: `# ruff: noqa: SIM117, FURB157, C408`, and `# noqa: DTZ001` on NOW, V0 and UPD0. Result unchanged: 101 passed, 64 xfailed, 100% branch.
- **Revision 4** (cases rev 4, verifier findings 1–3): no case was added, removed or renumbered, and no Expect changed. 109 tests gained exactly the return assertion that their case now lists. 106 gained a new one and 3 were tightened: INIT-01 and INIT-09 changed `res.id is not None` to the re-read-id check, and FIN-13 now checks both calls return T. No other assertion was changed. The xfail failure points are unchanged: each new return assertion comes before the bug assertion and passes today (checked with `--runxfail`). The targeted mutation run `mutate.py … --lines 145-170` reports `Mutants: 27 · killed 27 · timeout 0 · survived 0 · score 100%`. The verifier's survivors #27 (L149), #29 (L158) and #31 (L167), all `return txn → return None`, are now killed by AVR-12, AVR-17 and AVR-21 (and FIN-25).
- **Revision 3**: initial implementation of 165 cases (RR-08 restored, RR-10/RR-11 added).

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (132 statements, 34 branches).

## Factories added
None. `mk_txn` and the event helpers are local to this module. Move them to `tests/unit/factories.py` when a second test file (e.g. `PaymentTransactionService` or the payments endpoints) needs payment rows.

## Notes for maintainers
- **When a bug is fixed**, its strict xfails will XPASS. Remove the marker. BUG-019: INIT-09, 10, 11, 12, 15, 30. BUG-020: INIT-07, 08. BUG-021: INIT-18, 19. BUG-022: INIT-21, 23, 24. BUG-023: AVR-07..11, FIN-06, FIN-14, REC-15. BUG-024: AVR-23, 24, 26..29. BUG-025: AVR-15, FIN-11. BUG-026: AVR-37..43, FIN-15..18, 21, 22, 23, INIT-31, MTW-15, RR-09, 10, 11, REC-27. BUG-027: FIN-19, REC-19. BUG-028: FIN-04, 05, MTW-01..03. BUG-029: RR-08. BUG-030: REC-13, 14. BUG-031: REC-09. BUG-032: REC-21, 22, 28, 29.
- **Cases that need two fixes:** AVR-41 and AVR-43 (BUG-026 + BUG-023), and REC-14 (BUG-030 + BUG-025). Each keeps failing until both bugs are fixed. The xfail reason lists both.
- **After the BUG-026 fix**, the column exists. Then check that `mk_txn` without `outcome_verified` still gets `false` from the model default. AVR-42 depends on that.
- **After the BUG-023 fix**, the passing cases AVR-32..35, FIN-26 and REC-26 must stay green. They assert only "status not in {VALIDATED_SUCCESS, RISK_HOLD}" and the description, never the type.
- `NOW` is fixed in 2026. `initiated_at`/`created_at` come from the unpatched model default (real clock) only for rows created by `initiate_payment`, and no sweep case uses those rows.
- The `--cov` report can also list `app/dao/item.py`. That is a leftover from other coverage data, not from this file.
