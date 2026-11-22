# Execution notes — `app/services/item_summary_service.py`

> Cases: `tests/unit/services/item_summary_service.cases.md` (revision 4) · Tests: `tests/unit/services/test_item_summary_service.py` · Source commit: e48a092
> Result: 195 passed · 107 xfailed · 3 xpassed (non-strict, by design) · 0 discrepancies · 0 errors — branch coverage 99% (283 statements, 80 branches, 1 partial)
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_item_summary_service.py -q -p no:cacheprovider -o addopts="" --cov=app.services.item_summary_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows**: the autouse fixture `st` builds every Conventions standing row in Conventions order, one flush each (W0, W1, W2, U1, then W0's F0 S0 AC0 M0 WT0 L0 I0, W1's F1 F2 FD S1 AC1 AC2 M1 WT1 L1 I1 I2 IR, W2's F9 S9 AC9 M9 WT9 L9 I9). Card names are the attributes as the card writes them (`W1.id` → `st.W1.id`).
- **Given rows**: the `mk` fixture (`Builder`) has one method per Conventions builder (`po`, `pol`, `to`, `tol`, `so`, `sol`, `eo`, `wo`, `wol`, `stock`, `prod`, `place`, `mach`, `sec`, `assign`, `pf`, `pfl`, `batch`, `pbl`, `proj`, `comp`, `pcl`, `ient`, `pent`, `ment`, `tag`, `tagged`, `rev`, `revi`, `ret`, `reti`, `wf`). Keyword arguments are the card's "but" columns. `w="W2"` / `w="W0"` swaps the workspace and every standing W1 reference (F, S, AC, M, WT, L) for the counterpart; the item stays I1. Line numbers of `pol` / `tol` count the lines built before on the same order.
  - Closed states are properties spread with `**`: `voided`, `deleted_wo`, `deleted_line`, `deleted_machine`, `deleted_section`, `deleted_proj`, `deleted_account`, `deleted_stock`.
  - "`performed_at` not passed" (RA-22, DP-11) is `OMIT`: the builder leaves the column out so the database default fills it.
  - `sup(rows)` turns the cards' supplier tuples' text money into `Decimal` ("texts as Decimals"); `ids(snap)`, `accts(snap)` follow the section notes; `FMAP` / `MMAP` are fixtures.
- **TODAY / G(n)**: `today_g()` reads `date.today()` once per test (GS-09, GS-10, GS-11, GS-13, OQ31-05, OQ31-09, OQ32-17). Every other card passes TD.
- **Recorder** (`Recorder(db).start()` / `.stop()` in a `finally`): listens with `before_cursor_execute` on `db.connection()`. `selects(t)` = recorded statements starting with SELECT that contain `t`. Ids and arguments are read into locals before `start()`, so lazy attribute loads are not recorded.
  - SS-12: exactly one SELECT reads both `purchase_order_items` and `accounts`; it must contain `ORDER BY`.
  - US-12 / US-14: the text after `ORDER BY` of each SELECT reading the line table *with* `LIMIT` (the preview, not the count) must name `production_formulas.id` / `project_components.id`.
  - RA-11: the LIMIT value of the SELECT reading `inventory_ledger` is read from the text or, for `LIMIT %(name)s`, from the parameters (`limit_of`).
- **xfail markers**: `xf("BUG-…")` gives `xfail(strict=True, reason="BUG-NNN: <bugs.md title>")`; `strict=False` for the five `Author: claude` non-strict cards (SS-10, SS-11, US-10, US-11, US-13).
  - `raises=` pins the cause where the card says the call itself fails: `TypeError` for the 17 new-`workspace_id` cards (OL-21 … OL-30, ON-10 … ON-14, AL-04, AL-05; shared marker `BUG_2520_WS`) and RA-23; `AttributeError` for OQ31-10 (no `sales_revenue` field). For these the `# Then 1` comment stands before the call, which is where the card says it fails.
- **GS-14**: commit point = `db.commit()` (a savepoint release under the `db` fixture). It expires the standing objects; I2 is then edited and a Status added, both unflushed. GS-15 patches `db.query` and `db.execute` with one `RuntimeError` inside the spies.
- **RA-23 / RA-24**: the aware `performed_at` is kept on the flushed, unexpired machine-ledger object; the DAO read returns that identity-map object, so the value stays aware (checked by a setup `assert ... tzinfo is not None`, not a card check).
- **RA-22 / DP-11**: `SET LOCAL TIME ZONE 'Asia/Dhaka'` lasts for the test's transaction only.
- **ruff**: file-level `noqa: SIM117, C408` (nested `with` blocks; builder keyword dicts). `noqa: DTZ011` on the one `date.today()` and `noqa: RUF032` on DEC-04's `Decimal(0.1)` (the card compares against the binary value). `ruff --fix` turned `Decimal("0")`, `Decimal("3")`, `Decimal("5")` into `Decimal(0)`, `Decimal(3)`, `Decimal(5)`: same value and same `str`.
- Nothing is patched beyond the cards (spies, GS-15's failing `query` / `execute`). The spec lists no externals.

## Verification runs
- **3 plain runs** (revision 4): 195 passed, 107 xfailed, 3 xpassed in each of these runs. The count of xpassed can vary between runs: the non-strict tie cards SS-10 and SS-11 (unordered supplier query) may also xpass, giving 4 (seen in 1 of the verifier's 5 runs). The 3 that xpass every time are the non-strict collation cards US-10, US-11, US-13: the test database's collation already puts `"apex"` before `"Zeta"`, and the six equal formula names come back in id order. SS-10 and SS-11 (non-strict, unordered supplier query) xfailed in the plain runs; SS-10 xpassed once in a coverage run and in two per-fix runs (the order of the unordered query varies). That is why they are non-strict; no strict card varied.
- **`--runxfail`** (revision 4): 107 failed, 198 passed. Every strict xfail fails inside the Then line its card names (checked by `check_xfail.py` in scratch: it maps the failing line in the test file to the `# Then N` block and compares it with "Fails today on"). No mismatch. US-10, US-11, US-13 pass, as above.
- **Reference plugin** (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\is\is_ref.py`, loaded with `PYTHONPATH=<scratch> -p is_ref`; `IS_FIX` selects bugs, default all):
  - It replaces the service's methods in-process and covers BUG-2485 (`sales_revenue` on a stats subclass), 2486 (`terminal_status_ids_by_workflow`), 2487, 2520 (scoped joins and lookups; the resolvers get an *optional* `workspace_id`), 2521, 2522, 2523 (query `ORDER BY` plus Python tie keys), 2524, 2525, 2526 (`GROUP BY` inside the `LIMIT 5` previews), 2527, 2528 (links and numbers batched after the cut), 1339, and the DAO / model bugs 884, 1328, 1338, 981, 982, 977, 1326, 932, 640, and 2529 / 1337 (a Python `utcnow` default on both ledger times).
  - With all fixes and `--runxfail` (revision 4): **305 passed**.
  - **Per-fix check** (`per_fix.py` in scratch, one `--runxfail` run per `IS_FIX` value, 25 runs; repeated for revision 4 with the same counts): with no fix the plugin behaves as today (no pass card breaks; only the non-strict US-10, US-11, US-13 pass). Each of the 24 fixes on its own passes exactly its own cards and breaks no pass card. The only extras are the non-strict US-10, US-11, US-13 (every run) and SS-10 (randomly). Counts: 2520 → 38, 2522 → 13 (incl. the 3 non-strict), 2523 → 10, 2485 → 6, 2524 → 5, 2526 → 5, 2527 → 5, 2486 → 4, 2521 → 4, 2525 → 4, 2487 → 2, 981 → 2, and one each for 1339, 1338, 1328, 884, 982, 977, 1326, 932, 640, 1337, 2528, 2529.
- **Mutation check** (revision 4; scratch plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\lowsupe\is\is_mut.py`, `IS_MUT="<line>|<old>|<new>"` re-runs the mutated module source in the module's own namespace before collection; not `tests/unit/_tools/mutate.py`). The three survivors the revision names now fail, each on exactly one card:
  - #206, L429 `weight_total > 0` → `> 1`: 1 failed (PS-08), 194 passed.
  - #285, L653 `Decimal(999999999)` → `Decimal(1000000000)`: 1 failed (MF-07, `assert 1 == 2`), 194 passed.
  - #185, L587 `'last_price'` → `''`: 1 failed (SR-19, `KeyError: 'last_price'`), 194 passed.
- `ruff check`: clean. The file is LF only (0 CR bytes).
- Under `--cov` only, SQLAlchemy "GenericFunction already registered" `SAWarning`s appear (as in other files). Plain runs are clean.

## Discrepancies
None open. DISCREPANCY-1 (ISM-OQ31-11, a sales line with NULL `unit_price` / `line_total` cannot be inserted) was closed by cases revision 3, which retired the card.

## Coverage gaps
| Lines | Kind | What the code does there |
|---|---|---|
| 249->251 | unreachable | `if inv.qty > 0:` inside `_inventory_rows` is always true: rows with `qty <= 0` were skipped two lines above (spec Branch map: "`qty > 0` (always true here)"). |

## Factories added
None. The builders are local to this file.

## Notes for maintainers
- **Global unique numbers** (revision 3: now stored with the `GN(n)` per-process suffix, so parallel runs no longer clash; the text below describes revision 2): `sales_order_number`, `transfer_number` and `return_number` are unique across all workspaces, and the cards use fixed values (`SO-1`, `TO-1`, `RET-1`, …). Two runs of this file at the same moment, or another file using the same numbers, block on each other's uncommitted inserts until one rolls back. Do not run it in parallel with itself.
- Explicit ids `XID(k)` (OL-02, -03, -08, -09, -16 … -19) are per process id, so parallel processes do not collide.
- **When a BUG is fixed**, its strict cards XPASS (strict → fail); remove the marker. BUG-2520 → ML-05 … ML-07, IV-12, IV-13, PD-12, PD-13, MP-10, MP-11, SS-07, SS-08, US-24 … US-29, OL-21 … OL-30, ON-10 … ON-14, AL-04, AL-05, RA-17 … RA-20. BUG-2485 → OQ31-01 … OQ31-05, OQ31-10.
- **BUG-2520 signature**: the spec makes the resolvers' `workspace_id` *required*. Today's OL / ON / AL cards call without it, so the fix must add `workspace_id=W1.id` to those tests in the same change (cases Conventions). The reference plugin makes it optional so that both sets run.
- **BUG-2526 and US-12 / US-14**: the reference keeps the `LIMIT 5` in SQL and deduplicates with `GROUP BY`. A fix that drops the SQL `LIMIT` and deduplicates in Python leaves US-12 / US-14 with no matching statement, and they fail.
- Collation: US-10, US-11, US-13 pass today on this database (non-strict). They would fail under a `C` collation until BUG-2522 is fixed.

## Revision history
- **2026-11-10 — cases revision 2.** First implementation: 299 cases.
- **2026-11-10 — cases revision 3.** OQ31-11 retired (its test deleted; DISCREPANCY-1 closed). New Conventions helper `GN(n) = f"{n}-{os.getpid()}"`; the `mk.to`, `mk.so` and `mk.ret` builders store `GN(no)`, and ON-04, ON-05 and RA-06 now expect `GN("TO-1")` / `GN("SO-1")`. Unused `IntegrityError` import removed. Result 188 passed, 107 xfailed, 3 xpassed (US-10/11/13, non-strict) in each of 3 plain runs; `--runxfail` 107 failed, every one in its named Then line; reference plugin with all fixes and `--runxfail` 298 passed; per-fix check (25 runs) flips exactly each bug's own cards, BUG-2485 now 6 of 6, no pass card broken. Branch coverage 99% (gap 249->251 unchanged). ruff clean, LF only.
- **2026-11-10 — cases revision 4** (`item_summary_service.verify.md` findings 1–5, 7; spec R5b). PRC-07 gains Then 4 and 5 (the `days_30` / `days_90` min and max) and cites R1, R3. US-03 is rewritten to the new card: W0 and W2 formula, batch and project lines of I1 next to one W1 line of each (plus PF0X, a W0 formula line of I1), with all four counts and four previews checked. New pass tests PS-08, OS-13, PD-14, SR-19, SR-20, MF-07, MF-08, each after the last test of its group, in card order. MF-07 follows the spec's literal R1: "no average" ranks as 999999999, so 999999999.50 loses the count tie (coordinator decision, not a bug). PS-08 writes `Decimal(3)` for the card's `Decimal("3")` (ruff FURB157; same value). Result 195 passed, 107 xfailed, 3 xpassed (US-10/11/13, non-strict) in each of 3 plain runs; `--runxfail` 107 failed, 0 mismatches against the named Then lines; reference plugin with all fixes and `--runxfail` 305 passed; per-fix check unchanged, no pass card broken (new cards included). Mutants #206, #285 and #185 now fail (PS-08, MF-07, SR-19). Branch coverage 99% (gap 249->251 unchanged). ruff clean, LF only.
