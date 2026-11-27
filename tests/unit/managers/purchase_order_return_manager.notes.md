# Execution notes — `app/managers/purchase_order_return_manager.py`

> Cases: `tests/unit/managers/purchase_order_return_manager.cases.md` (revision 3, 2026-11-19) · Tests: `tests/unit/managers/test_purchase_order_return_manager.py` · Source commit: e48a092
> Result: 104 passed · 77 xfailed (75 strict, 2 non-strict) · 1 discrepancy (card wording, no marker change) · 0 errors — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_purchase_order_return_manager.py -q -p no:cacheprovider -o addopts=""`

## How the tests are built
- Normal mode (no local model); every test sits below a `# [claude] <ID>` comment, one test per card, in card order. Names and helpers match the twin `test_sales_order_return_manager.py`.
- **Standing rows** = autouse fixture `s` (SimpleNamespace): `TAG`, `W0 < W1 < W2`, `U1`, `U2`, per workspace `F0/F1/F9`, `ST0/ST1/ST9`, `AC0/AC1/AC9`, items `I1` "Pump", `I2` "Valve", orders `O0, O1, O2, O3, O9` (`po_number f"PO-{TAG}-<name>"`), all flushed in Conventions order. `s.AC_OF[ws.id]` picks the workspace's account for a credit note. Schema cards run with the standing rows too (autouse) but do not use them.
- **Given rows**: `mk_line(db, s, k, **but)` (line 2 always `I2`), `mk_return(db, s, "N", **but)`, `completed(s)` / `VOIDED` dicts, `mk_rline(db, R, L, "q", **but)`, `mk_cn(db, s, W, payment_status, **but)`, `voided_cn`, `confirmed_cn(**but)`, `void_step` (the Q47 Given line, a real `account_invoice_manager.void_invoice` call, then `db.expire_all()`), `seqscan`, `bump_l`. Invalid cross-workspace rows are inserted directly; no FK has to be disabled (all FKs are on ids only).
- **Requests**: `LN`, `REQ`, `V(db, s, req)`, `TOO`, `NOTHERE` exactly as Conventions; `TOO` / Q46 texts use U+2014.
- **Named checks**: `reread(db, Model, id)` (expire + SELECT), `snap` (every mapped column, for unchanged(X), taken after the last Given line), `counts` (the four tables, all workspaces, for "nothing written"), `assert_session_clean` (three asserts). For refusals the request is built before `pytest.raises`, so only the When call is inside the block.
- **Statement recorder**: fixture `rec` (`before_cursor_execute` on the session's connection), started right before the When and kept on until the test ends; `rec.sel(t)` parses the FROM part (joins included), `order_part`, `no_lock`, `locks` as Conventions. Recorder cards expunge after the Given (except `sync_return_paid`, which passes a loaded return).
- **Commit spy** (S-14): `patch.object(db, "commit", wraps=db.commit)` around `db.begin_nested()` + call; inside lines, `sp.rollback()`, after lines.
- **Mocks**: none (Conventions: Externals none, no race simulations). The Q47 cards call the real `AIM.void_invoice`.
- **RR cards (revision 3, BUG-2810)**: `PurchaseOrderReturnReplacementCreate` is imported at the top of each RR test (Conventions), so the module still collects. Helpers `RRQ(cls, (X, "q"), …)` (takes the imported class; `MISSING` in place of X), `RV(db, s, R, req)`, `RTOO`, `NOTPART`; setup shorthands `replaced_l1` (line 1, received 6.00, returned 4.00) and `replace_rc` (return `replace`, completed). "X has `quantity_replaced`" = `mk_rline(..., quantity_replaced=Decimal(q))` (a column that does not exist yet).
- Cards whose When raises today (V-14, V-17, V-18, V-20, V-51 … V-53, Q47-04 `HTTPException`; G-10, G-12 `TypeError`) fail in the When line directly above `# Then 1`, as their "Fails today on: Then 1 (the call raises …)" says.

## Checks done
- 3 plain runs: identical, `104 passed, 77 xfailed` each (revision 3).
- `--runxfail` with the executor's own line-mapping plugin (scratch `porm_failson.py`, maps the failing line of the test to its `# Then N` block and compares with the card): 42 failed, all 42 on the card's named Then line (or the When call for the "call raises" cards), 0 mismatches, every xfail card failing. Revision 3: 77 failed, 0 mismatches; all 35 RR cards fail before `# Then 1` on the in-test `ImportError` (see DISCREPANCY-1).
- Revision 3, schema-only reference (`PORM_REF_SCHEMA_ONLY=1`, only the schema patched in): the 30 method cards then fail exactly as their cards say — `AttributeError` (no `validate_replacement_receipt`) at the call, or `TypeError` (`quantity_replaced` is not a column) in the Given for RR-05, 06, 07, 09; 0 mismatches.
- Reference plugin (scratch `porm_reference.py`, monkeypatches the app in-process to the intended behaviour of BUG-2429, 2750, 2751, 2752, 2753, 2754, 2755, 2785, 2787, 2788, 2792, and for revision 3 BUG-2810: the schema, `validate_replacement_receipt` RR1–RR8, and the column `quantity_replaced` added to the model and, per test, to the table by `ALTER TABLE … ADD COLUMN IF NOT EXISTS` inside the test's rolled-back transaction): `--runxfail` → 181 passed. The ALTER takes an exclusive lock on `purchase_order_return_items` for the length of each test, so run the reference alone, not beside other files.
- `ruff check` clean (file header `noqa: DTZ001, FURB157` — naive datetimes and `Decimal("4")` literals are prescribed); `ruff --select F841,F811` clean; AST pass: no unused test arguments; LF line endings.

## Discrepancies
| ID | Case | Designed | Actual | Evidence | Likely cause |
|---|---|---|---|---|---|
| DISCREPANCY-1 | PORM-RR-01 … RR-04, RR-08, RR-10 … RR-30 (26 cards) | xfail BUG-2810; "Fails today on: Then 1 (the call raises AttributeError …)" | xfail as designed, but the first failure is `ImportError` on `PurchaseOrderReturnReplacementCreate`, before the call | `--runxfail` report; with the schema patched in (schema-only reference run) each fails with the named `AttributeError` at the call | Card wording: the Conventions import the schema inside the test and RRQ builds it before the call, so the import fails first while the schema is missing. Marker and assertions unchanged; for the case designer only (reword to "fails before the call: the schema and the method do not exist"). |

## Coverage gaps
None — 100% branch coverage (47 statements, 12 branches).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed, its strict xfails XPASS → remove the markers: BUG-2750 (V-14, V-15, V-17, V-18, V-20), BUG-2751 (V-21, V-23, V-24, V-26, V-27, V-55, V-56), BUG-2752 (SCH-08 … SCH-12), BUG-2753 (V-44), BUG-2754 (G-10, G-11, G-12), BUG-2755 (G-13, L-08; non-strict G-14, L-09), BUG-2429 (L-07), BUG-2785 (Q45-01, 03, 04, 07, 10, 12), BUG-2787 (Q46-01, Q46-05), BUG-2788 (Q47-03 … Q47-07), BUG-2792 (V-51, V-52, V-53), BUG-2810 (RR-01 … RR-35; the schema, the method and the `quantity_replaced` column must all land together, or the RR tests error in different places).
- G-14 / L-09 are non-strict: they rely on physical row order after an UPDATE under `seqscan`; today A comes last.
- Fix hints found while building the reference plugin:
  - BUG-2753: `PurchaseOrderItem.item` is joined-eager loaded, so a plain `.with_for_update()` on the lines fails in Postgres ("FOR UPDATE cannot be applied to the nullable side of an outer join"); the fix needs `with_for_update(of=PurchaseOrderItem)`. V-44 accepts that (`FOR UPDATE OF purchase_order_items`).
  - BUG-2755: setting `order_by` on the relationship after mapper configuration is not enough (the lazy loader copies it at init); the fix belongs in the model's `relationship(..., order_by=...)`.
  - BUG-2788 (`void_invoice` R3c): the completed-return refusal must come before any write, or Q47-07's "session clean" / CN still `confirmed` fail.

## Revision history
- **2026-11-19 — cases revision 3 (BUG-2810).** Added 35 tests PORM-RR-01 … RR-35 for the new `validate_replacement_receipt` and schema `PurchaseOrderReturnReplacementCreate`, all strict xfail BUG-2810, in card order after the `sync_return_paid` section; new helpers `RRQ`, `RV`, `RTOO`, `NOTPART`, `replaced_l1`, `replace_rc` and reason `X2810`; header docstring names revision 3. The 146 existing tests are unchanged; no ID retired. Result now 104 passed · 77 xfailed. Reference plugin extended (181 passed with `--runxfail`). DISCREPANCY-1 logged (card wording of the RR "Fails today on" lines). Coverage unchanged at 100% (the new method does not exist yet).
- **2026-11-17 — cases revision 2.** First execution: 146 tests, 104 passed · 42 xfailed.
