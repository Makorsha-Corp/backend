# Execution notes — `app/services/calendar_service.py`

> Cases: `tests/unit/services/calendar_service.cases.md` (revision 6) · Tests: `tests/unit/services/test_calendar_service.py` · Source commit: e48a092
> Result: 105 passed · 23 xfailed · 0 discrepancies · 0 errors — branch coverage 100%
> Run: `COVERAGE_FILE=<private> .venv/Scripts/python.exe -m pytest tests/unit/services/test_calendar_service.py -q -p no:cacheprovider --cov=app.services.calendar_service --cov-branch --cov-report=term-missing`

## How the tests are built
- **Standing rows**: the autouse fixture `st` builds every Conventions standing row, in Conventions order with one flush each, for every test (the pure-helper tests included): W0, W1, W2 (so `W0.id < W1.id < W2.id`), U1, then W0's F0, WT0, AC0, S0, L0, M0, then W1's and W2's rows, then SOX, SOX9, INX, INX9, SOX0, INX0.
- **Given rows**: `mk` (a `Builder`) has one method per Conventions builder (`wo`, `po`, `eo`, `so`, `dl`, `inv`, `pay`, `batch`, `proj`, `log`). The number or name goes first.
  - `w2=True` gives "W2 x" and `w0=True` gives "W0 x". `Builder._v` picks the W1, W2 or W0 counterpart of each standing row.
  - Keyword arguments are the dates and the "but" columns. Every nullable date column the card does not name is passed explicitly as `None`.
  - Closed states are properties spread with `**`: `deleted_wo`, `voided_po` (also used for eo), `voided_inv`, `voided_pay`, `cancelled_batch`, `deleted_proj`, `gone_log`. "private proj" is `**mk.private`.
  - Access rows are `mk.member(u, role, status="active")` and `mk.project_member(p, u)`. Amounts are explicit two-place `Decimal`s.
- **Named checks**: `keys`, `recs`, `types_of` and `of(result, src)` follow Conventions. The **recorder** listens with `before_cursor_execute` on `db.connection()` and is removed right after the When. **spies** and **failing query** are written as Conventions say. The commit point is `db.commit()`, which only releases a savepoint under the `db` fixture.
- **`CC`**: a `SimpleNamespace` that maps each lower-case value to its `CalendarCategory` member, so a card's `CC.sales` reads as written and is `CalendarCategory.SALES` (the revision 3 Conventions note).
- **Parametrized cards** (same setup and asserts, one input differs): DR-01…06, WO-02/03, PO-03…05, SD-02/03, IN-07/08, PJ-02…04, OQ5-03/04. Each card ID is a param id. A check script confirms that all 124 IDs appear exactly once and that no test argument goes unused.
- **OQ5 cards (BUG-1869)**: they use the shared marker `BUG_1869 = xfail(strict=True, raises=TypeError, reason="BUG-1869")`. Today the When call itself raises `TypeError: get_events() got an unexpected keyword argument 'user_id'`, before Then 1 can be checked, which is what the cards' "Fails today on" says. `raises=TypeError` pins the xfail to that cause, so a setup error (for example a wrong member row) fails the run instead of hiding as an xfail.
- **`import app.db.base`** is not needed. The mappers configure from the imported models alone (checked with `configure_mappers()`).
- Nothing is patched beyond the Conventions (the spies and the failing `db.query` of GE-16). The spec lists no externals.

## Verification runs (revision 4)
- 3 plain runs, plus 1 run with `PGOPTIONS=-c enable_seqscan=off`: 105 passed, 19 xfailed in every run.
- `--runxfail`: all 19 strict xfails fail where their card says.
  - **Then 1 assertion:** GE-17…21 (empty list), OQ14-01 (V listed), OQ15-01 (X listed), OQ15-02 (X listed), PY-08 (X listed), PB-07 (X listed), PJ-10 (D listed), PJ-11 (X listed).
  - **The When call, before Then 1:** OQ5-01…07 raise the `TypeError` on the `user_id` keyword.
- **PB-08 / SD-07**: the batch `status` column (String(20), no CHECK constraint) accepts `"Cancelled"`, and so does the delivery `delivery_status` column. Both cards pass, so there is no discrepancy.
- **Reference plugin** (scratch `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc4e2\cal\cal_ref_fix.py`, patched in-process, `CAL_FIX` selects bugs):
  - BUG-1805: a maintenance collector in `get_events`.
  - BUG-1801: the payment's invoice must be in the same workspace.
  - BUG-1807: drops batches whose line's factory is deleted.
  - BUG-1800 and BUG-1806: drop deleted projects, and projects of a deleted factory.
  - BUG-1876: drops `VOIDED` work orders.
  - BUG-1877 and BUG-1878: drop work and sales orders of a deleted factory.
  - BUG-1869: `get_events(..., user_id=None)` filters private projects with `ProjectManager.can_access_project`, and a `None` caller sees no private project.
  - With all fixes and `--runxfail`: **124 passed**.
  - Each fix on its own flips exactly its own cards and breaks no pass card: 1800 → PJ-10; 1801 → PY-08; 1805 → GE-17…21; 1806 → PJ-11; 1807 → PB-07; 1869 → OQ5-01…07; 1876 → OQ14-01; 1877 → OQ15-01; 1878 → OQ15-02.
- `ruff check`: clean. The file is LF only (checked by byte count).
- Under `--cov` only, 15 SQLAlchemy "GenericFunction already registered" `SAWarning`s appear (also for other files). Plain runs are clean.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (123 statements, 44 branches). The `None` arms of the amount, priority and status conditional expressions are not counted as branches by coverage.py. The spec records them as unreachable (NOT NULL, G2–G4).

## Factories added
None. The calendar's builders are local.

## Notes for maintainers
- `sales_order_number` and `delivery_number` are unique across **all** workspaces, and the cards use fixed values (`SO-1`, `SD-1`, `SO-X`, `SO-X0`). Two runs of this file at the same moment block on each other's uncommitted inserts. Do not run it in parallel with itself.
- Collectors have no `ORDER BY`. The cards compare sorted keys, except for one record's own field order and the GE-10/12/13 sort.
- **When BUG-1869 is fixed** with a required `user_id`, every other `get_events` card gains `user_id=U1.id` and nothing else changes (cases Conventions). These are GE-01…16 and GE-17…21. U1 creates no private project, and no non-OQ5 card builds one. The fixed signature must keep `user_id` keyword-only, as the OQ5 cards pass it by name. Remove the `BUG_1869` marker then.
- When any other BUG is fixed, its cards XPASS (strict → fail). Remove the marker: BUG-1805 → GE-17…21; BUG-1801 → PY-08; BUG-1807 → PB-07; BUG-1800 → PJ-10; BUG-1806 → PJ-11; BUG-1876 → OQ14-01; BUG-1877 → OQ15-01; BUG-1878 → OQ15-02.
- For the permissions work: the reference 1869 fix reuses `ProjectManager.can_access_project`. That check covers the workspace owner (`owner_user_id`), an active member with role `owner` or `ground-team-manager`, the creator, and project members. An inactive privileged member is refused (OQ5-07) because `_is_privileged` requires `status == 'active'`. Calling it once per project event costs one query per check. A real fix should load the caller's grants once per request.

## Revision history
- **2026-11-04 — cases revision 2.** First implementation: 114 cases, 105 passed and 9 xfailed, 100% branch.
- **2026-11-04 — cases revision 4** (owner answers OQ-5, OQ-14 and OQ-15, plus verifier findings 1–4):
  - Standing W0, with its rows and SOX0/INX0, is built before W1.
  - A W0 row was added to WO-05, PO-07, EO-05, SO-04, SD-05, IN-05, PY-06, PB-05, PJ-07 and GE-20. PY-06 also gained a W2 payment on W1's invoice.
  - GE-12 and GE-13 gained a second, reversed tie pair (GE-13 renames I2 after Y2 exists, then flushes).
  - OQ5-01 was rewritten and OQ5-02…07 are new (xfail BUG-1869, `raises=TypeError`).
  - OQ14-01 is now xfail BUG-1876. OQ14-02 gained the in-progress order. OQ15-01 is xfail BUG-1877 and OQ15-02 is xfail BUG-1878.
  - New pass cards: WO-08, SO-06, SD-07, PB-08.
  - The reference plugin was extended with BUG-1869, 1876, 1877 and 1878.
  - Result: 124 cases, 105 passed, 19 xfailed, 100% branch, no discrepancy.
- **2026-11-04 — cases revision 5** (verifier Round 2):
  - R2-1: GE-12 and GE-13 give every tie-pair row an explicit id through `XID(k)`, a module function as in Conventions (`800_000_000 + (os.getpid() % 1_000_000) * 10 + k`). GE-13 now builds I2 with its final number `Payment #XID(8)`, so the rename step is gone.
  - Tie-break mutant (scratch `tiebreak.py`, in-process): adding `-record_id` to the sort key fails GE-12 and GE-13 and nothing else. Adding `+record_id` also fails exactly those two.
  - R2-2: OQ5-08…11 are new refused-caller cards, strict xfail BUG-1869 with `raises=TypeError`. Under `--runxfail` each raises the `user_id` `TypeError` at the When call. OQ5-11's grants in W2 and W0 are bare `WorkspaceMember` rows, as the card writes them.
  - Reference plugin (unchanged code; `ProjectManager.can_access_project` already scopes owner and role to the workspace asked): it refuses all four new callers. With all fixes and `--runxfail`, 128 passed; with 1869 alone, exactly the 11 OQ5 cards flip.
  - Result: 3 plain runs and 1 run with sequential scans off each gave 105 passed and 23 xfailed. Branch coverage is 100%. The 128 IDs each appear once. ruff is clean and the file is LF.
- **2026-11-04 — cases revision 6:**
  - OQ5-11 now flushes UX's W2 `owner` and W0 `ground-team-manager` memberships first and the W1 `ground-team` row last, so the W1 row has the highest id.
  - The GE-12 and GE-13 docstrings now carry the new card titles ("whichever id is larger").
  - Faulty-fix check: `CAL_1869_VARIANT=first_no_ws` in the reference plugin reads the caller's membership with `first()`, ordered by id and with no workspace filter. Under `--runxfail` it fails OQ5-11 only (1 failed, 127 passed). The correct reference gives 128 passed.
  - Result: 3 plain runs each gave 105 passed and 23 xfailed. The 128 IDs each appear once. ruff is clean and the file is LF.
