# Test cases — `app/dao/project_component_item_ledger.py`

> **Spec:** `tests/unit/dao/project_component_item_ledger.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-10, nothing open). P1–P4, Q2 and the 2026-11-10 intent rules (R1b, R2b, `get_by_performer` R3–R6) were decided by Claude under the reviewer's delegation; OQ-27 is the owner's answer (projects skipped until after launch, today's behaviour kept).
> **Revision:** 2 (2026-11-10) — spec apply-review + fill-gaps (Gap log G1–G4, OQ-27). OQ-27: no rule changed; the empty pending section is relabelled as answered. The 32 xfail cards of BUG-640, BUG-2462, BUG-2463, BUG-2464 and BUG-654 keep their design and now carry *revisit after launch* (Expect line and reason); BUG-645 and BUG-100 cards are not tagged, as the spec says. This file has no BUG-647 card (that bug's cards are the ledger manager's; DR-34, DR-35 still pin today's R3). G1: the `Decimal('0.00')` fallback cards stand unchanged. G2 → TC-24 … TC-29 (R1b: exact match; variants are added). G3 → PF-10 … PF-17 (R3–R6), and PF-09 now also cites R4. G4 → DR-46 … DR-51 (R2b: mixed bounds normalised one by one). No card retired.
> **Revision:** 3 (2026-11-10) — `project_component_item_ledger.verify.md` finding 1 (`case-missing`). PCIL-CI-22, CO-22, TT-22, DR-22, BAL-32, LE-26 gain a last Then line `"FOR UPDATE" not in sql` (no read takes a row lock); PF-17 replaces its vacuous `lock_part == ""` with the same check. Conventions gain "No-lock check" and "Clear the session before a one-query check". Counts unchanged; no ID retired.
> **Counts:** 259 cases · 208 expected-to-pass · 51 expected-to-fail (bugs) · 11 deferred

## Reviewer summary
- **Per callable:** `get_by_component_and_item` 32 (3 bug) · `get_by_component` 30 (3 bug) · `get_by_transaction_type` 39 (3 bug) · `get_by_date_range` 51 (11 bug) · `get_by_performer` 17 (17 bug) · `calculate_balance` 32 (2 bug) · `get_latest_entry` 26 (2 bug) · `calculate_total_cost_for_component` 29 (8 bug) · inherited `get_by_workspace` 3 (2 bug).
- **Depth:** full (skill step 1a): a stock and money ledger; balance, latest entry and total cost are the figures a component's cost will rest on.
- **Expected-to-fail:** BUG-640 (CI, CO) · BUG-2462 (TT, DR) · BUG-2463 (BAL, LE) · BUG-100 (INH): per query two non-strict tie cards for the lists, one for BAL / LE / INH, and exactly one strict statement-recorder alarm · BUG-2464 8 strict (aware and mixed bounds under New York / Dhaka) · BUG-654 8 strict (net cost) · BUG-645 17 strict (method missing; every call raises). 11 of the 51 are non-strict. **Revisit after launch** (owner, 2026-11-10): the 32 cards of BUG-640, 2462, 2463, 2464 and 654 keep failing today and are tagged; nothing else changes.
- **OQ-27 (answered 2026-11-10):** projects are skipped until after launch; today's behaviour is kept and no rule changed, so no card changed. No card asserts that nothing writes the table or that the total is always 0.00: every card builds its own rows.
- **Notable design choices:**
  - Today's order (`performed_at` newest first) is pinned by pass cards, including an older row with the highest id; ties are pinned as "between the newer and the older row". Only the id tie-break is xfail.
  - HR-15: this DAO rounds nothing, so the half-up cards check the database's own rounding of stored values through `calculate_balance` and the total (2.125, 0.005, -1.005 against the control 2.124; the three-row sum 4.26 differs from both half even, 4.24, and unrounded, 4.25).
  - BUG-654 pass cards use only added types, so they hold today and after the fix; every subtracted-type assertion is in an xfail card. R1b look-alikes (`Transfer_Out`, `DAMAGED`, a leading or a trailing space) are added today and after the fix, so TC-24 … TC-27 pass and catch a case- or space-insensitive fix; TC-28, TC-29 put each look-alike next to its real outgoing type.
  - R2b mixed bounds: four xfail cards (each mix under New York and under Dhaka, today's wrong result different in each) and two UTC controls that hold today and after the fix.
  - Isolation rows that reuse W1's component and item ids under W0 / W2 are deliberately invalid data (HR-16); they test the row's own `workspace_id` filter.
  - `get_by_date_range` ArgumentError cards pin today's R3, which the BUG-647 fix retires. No commit spy: nothing here writes. Race simulations: none.
- **Needs a decision:** None. Gaps 1–4 of revision 1 are closed by the spec's Gap log (2026-11-10).

## Conventions for this module

**IDs.** `PCIL` = `app/dao/project_component_item_ledger.py`. `CI` get_by_component_and_item · `CO` get_by_component · `TT` get_by_transaction_type · `DR` get_by_date_range · `PF` get_by_performer (to add) · `BAL` calculate_balance · `LE` get_latest_entry · `TC` calculate_total_cost_for_component · `INH` inherited `BaseDAO`. (`OQ27` is reserved and holds no card: OQ-27 is answered.)

**Actors and fixed values.**
- `dao` = `project_component_item_ledger_dao` (`from app.dao.project_component_item_ledger import project_component_item_ledger_dao`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `ProjectComponentItemLedger` = `app.models.project_component_item_ledger.ProjectComponentItemLedger`. `Factory`, `Project`, `ProjectComponent`, `Item` = `app.models.factory`, `.project`, `.project_component`, `.item`. `Decimal`, `datetime`, `timedelta`, `timezone`, `text`, `select`, `patch` = the usual ones. `DataError`, `ArgumentError` = `sqlalchemy.exc`; `InvalidRowCountInLimitClause`, `InvalidRowCountInResultOffsetClause` = `psycopg2.errors`.
- MISSING = `999999999`. TAG = `uuid4().hex[:8]`, made once per test.
- T1 … T5 = `datetime(2026, 1, 1, 9, 0, 0)` … `datetime(2026, 1, 1, 13, 0, 0)`, one hour apart, naive (UTC as stored). Z1130, Z1230 = `datetime(2026, 1, 1, 11, 30 / 12, 30, tzinfo=timezone.utc)`. P1730, P1830 = `datetime(2026, 1, 1, 17, 30 / 18, 30, tzinfo=timezone(timedelta(hours=6)))` (the same instants as Z1130, Z1230).
- HIGH_ID = `max(greatest project_component_item_ledger.id or 0, last_value of pg_get_serial_sequence('project_component_item_ledger', 'id')) + 1000001`, read when the row is built.

**Externals.** None. Nothing is mocked and no clock is patched; every Given row sets `performed_at`. (Shared names not used here: **clock(L, U)**, **Dhaka**, **commit spy**.)

**Standing rows** (every test, this order, each added and flushed; no Given line):
1. W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`. U1, U2, U3 = `make_profile(db)` three times.
2. F0, F1, F2 = `Factory(workspace_id=W.id, name="Plant " + TAG, abbreviation=...)` for W0 / W1 / W2, abbreviations `"P0"`, `"P1"`, `"P2"`.
3. PJ0 = `Project(workspace_id=W0.id, factory_id=F0.id, name="Zero", description="x")`; PJ1 = the same on W1 / F1, `name "Bridge A"`; PJD = the same as PJ1, but `name "Old bridge"`, `is_deleted True`, `deleted_at T1`, `deleted_by U1.id` (soft-deleted); PJ9 = the same on W2 / F2, `name "Nine"`.
4. Components `ProjectComponent(workspace_id=..., project_id=..., name=...)`, in this order: C0 (W0, PJ0, "Base"), CL (W1, PJ1, "Beam"), C1 (W1, PJ1, "Deck"), C2 (W1, PJ1, "Wall"), CD (W1, PJD, "Floor"), C9 (W2, PJ9, "Nine"). So `CL.id < C1.id < C2.id`.
5. Items `Item(workspace_id=..., name=..., name_normalized=<lower name>, unit="pcs")`, in this order: I0 (W0, "Pin"), IL (W1, "Washer"), I1 (W1, "Bolt"), I2 (W1, "Nut"), IR (W1, "Old gasket", `is_active False`), I9 (W2, "Rivet"). So `IL.id < I1.id < I2.id`.

**Given rows.** Inserted directly (never through `dao`), added and flushed one at a time in the order written, so sequence ids rise in that order. A line written as code is a step to run exactly, at that place. `db.add(...)` without flush leaves the row pending.
- ENTRY = `{"workspace_id": W1.id, "project_component_id": C1.id, "item_id": I1.id, "transaction_type": "transfer_in", "quantity": 1, "qty_before": 4, "qty_after": 5, "unit_cost": Decimal("2.00"), "total_cost": Decimal("2.00"), "source_type": "manual", "performed_by": U1.id}`.
- **entry** = `ProjectComponentItemLedger(**ENTRY, performed_at=...)`; every other column None, sequence `id`. The card always gives `performed_at`; after "but" it lists every column that differs from ENTRY (or sets `id`).
- No ledger row exists unless the card's Given lists it.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, order part of the check. **idset(result)** = `{r.id for r in result}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **nothing written** = the number of `project_component_item_ledger` rows (all workspaces) equals its value before the call.
- `pending:` lines check the session directly after the call, before anything expires it; they come before any `nothing written:` line.
- Money is compared as `Decimal` with `==`, never as strings, unless the line uses `str(...)`. A line that says `isinstance(..., Decimal)` checks the type too (`Decimal("0.00") == 0.0` is true in Python).
- `raises: DataError` = `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the When; later `raises:` lines assert on `exc.value` / `exc.value.orig`, one `assert` per line. `ArgumentError` = plain `with pytest.raises(ArgumentError) as exc:`, no savepoint (it would send SQL).
- **Statement recorder** = the SQL the session sends during the When is recorded (`before_cursor_execute`, as in `tests/unit/managers/test_ledger_manager.py`). `statements` = all of them; `sql` = the one `SELECT` from `project_component_item_ledger`; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `lock_part` = text after `FOR UPDATE` (`""`); `written` = every `INSERT`, `UPDATE`, `DELETE`.
- **No-lock check** = `"FOR UPDATE" not in sql`. Never use `lock_part == ""` for this: Postgres prints the lock clause last, so the text after `FOR UPDATE` is empty with a lock as well.
- **Clear the session before a one-query check**: a card that counts the SELECTs a call sends (or reads stored values back) ends its Given with `db.expunge_all()` (or `db.expire_all()` where the card says so), so a row the identity map still holds (a profile, a just-inserted value) cannot hide a second read. Ids used in Then come from objects built before it; their loaded attributes stay readable.
- A When written as one step with two calls (`latest, bal = ...`) is one step.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for cards comparing a tie order that rests on physical row order. `(revisit after launch)` (alone or after `non-strict, `) keeps the same strictness and sets `reason="BUG-n — revisit after launch (owner 2026-11-10)"`. Write the call and every check exactly as shown; never weaken one.

**Race simulations.** None.

## `ProjectComponentItemLedgerDAO.get_by_component_and_item`

### PCIL-CI-01 — returns ledger rows newest first, whatever the insertion order and the ids
- **Rules:** `get_by_component_and_item` R1, R3 (newest first; holds today), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T1`, but `id HIGH_ID` (the oldest row has the highest id).

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `all(isinstance(r, ProjectComponentItemLedger) for r in result)`.
3. returns: `ids(result) == [E2.id, E1.id, E3.id]`.

### PCIL-CI-02 — rows of W0 and W2 with the same component and item ids are not returned
- **Rules:** `get_by_component_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id` (same component and item ids, on purpose).
2. E1 = entry, `performed_at T1`.
3. X2 = entry, `performed_at T5`, but `workspace_id W2.id` (same component and item ids, on purpose).

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CI-03 — asked for W2, only the W2 row is returned, though W0 and W1 rows exist
- **Rules:** `get_by_component_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### PCIL-CI-04 — asked for W0, only the W0 row is returned
- **Rules:** `get_by_component_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T2`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T4`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W0.id)`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### PCIL-CI-05 — an unknown workspace id returns an empty list
- **Rules:** `get_by_component_and_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PCIL-CI-06 — skip 1 and limit 1 return exactly the middle row
- **Rules:** `get_by_component_and_item` R5, R3 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-CI-07 — skip 2 and limit 1 return the oldest row
- **Rules:** `get_by_component_and_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, skip=2, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CI-08 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_component_and_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### PCIL-CI-09 — limit 0 returns an empty list
- **Rules:** `get_by_component_and_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCIL-CI-10 — limit 1 returns only the newest row
- **Rules:** `get_by_component_and_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### PCIL-CI-11 — with the default limit, 101 rows give the 100 newest; the oldest is missing
- **Rules:** `get_by_component_and_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.
3. returns: `ids(result)[0] == rows[100].id`.

### PCIL-CI-12 — with the default limit, exactly 100 rows are all returned
- **Rules:** `get_by_component_and_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(100)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-CI-13 — limit 1000 returns all 101 rows: no upper cap
- **Rules:** `get_by_component_and_item` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-CI-14 — a negative limit makes the database reject the query
- **Rules:** `get_by_component_and_item` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. nothing written: nothing written.

### PCIL-CI-15 — a negative skip makes the database reject the query
- **Rules:** `get_by_component_and_item` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. nothing written: nothing written.

### PCIL-CI-16 — the workspace filter comes before the page: a newer W2 row takes no place
- **Rules:** `get_by_component_and_item` R5, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. X2 = entry, `performed_at T5`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-CI-17 — the filter comes before the page: a newer row of another item takes no place
- **Rules:** `get_by_component_and_item` R5, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. H = entry, `performed_at T5`, but `item_id I2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-CI-18 — tied rows are each returned once, between the newer and the older row
- **Rules:** `get_by_component_and_item` R3 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`.
5. A = entry, `performed_at T2`, but `qty_after 99`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### PCIL-CI-19 — on a tie the highest id comes first, when the lowest id was updated and other columns would sort otherwise
- **Rules:** `get_by_component_and_item` R3 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no second sort key; physical row order decides among tied rows)
- **Author:** claude

**Given**
1. B = entry, `performed_at T2`, but `performed_by U3.id`, `notes "Abe"`, `qty_after 15`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `notes "Mid"`, `qty_after 10`.
3. A = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Zed"`, `qty_after 99`.
4. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Abe two' WHERE id = :i"), {"i": B.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### PCIL-CI-20 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_component_and_item` R3 [BUG-640], R5
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no order among tied rows; a row can repeat and another be missed)
- **Author:** claude

**Given**
1. A = entry, `performed_at T2`, but `notes "Zed"`.
2. B = entry, `performed_at T2`, but `notes "Abe"`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `notes "Mid"`.
4. D = entry, `performed_at T2`, but `notes "Kay"`.
5. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Zed two' WHERE id = :i"), {"i": A.id})`, then `db.expire_all()`.

**When**
- `pages = [dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id, skip=k, limit=1) for k in range(4)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [C.id, D.id, B.id, A.id]`.

### PCIL-CI-21 — the query orders by performed_at newest first, then id highest first
- **Rules:** `get_by_component_and_item` R3 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (revisit after launch)
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"project_component_item_ledger.performed_at DESC" in order_part`.
4. statement: `"project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC" in order_part`.

### PCIL-CI-22 — writes nothing: a pending row stays pending and unseen, an unflushed edit stays unflushed, no parent is joined
- **Rules:** `get_by_component_and_item` Side effects, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. B = entry, `performed_at T2`.
3. `B.notes = "Edited"` (not flushed).
4. `P = ProjectComponentItemLedger(**ENTRY, performed_at=T4)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, E1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"JOIN" not in sql.upper()`.
9. nothing written: nothing written.
10. statement: `"FOR UPDATE" not in sql`.

### PCIL-CI-23 — rows of other items of the same component are not returned, the lower and the higher item id
- **Rules:** `get_by_component_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. EL = entry, `performed_at T4`, but `item_id IL.id`.
2. E1 = entry, `performed_at T1`.
3. EH = entry, `performed_at T5`, but `item_id I2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CI-24 — rows of the same item on other components are not returned, the lower and the higher component id
- **Rules:** `get_by_component_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. EL = entry, `performed_at T4`, but `project_component_id CL.id`.
2. E1 = entry, `performed_at T1`.
3. EH = entry, `performed_at T5`, but `project_component_id C2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CI-25 — asked for item I2, only the I2 row is returned
- **Rules:** `get_by_component_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. EL = entry, `performed_at T4`, but `item_id IL.id`.
2. E1 = entry, `performed_at T5`.
3. EH = entry, `performed_at T1`, but `item_id I2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [EH.id]`.

### PCIL-CI-26 — asked for component C2, only the C2 row is returned
- **Rules:** `get_by_component_and_item` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. EL = entry, `performed_at T4`, but `project_component_id CL.id`.
2. E1 = entry, `performed_at T5`.
3. EH = entry, `performed_at T1`, but `project_component_id C2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C2.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [EH.id]`.

### PCIL-CI-27 — every transaction type and performer of that component and item is returned
- **Rules:** `get_by_component_and_item` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.
3. E3 = entry, `performed_at T3`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

### PCIL-CI-28 — an unknown component id returns an empty list
- **Rules:** `get_by_component_and_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=MISSING, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-CI-29 — item_id 0 is an id that matches nothing
- **Rules:** `get_by_component_and_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-CI-30 — a component and item of another workspace, asked under W1, return an empty list
- **Rules:** `get_by_component_and_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X2 = entry, `performed_at T2`, but `workspace_id W2.id`, `project_component_id C9.id`, `item_id I9.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C9.id, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-CI-31 — a row of a component of a soft-deleted project is returned
- **Rules:** `get_by_component_and_item` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `project_component_id CD.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=CD.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CI-32 — a row of an inactive item is returned
- **Rules:** `get_by_component_and_item` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_by_component_and_item(db, project_component_id=C1.id, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

## `ProjectComponentItemLedgerDAO.get_by_component`

### PCIL-CO-01 — returns ledger rows newest first, whatever the insertion order and the ids
- **Rules:** `get_by_component` R1, R2, R3 (newest first; holds today), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T1`, but `id HIGH_ID` (the oldest row has the highest id).

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `all(isinstance(r, ProjectComponentItemLedger) for r in result)`.
3. returns: `ids(result) == [E2.id, E1.id, E3.id]`.

### PCIL-CO-02 — rows of W0 and W2 with the same component and item ids are not returned
- **Rules:** `get_by_component` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id` (same component and item ids, on purpose).
2. E1 = entry, `performed_at T1`.
3. X2 = entry, `performed_at T5`, but `workspace_id W2.id` (same component and item ids, on purpose).

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CO-03 — asked for W2, only the W2 row is returned, though W0 and W1 rows exist
- **Rules:** `get_by_component` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### PCIL-CO-04 — asked for W0, only the W0 row is returned
- **Rules:** `get_by_component` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T2`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T4`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W0.id)`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### PCIL-CO-05 — an unknown workspace id returns an empty list
- **Rules:** `get_by_component` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PCIL-CO-06 — skip 1 and limit 1 return exactly the middle row
- **Rules:** `get_by_component` R5, R3 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-CO-07 — skip 2 and limit 1 return the oldest row
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=2, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CO-08 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### PCIL-CO-09 — limit 0 returns an empty list
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCIL-CO-10 — limit 1 returns only the newest row
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### PCIL-CO-11 — with the default limit, 101 rows give the 100 newest; the oldest is missing
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.
3. returns: `ids(result)[0] == rows[100].id`.

### PCIL-CO-12 — with the default limit, exactly 100 rows are all returned
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(100)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-CO-13 — limit 1000 returns all 101 rows: no upper cap
- **Rules:** `get_by_component` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-CO-14 — a negative limit makes the database reject the query
- **Rules:** `get_by_component` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. nothing written: nothing written.

### PCIL-CO-15 — a negative skip makes the database reject the query
- **Rules:** `get_by_component` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. nothing written: nothing written.

### PCIL-CO-16 — the workspace filter comes before the page: a newer W2 row takes no place
- **Rules:** `get_by_component` R5, R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. X2 = entry, `performed_at T5`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-CO-17 — the filter comes before the page: a newer row of another component takes no place
- **Rules:** `get_by_component` R5, R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. H = entry, `performed_at T5`, but `project_component_id C2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-CO-18 — tied rows are each returned once, between the newer and the older row
- **Rules:** `get_by_component` R3 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`.
5. A = entry, `performed_at T2`, but `qty_after 99`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### PCIL-CO-19 — on a tie the highest id comes first, when the lowest id was updated and other columns would sort otherwise
- **Rules:** `get_by_component` R3 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no second sort key; physical row order decides among tied rows)
- **Author:** claude

**Given**
1. B = entry, `performed_at T2`, but `performed_by U3.id`, `notes "Abe"`, `qty_after 15`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `notes "Mid"`, `qty_after 10`.
3. A = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Zed"`, `qty_after 99`.
4. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Abe two' WHERE id = :i"), {"i": B.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### PCIL-CO-20 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_component` R3 [BUG-640], R5
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no order among tied rows; a row can repeat and another be missed)
- **Author:** claude

**Given**
1. A = entry, `performed_at T2`, but `notes "Zed"`.
2. B = entry, `performed_at T2`, but `notes "Abe"`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `notes "Mid"`.
4. D = entry, `performed_at T2`, but `notes "Kay"`.
5. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Zed two' WHERE id = :i"), {"i": A.id})`, then `db.expire_all()`.

**When**
- `pages = [dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id, skip=k, limit=1) for k in range(4)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [C.id, D.id, B.id, A.id]`.

### PCIL-CO-21 — the query orders by performed_at newest first, then id highest first
- **Rules:** `get_by_component` R3 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (revisit after launch)
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"project_component_item_ledger.performed_at DESC" in order_part`.
4. statement: `"project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC" in order_part`.

### PCIL-CO-22 — writes nothing: a pending row stays pending and unseen, an unflushed edit stays unflushed, no parent is joined
- **Rules:** `get_by_component` Side effects, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. B = entry, `performed_at T2`.
3. `B.notes = "Edited"` (not flushed).
4. `P = ProjectComponentItemLedger(**ENTRY, performed_at=T4)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, E1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"JOIN" not in sql.upper()`.
9. nothing written: nothing written.
10. statement: `"FOR UPDATE" not in sql`.

### PCIL-CO-23 — rows of every item, type and performer of the component are returned
- **Rules:** `get_by_component` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id I2.id`.
3. E3 = entry, `performed_at T3`, but `item_id IL.id`, `transaction_type "damaged"`, `performed_by U2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

### PCIL-CO-24 — rows of other components are not returned, the lower and the higher component id
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. EL = entry, `performed_at T4`, but `project_component_id CL.id`.
2. E1 = entry, `performed_at T1`.
3. EH = entry, `performed_at T5`, but `project_component_id C2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-CO-25 — asked for component C2, only the C2 row is returned
- **Rules:** `get_by_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. EL = entry, `performed_at T4`, but `project_component_id CL.id`.
2. E1 = entry, `performed_at T5`.
3. EH = entry, `performed_at T1`, but `project_component_id C2.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [EH.id]`.

### PCIL-CO-26 — another workspace's component id, asked under W1, returns an empty list
- **Rules:** `get_by_component` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X2 = entry, `performed_at T2`, but `workspace_id W2.id`, `project_component_id C9.id`, `item_id I9.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-CO-27 — an unknown component id returns an empty list
- **Rules:** `get_by_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-CO-28 — project_component_id 0 is an id that matches nothing
- **Rules:** `get_by_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_component(db, project_component_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-CO-29 — rows of a component of a soft-deleted project are returned
- **Rules:** `get_by_component` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `project_component_id CD.id`.
2. E2 = entry, `performed_at T2`, but `project_component_id CD.id`, `item_id IR.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=CD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

### PCIL-CO-30 — a row of an inactive item is returned
- **Rules:** `get_by_component` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `item_id IR.id`.

**When**
- `result = dao.get_by_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id]`.

## `ProjectComponentItemLedgerDAO.get_by_transaction_type`

### PCIL-TT-01 — returns ledger rows newest first, whatever the insertion order and the ids
- **Rules:** `get_by_transaction_type` R1, R2, R3 (newest first; holds today), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T1`, but `id HIGH_ID` (the oldest row has the highest id).

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `all(isinstance(r, ProjectComponentItemLedger) for r in result)`.
3. returns: `ids(result) == [E2.id, E1.id, E3.id]`.

### PCIL-TT-02 — rows of W0 and W2 with the same component and item ids are not returned
- **Rules:** `get_by_transaction_type` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id` (same component and item ids, on purpose).
2. E1 = entry, `performed_at T1`.
3. X2 = entry, `performed_at T5`, but `workspace_id W2.id` (same component and item ids, on purpose).

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-TT-03 — asked for W2, only the W2 row is returned, though W0 and W1 rows exist
- **Rules:** `get_by_transaction_type` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### PCIL-TT-04 — asked for W0, only the W0 row is returned
- **Rules:** `get_by_transaction_type` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T2`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T4`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W0.id)`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### PCIL-TT-05 — an unknown workspace id returns an empty list
- **Rules:** `get_by_transaction_type` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-06 — skip 1 and limit 1 return exactly the middle row
- **Rules:** `get_by_transaction_type` R5, R3 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-TT-07 — skip 2 and limit 1 return the oldest row
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, skip=2, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-TT-08 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-09 — limit 0 returns an empty list
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-10 — limit 1 returns only the newest row
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### PCIL-TT-11 — with the default limit, 101 rows give the 100 newest; the oldest is missing
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.
3. returns: `ids(result)[0] == rows[100].id`.

### PCIL-TT-12 — with the default limit, exactly 100 rows are all returned
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(100)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-TT-13 — limit 1000 returns all 101 rows: no upper cap
- **Rules:** `get_by_transaction_type` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-TT-14 — a negative limit makes the database reject the query
- **Rules:** `get_by_transaction_type` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. nothing written: nothing written.

### PCIL-TT-15 — a negative skip makes the database reject the query
- **Rules:** `get_by_transaction_type` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. nothing written: nothing written.

### PCIL-TT-16 — the workspace filter comes before the page: a newer W2 row takes no place
- **Rules:** `get_by_transaction_type` R5, R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. X2 = entry, `performed_at T5`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-TT-17 — the filter comes before the page: a newer row of another type takes no place
- **Rules:** `get_by_transaction_type` R5, R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. H = entry, `performed_at T5`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-TT-18 — tied rows are each returned once, between the newer and the older row
- **Rules:** `get_by_transaction_type` R3 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`.
5. A = entry, `performed_at T2`, but `qty_after 99`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### PCIL-TT-19 — on a tie the highest id comes first, when the lowest id was updated and other columns would sort otherwise
- **Rules:** `get_by_transaction_type` R3 [BUG-2462]
- **Kind:** bug
- **Expect:** xfail BUG-2462 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no second sort key; physical row order decides among tied rows)
- **Author:** claude

**Given**
1. B = entry, `performed_at T2`, but `performed_by U3.id`, `notes "Abe"`, `qty_after 15`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `notes "Mid"`, `qty_after 10`.
3. A = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Zed"`, `qty_after 99`.
4. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Abe two' WHERE id = :i"), {"i": B.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### PCIL-TT-20 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_transaction_type` R3 [BUG-2462], R5
- **Kind:** bug
- **Expect:** xfail BUG-2462 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no order among tied rows; a row can repeat and another be missed)
- **Author:** claude

**Given**
1. A = entry, `performed_at T2`, but `notes "Zed"`.
2. B = entry, `performed_at T2`, but `notes "Abe"`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `notes "Mid"`.
4. D = entry, `performed_at T2`, but `notes "Kay"`.
5. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Zed two' WHERE id = :i"), {"i": A.id})`, then `db.expire_all()`.

**When**
- `pages = [dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id, skip=k, limit=1) for k in range(4)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [C.id, D.id, B.id, A.id]`.

### PCIL-TT-21 — the query orders by performed_at newest first, then id highest first
- **Rules:** `get_by_transaction_type` R3 [BUG-2462]
- **Kind:** bug
- **Expect:** xfail BUG-2462 (revisit after launch)
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"project_component_item_ledger.performed_at DESC" in order_part`.
4. statement: `"project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC" in order_part`.

### PCIL-TT-22 — writes nothing: a pending row stays pending and unseen, an unflushed edit stays unflushed, no parent is joined
- **Rules:** `get_by_transaction_type` Side effects, R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. B = entry, `performed_at T2`.
3. `B.notes = "Edited"` (not flushed).
4. `P = ProjectComponentItemLedger(**ENTRY, performed_at=T4)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, E1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"JOIN" not in sql.upper()`.
9. nothing written: nothing written.
10. statement: `"FOR UPDATE" not in sql`.

### PCIL-TT-23 — a look-alike type is not returned
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-TT-24 — asked for transfer_out, only that row is returned
- **Rules:** `get_by_transaction_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_out", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-TT-25 — the argument "Transfer_In" (different case) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="Transfer_In", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-26 — the argument "TRANSFER_IN" (capitals) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="TRANSFER_IN", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-27 — the argument "transfer" (a part of the value) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-28 — the argument "transfer%" (a `%` pattern) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer%", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-29 — the argument "transfer_i_" (`_` used as a wildcard) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_i_", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-30 — the argument " transfer_in" (a leading space) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type=" transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-31 — the argument "transfer_in " (a trailing space) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in ", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-32 — the argument "" (the empty string) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-33 — the argument None (None) matches nothing
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type=None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-TT-34 — a stored type "Transfer_In" (a different case) is not matched by transfer_in
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "Transfer_In"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-TT-35 — a stored type " transfer_in" (a leading space) is not matched by transfer_in
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type " transfer_in"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-TT-36 — a stored type "transferXin" (another character where the argument has `_`) is not matched by transfer_in
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transferXin"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-TT-37 — a stored type "transfer_in_extra" (the argument as a part of it) is not matched by transfer_in
- **Rules:** `get_by_transaction_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_in_extra"`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-TT-38 — rows of every component, item and performer of the workspace are returned
- **Rules:** `get_by_transaction_type` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `project_component_id C2.id`.
3. E3 = entry, `performed_at T3`, but `item_id I2.id`.
4. E4 = entry, `performed_at T4`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E4.id, E3.id, E2.id, E1.id]`.

### PCIL-TT-39 — rows of a soft-deleted project's component and of an inactive item are returned
- **Rules:** `get_by_transaction_type` R4 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `project_component_id CD.id`.
2. E2 = entry, `performed_at T2`, but `item_id IR.id`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_transaction_type(db, transaction_type="transfer_in", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

## `ProjectComponentItemLedgerDAO.get_by_date_range`

### PCIL-DR-01 — returns ledger rows newest first, whatever the insertion order and the ids
- **Rules:** `get_by_date_range` R1, R5, R4 (newest first; holds today), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T1`, but `id HIGH_ID` (the oldest row has the highest id).

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `all(isinstance(r, ProjectComponentItemLedger) for r in result)`.
3. returns: `ids(result) == [E2.id, E1.id, E3.id]`.

### PCIL-DR-02 — rows of W0 and W2 with the same component and item ids are not returned
- **Rules:** `get_by_date_range` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id` (same component and item ids, on purpose).
2. E1 = entry, `performed_at T1`.
3. X2 = entry, `performed_at T5`, but `workspace_id W2.id` (same component and item ids, on purpose).

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-03 — asked for W2, only the W2 row is returned, though W0 and W1 rows exist
- **Rules:** `get_by_date_range` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W2.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### PCIL-DR-04 — asked for W0, only the W0 row is returned
- **Rules:** `get_by_date_range` R1, R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T2`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T5`.
3. X2 = entry, `performed_at T4`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W0.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [X0.id]`.

### PCIL-DR-05 — an unknown workspace id returns an empty list
- **Rules:** `get_by_date_range` R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=MISSING, start_date=T1, end_date=T5)`.

**Then**
1. returns: `result == []`.

### PCIL-DR-06 — skip 1 and limit 1 return exactly the middle row
- **Rules:** `get_by_date_range` R6, R4 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-07 — skip 2 and limit 1 return the oldest row
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=2, limit=1)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-08 — skip equal to the number of rows returns an empty list
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=3)`.

**Then**
1. returns: `result == []`.

### PCIL-DR-09 — limit 0 returns an empty list
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=0)`.

**Then**
1. returns: `result == []`.

### PCIL-DR-10 — limit 1 returns only the newest row
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E3 = entry, `performed_at T3`.
3. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=1)`.

**Then**
1. returns: `ids(result) == [E3.id]`.

### PCIL-DR-11 — with the default limit, 101 rows give the 100 newest; the oldest is missing
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.
3. returns: `ids(result)[0] == rows[100].id`.

### PCIL-DR-12 — with the default limit, exactly 100 rows are all returned
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(100)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-DR-13 — limit 1000 returns all 101 rows: no upper cap
- **Rules:** `get_by_date_range` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `rows = [ProjectComponentItemLedger(**ENTRY, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result)[-1] == rows[0].id`.

### PCIL-DR-14 — a negative limit makes the database reject the query
- **Rules:** `get_by_date_range` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
3. raises: `exc.value.orig.pgcode == "2201W"`.
4. nothing written: nothing written.

### PCIL-DR-15 — a negative skip makes the database reject the query
- **Rules:** `get_by_date_range` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
3. raises: `exc.value.orig.pgcode == "2201X"`.
4. nothing written: nothing written.

### PCIL-DR-16 — the workspace filter comes before the page: a newer W2 row takes no place
- **Rules:** `get_by_date_range` R6, R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. X2 = entry, `performed_at T5`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-17 — the filter comes before the page: a newer row of a time just after the end bound takes no place
- **Rules:** `get_by_date_range` R6, R1, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.
4. H = entry, `performed_at T5 + timedelta(microseconds=1)`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-18 — tied rows are each returned once, between the newer and the older row
- **Rules:** `get_by_date_range` R4 (newest first; holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. N = entry, `performed_at T3`.
3. B = entry, `performed_at T2`, but `qty_after 15`.
4. C = entry, `performed_at T2`, but `id HIGH_ID`, `qty_after 10`.
5. A = entry, `performed_at T2`, but `qty_after 99`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `result[0].id == N.id`.
3. returns: `result[-1].id == O.id`.
4. returns: `sorted(ids(result)[1:4]) == sorted([B.id, C.id, A.id])`.

### PCIL-DR-19 — on a tie the highest id comes first, when the lowest id was updated and other columns would sort otherwise
- **Rules:** `get_by_date_range` R4 [BUG-2462]
- **Kind:** bug
- **Expect:** xfail BUG-2462 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no second sort key; physical row order decides among tied rows)
- **Author:** claude

**Given**
1. B = entry, `performed_at T2`, but `performed_by U3.id`, `notes "Abe"`, `qty_after 15`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `notes "Mid"`, `qty_after 10`.
3. A = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Zed"`, `qty_after 99`.
4. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Abe two' WHERE id = :i"), {"i": B.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `sorted(ids(result)) == sorted([B.id, C.id, A.id])`.
2. returns: `ids(result) == [C.id, A.id, B.id]`.

### PCIL-DR-20 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_date_range` R4 [BUG-2462], R6
- **Kind:** bug
- **Expect:** xfail BUG-2462 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no order among tied rows; a row can repeat and another be missed)
- **Author:** claude

**Given**
1. A = entry, `performed_at T2`, but `notes "Zed"`.
2. B = entry, `performed_at T2`, but `notes "Abe"`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `notes "Mid"`.
4. D = entry, `performed_at T2`, but `notes "Kay"`.
5. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Zed two' WHERE id = :i"), {"i": A.id})`, then `db.expire_all()`.

**When**
- `pages = [dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5, skip=k, limit=1) for k in range(4)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [C.id, D.id, B.id, A.id]`.

### PCIL-DR-21 — the query orders by performed_at newest first, then id highest first
- **Rules:** `get_by_date_range` R4 [BUG-2462]
- **Kind:** bug
- **Expect:** xfail BUG-2462 (revisit after launch)
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"project_component_item_ledger.performed_at DESC" in order_part`.
4. statement: `"project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC" in order_part`.

### PCIL-DR-22 — writes nothing: a pending row stays pending and unseen, an unflushed edit stays unflushed, no parent is joined
- **Rules:** `get_by_date_range` Side effects, R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. B = entry, `performed_at T2`.
3. `B.notes = "Edited"` (not flushed).
4. `P = ProjectComponentItemLedger(**ENTRY, performed_at=T4)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [B.id, E1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"JOIN" not in sql.upper()`.
9. nothing written: nothing written.
10. statement: `"FOR UPDATE" not in sql`.

### PCIL-DR-23 — both bounds are inclusive: T1 to T3 returns all three rows
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T3)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

### PCIL-DR-24 — bounds one microsecond inside keep only the middle row
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1 + timedelta(microseconds=1), end_date=T3 - timedelta(microseconds=1))`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-25 — a start exactly at the row keeps it
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T2, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-26 — a start one microsecond after the row leaves it out
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T2 + timedelta(microseconds=1), end_date=T5)`.

**Then**
1. returns: `result == []`.

### PCIL-DR-27 — an end exactly at the row keeps it
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T2)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-28 — an end one microsecond before the row leaves it out
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T2 - timedelta(microseconds=1))`.

**Then**
1. returns: `result == []`.

### PCIL-DR-29 — equal bounds at the row's instant return that row
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T2, end_date=T2)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-30 — a midnight-to-midnight range of the same day misses that day's row
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 0, 0, 0), end_date=datetime(2026, 1, 1, 0, 0, 0))`.

**Then**
1. returns: `result == []`.

### PCIL-DR-31 — an end at the last microsecond of the day keeps that day's row
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E2 = entry, `performed_at T2`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 0, 0, 0), end_date=datetime(2026, 1, 1, 23, 59, 59, 999999))`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-DR-32 — a reversed range returns an empty list and raises nothing
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T3, end_date=T1)`.

**Then**
1. returns: `result == []`.

### PCIL-DR-33 — rows of every component, item, type and performer inside the window are returned
- **Rules:** `get_by_date_range` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`, but `project_component_id C2.id`.
3. E3 = entry, `performed_at T3`, but `item_id I2.id`.
4. E4 = entry, `performed_at T4`, but `transaction_type "damaged"`, `performed_by U2.id`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E4.id, E3.id, E2.id, E1.id]`.

### PCIL-DR-34 — start_date None raises ArgumentError before any query is sent
- **Rules:** `get_by_date_range` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=None, end_date=T3)`, inside `with pytest.raises(ArgumentError) as exc:`.

**Then**
1. raises: `ArgumentError`.
2. statement: `statements == []`.
3. nothing written: nothing written.

### PCIL-DR-35 — end_date None raises ArgumentError before any query is sent
- **Rules:** `get_by_date_range` R3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=None)`, inside `with pytest.raises(ArgumentError) as exc:`.

**Then**
1. raises: `ArgumentError`.
2. statement: `statements == []`.
3. nothing written: nothing written.

### PCIL-DR-36 — naive bounds are compared to the stored value as given, under the session zone America/New_York
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30), end_date=datetime(2026, 1, 1, 12, 30))`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-37 — naive bounds are compared to the stored value as given, under the session zone Asia/Dhaka
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30), end_date=datetime(2026, 1, 1, 12, 30))`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-38 — aware UTC bounds find the row inside the UTC window under the session zone America/New_York
- **Rules:** `get_by_date_range` R2a [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (the stored value is read in the session zone America/New_York, so `result == []`)

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-39 — aware UTC bounds find the row inside the UTC window under the session zone Asia/Dhaka
- **Rules:** `get_by_date_range` R2a [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (the stored value is read in the session zone Asia/Dhaka, so `result == []`)

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-40 — aware bounds with a +06:00 offset find the row under the session zone America/New_York
- **Rules:** `get_by_date_range` R2a [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (the stored value is read in the session zone, so `result == []`)

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=P1730, end_date=P1830)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-41 — aware UTC bounds keep only the row in the UTC window under the session zone Asia/Dhaka
- **Rules:** `get_by_date_range` R2a [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (today E2 is returned instead of E1)

**Given**
1. E1 = entry, `performed_at T4`.
2. E2 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)` (12:00 UTC when read as Dhaka time).
3. `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-42 — control: aware UTC bounds find the row under the session zone UTC
- **Rules:** `get_by_date_range` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TimeZone = 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-43 — control: aware bounds with an offset are converted, not cut off, under the session zone UTC
- **Rules:** `get_by_date_range` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. `db.execute(text("SET LOCAL TimeZone = 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=P1730, end_date=P1830)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-44 — control: aware UTC bounds leave out a row outside the window under the session zone UTC
- **Rules:** `get_by_date_range` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T4`.
2. E2 = entry, `performed_at T5`.
3. `db.execute(text("SET LOCAL TimeZone = 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-DR-45 — rows of a soft-deleted project's component and of an inactive item are returned
- **Rules:** `get_by_date_range` R5 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `project_component_id CD.id`.
2. E2 = entry, `performed_at T2`, but `item_id IR.id`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=T1, end_date=T5)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

### PCIL-DR-46 — an aware start and a naive end are each normalised on their own, under America/New_York
- **Rules:** `get_by_date_range` R2b [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (the aware start is read in the session zone, so the 07:00 row comes back too: `[E12.id, E07.id]`)

**Given**
1. E07 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E12 = entry, `performed_at datetime(2026, 1, 1, 12, 0, 0)`.
3. E18 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=datetime(2026, 1, 1, 12, 30, 0))`.

**Then**
1. returns: `ids(result) == [E12.id]`.

### PCIL-DR-47 — a naive start and an aware end are each normalised on their own, under Asia/Dhaka
- **Rules:** `get_by_date_range` R2b [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (the aware end is read in the session zone, so the 18:00 row comes back too: `[E18.id, E12.id]`)

**Given**
1. E07 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E12 = entry, `performed_at datetime(2026, 1, 1, 12, 0, 0)`.
3. E18 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30, 0), end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E12.id]`.

### PCIL-DR-48 — a naive start and an aware end, under America/New_York
- **Rules:** `get_by_date_range` R2b [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (the aware end is read in the session zone, which leaves no row: `[]`)

**Given**
1. E07 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E12 = entry, `performed_at datetime(2026, 1, 1, 12, 0, 0)`.
3. E18 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TimeZone = 'America/New_York'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30, 0), end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E12.id]`.

### PCIL-DR-49 — an aware start and a naive end, under Asia/Dhaka
- **Rules:** `get_by_date_range` R2b [BUG-2464]
- **Kind:** bug
- **Expect:** xfail BUG-2464 (revisit after launch)
- **Fails today on:** Then 1 (the aware start is read in the session zone, which leaves no row: `[]`)

**Given**
1. E07 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E12 = entry, `performed_at datetime(2026, 1, 1, 12, 0, 0)`.
3. E18 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=datetime(2026, 1, 1, 12, 30, 0))`.

**Then**
1. returns: `ids(result) == [E12.id]`.

### PCIL-DR-50 — control: an aware start and a naive end under UTC run the query and keep only the row inside
- **Rules:** `get_by_date_range` R2b (holds today and after the fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E07 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E12 = entry, `performed_at datetime(2026, 1, 1, 12, 0, 0)`.
3. E18 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TimeZone = 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=Z1130, end_date=datetime(2026, 1, 1, 12, 30, 0))`.

**Then**
1. returns: `ids(result) == [E12.id]`.

### PCIL-DR-51 — control: a naive start and an aware end under UTC run the query and keep only the row inside
- **Rules:** `get_by_date_range` R2b (holds today and after the fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E07 = entry, `performed_at datetime(2026, 1, 1, 7, 0, 0)`.
2. E12 = entry, `performed_at datetime(2026, 1, 1, 12, 0, 0)`.
3. E18 = entry, `performed_at datetime(2026, 1, 1, 18, 0, 0)`.
4. `db.execute(text("SET LOCAL TimeZone = 'UTC'"))`

**When**
- `result = dao.get_by_date_range(db, workspace_id=W1.id, start_date=datetime(2026, 1, 1, 11, 30, 0), end_date=Z1230)`.

**Then**
1. returns: `ids(result) == [E12.id]`.

## `ProjectComponentItemLedgerDAO.get_by_performer` (to add, BUG-645)

### PCIL-PF-01 — rows of every component, item and type of that user are returned, newest first
- **Rules:** `get_by_performer` R1 [BUG-645], R2 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T2`, but `performed_by U2.id`.
2. E2 = entry, `performed_at T3`, but `performed_by U2.id`, `project_component_id C2.id`.
3. E3 = entry, `performed_at T1`, but `id HIGH_ID`, `performed_by U2.id`, `item_id I2.id`, `transaction_type "damaged"`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E2.id, E1.id, E3.id]`.

### PCIL-PF-02 — rows of the lower and the higher profile id are not returned
- **Rules:** `get_by_performer` R1 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. EL = entry, `performed_at T4`, but `performed_by U1.id`.
2. E1 = entry, `performed_at T1`, but `performed_by U2.id`.
3. EH = entry, `performed_at T5`, but `performed_by U3.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-PF-03 — the same user's rows in W0 and W2 are not returned
- **Rules:** `get_by_performer` R1 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id`, `performed_by U2.id`.
2. E1 = entry, `performed_at T1`, but `performed_by U2.id`.
3. X2 = entry, `performed_at T5`, but `workspace_id W2.id`, `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.

### PCIL-PF-04 — asked for W2, only the W2 row is returned
- **Rules:** `get_by_performer` R1 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. X0 = entry, `performed_at T4`, but `workspace_id W0.id`, `performed_by U2.id`.
2. E1 = entry, `performed_at T5`, but `performed_by U2.id`.
3. X2 = entry, `performed_at T1`, but `workspace_id W2.id`, `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [X2.id]`.

### PCIL-PF-05 — on a tie the highest id comes first
- **Rules:** `get_by_performer` R2 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. B = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Abe"`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U2.id`, `notes "Mid"`.
3. A = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Zed"`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, A.id, B.id]`.

### PCIL-PF-06 — skip 1 and limit 1 return the middle row; another user's newer row takes no place
- **Rules:** `get_by_performer` R2 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.
2. E2 = entry, `performed_at T2`, but `performed_by U2.id`.
3. E3 = entry, `performed_at T3`, but `performed_by U2.id`.
4. H = entry, `performed_at T5`, but `performed_by U1.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [E2.id]`.

### PCIL-PF-07 — with the default limit, 101 rows give the 100 newest
- **Rules:** `get_by_performer` R2 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. `rows = [ProjectComponentItemLedger(**{**ENTRY, "performed_by": U2.id}, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `rows[0].id not in ids(result)`.

### PCIL-PF-08 — limit 1000 returns all 101 rows
- **Rules:** `get_by_performer` R2 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. `rows = [ProjectComponentItemLedger(**{**ENTRY, "performed_by": U2.id}, performed_at=T1 + timedelta(minutes=k)) for k in range(101)]`, each added and flushed in this order (k = 0 is the oldest).

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### PCIL-PF-09 — an unknown profile id returns an empty list
- **Rules:** `get_by_performer` R1, R4 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-PF-10 — limit 0 returns an empty list
- **Rules:** `get_by_performer` R3 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### PCIL-PF-11 — a negative limit makes the database reject the query
- **Rules:** `get_by_performer` R3 [BUG-645], Errors
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.

**When**
- `dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `isinstance(exc.value.orig, InvalidRowCountInLimitClause)`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### PCIL-PF-12 — a negative skip makes the database reject the query
- **Rules:** `get_by_performer` R3 [BUG-645], Errors
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.

**When**
- `dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `isinstance(exc.value.orig, InvalidRowCountInResultOffsetClause)`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### PCIL-PF-13 — a skip equal to the number of rows returns an empty list
- **Rules:** `get_by_performer` R3 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.
2. E2 = entry, `performed_at T2`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### PCIL-PF-14 — performed_by None returns an empty list and raises nothing
- **Rules:** `get_by_performer` R4 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=None, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-PF-15 — performed_by 0 returns an empty list and raises nothing
- **Rules:** `get_by_performer` R4 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PCIL-PF-16 — rows of a soft-deleted project's component and of an inactive item are listed
- **Rules:** `get_by_performer` R5 [BUG-645]
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`, `project_component_id CD.id`.
2. E2 = entry, `performed_at T2`, but `performed_by U2.id`, `item_id IR.id`.
3. E3 = entry, `performed_at T3`, but `performed_by U2.id`.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E3.id, E2.id, E1.id]`.

### PCIL-PF-17 — writes nothing and takes no lock: a pending row stays pending and unseen, an unflushed edit stays unflushed
- **Rules:** `get_by_performer` R6 [BUG-645], Side effects
- **Kind:** bug
- **Expect:** xfail BUG-645
- **Fails today on:** Then 1 (the call raises AttributeError: the method does not exist)

**Given**
1. E1 = entry, `performed_at T1`, but `performed_by U2.id`.
2. B = entry, `performed_at T2`, but `performed_by U2.id`.
3. `B.notes = "Edited"` (not flushed).
4. `P = ProjectComponentItemLedger(**{**ENTRY, "performed_by": U2.id}, performed_at=T4)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_performer(db, performed_by=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, E1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"FOR UPDATE" not in sql`.
9. nothing written: nothing written.

## `ProjectComponentItemLedgerDAO.calculate_balance`

### PCIL-BAL-01 — with no entry the result is (0, Decimal 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger entry exists.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.
2. returns: `isinstance(result, tuple)`.
3. returns: `isinstance(result[1], Decimal)`.

### PCIL-BAL-02 — the latest entry's quantity and value are returned; earlier entries are not summed
- **Rules:** `calculate_balance` R2, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 10`, `value_after Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `qty_after 7`, `value_after Decimal("35.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (7, Decimal("35.00"))`.
2. returns: `isinstance(result[1], Decimal)`.

### PCIL-BAL-03 — the latest entry wins when it has the lowest id
- **Rules:** `calculate_balance` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`, but `qty_after 3`, `value_after Decimal("6.00")`.
2. E2 = entry, `performed_at T1`, but `qty_after 8`, `value_after Decimal("16.00")`.
3. E3 = entry, `performed_at T2`, but `qty_after 9`, `value_after Decimal("18.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (3, Decimal("6.00"))`.

### PCIL-BAL-04 — the latest entry wins when it has the highest id
- **Rules:** `calculate_balance` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 8`, `value_after Decimal("16.00")`.
2. E2 = entry, `performed_at T2`, but `qty_after 9`, `value_after Decimal("18.00")`.
3. E3 = entry, `performed_at T3`, but `qty_after 3`, `value_after Decimal("6.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (3, Decimal("6.00"))`.

### PCIL-BAL-05 — an older entry with a higher id inside the same day does not win
- **Rules:** `calculate_balance` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`, but `qty_after 3`, `value_after Decimal("6.00")`.
2. E2 = entry, `performed_at T1`, but `id HIGH_ID`, `qty_after 8`, `value_after Decimal("16.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (3, Decimal("6.00"))`.

### PCIL-BAL-06 — an empty value_after gives Decimal 0.00 and keeps qty_after
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 4`, `value_after None`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (4, Decimal("0.00"))`.
2. returns: `isinstance(result[1], Decimal)`.

### PCIL-BAL-07 — an emptied bucket: qty_after 0 with an empty value_after gives (0, 0.00)
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 0`, `value_after None`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.
2. returns: `isinstance(result[1], Decimal)`.

### PCIL-BAL-08 — a stored value_after of 0.00 gives Decimal 0.00
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 2`, `value_after Decimal("0.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (2, Decimal("0.00"))`.
2. returns: `isinstance(result[1], Decimal)`.

### PCIL-BAL-09 — an empty value on the latest entry does not fall back to an earlier entry
- **Rules:** `calculate_balance` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 10`, `value_after Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `qty_after 6`, `value_after None`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (6, Decimal("0.00"))`.

### PCIL-BAL-10 — negative stored figures are returned as they are
- **Rules:** `calculate_balance` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after -3`, `value_after Decimal("-7.50")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (-3, Decimal("-7.50"))`.

### PCIL-BAL-11 — a value_after stored as Decimal("2.125") reads back Decimal("2.13"): half up (half even gives 2.12)
- **Rules:** `calculate_balance` R2, HR-15 (database rounding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 1`, `value_after Decimal("2.125")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, Decimal("2.13"))`.

### PCIL-BAL-12 — a value_after stored as Decimal("0.005") reads back Decimal("0.01"): half up (half even gives 0.00)
- **Rules:** `calculate_balance` R2, HR-15 (database rounding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 1`, `value_after Decimal("0.005")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, Decimal("0.01"))`.

### PCIL-BAL-13 — a value_after stored as Decimal("-1.005") reads back Decimal("-1.01"): half up (half even gives -1.00)
- **Rules:** `calculate_balance` R2, HR-15 (database rounding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 1`, `value_after Decimal("-1.005")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, Decimal("-1.01"))`.

### PCIL-BAL-14 — control: a value_after stored as Decimal("2.124") reads back 2.12
- **Rules:** `calculate_balance` R2, HR-15 (database rounding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 1`, `value_after Decimal("2.124")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (1, Decimal("2.12"))`.

### PCIL-BAL-15 — tied entries: the figures of one of them, never of an older entry
- **Rules:** `calculate_balance` R3 (holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`, but `qty_after 1`, `value_after Decimal("1.00")`.
2. B = entry, `performed_at T2`, but `performed_by U3.id`, `qty_after 15`, `value_after Decimal("150.00")`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `qty_after 10`, `value_after Decimal("100.00")`.
4. A = entry, `performed_at T2`, but `performed_by U2.id`, `qty_after 99`, `value_after Decimal("990.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result in [(15, Decimal("150.00")), (10, Decimal("100.00")), (99, Decimal("990.00"))]`.

### PCIL-BAL-16 — among tied entries the greatest id decides, when the lowest id was updated
- **Rules:** `calculate_balance` R3 [BUG-2463]
- **Kind:** bug
- **Expect:** xfail BUG-2463 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no second sort key; physical row order decides among tied entries)
- **Author:** claude

**Given**
1. B = entry, `performed_at T2`, but `performed_by U3.id`, `qty_after 15`, `value_after Decimal("150.00")`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `qty_after 10`, `value_after Decimal("100.00")`.
3. A = entry, `performed_at T2`, but `performed_by U2.id`, `qty_after 99`, `value_after Decimal("990.00")`.
4. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'x' WHERE id = :i"), {"i": B.id})`, then `db.expire_all()`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result in [(15, Decimal("150.00")), (10, Decimal("100.00")), (99, Decimal("990.00"))]`.
2. returns: `result == (10, Decimal("100.00"))`.

### PCIL-BAL-17 — the query asks for performed_at newest first, then id highest first
- **Rules:** `calculate_balance` R3 [BUG-2463]
- **Kind:** bug
- **Expect:** xfail BUG-2463 (revisit after launch)
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"project_component_item_ledger.performed_at DESC" in order_part`.
4. statement: `"project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC" in order_part`.

### PCIL-BAL-18 — a newer entry of a lower component id does not change the result
- **Rules:** `calculate_balance` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. X = entry, `performed_at T5`, but `project_component_id CL.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### PCIL-BAL-19 — a newer entry of a higher component id does not change the result
- **Rules:** `calculate_balance` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. X = entry, `performed_at T5`, but `project_component_id C2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### PCIL-BAL-20 — a newer entry of a lower item id does not change the result
- **Rules:** `calculate_balance` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. X = entry, `performed_at T5`, but `item_id IL.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### PCIL-BAL-21 — a newer entry of a higher item id does not change the result
- **Rules:** `calculate_balance` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. X = entry, `performed_at T5`, but `item_id I2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### PCIL-BAL-22 — a newer entry of W0 with the same ids does not change the result
- **Rules:** `calculate_balance` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. X = entry, `performed_at T5`, but `workspace_id W0.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### PCIL-BAL-23 — a newer entry of W2 with the same ids does not change the result
- **Rules:** `calculate_balance` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. X = entry, `performed_at T5`, but `workspace_id W2.id`, `qty_after 9`, `value_after Decimal("99.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.

### PCIL-BAL-24 — when only entries of W0 and W2 exist the result is (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T1`, but `workspace_id W0.id`, `qty_after 9`, `value_after Decimal("99.00")`.
2. X2 = entry, `performed_at T2`, but `workspace_id W2.id`, `qty_after 8`, `value_after Decimal("88.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### PCIL-BAL-25 — asked for W2, the W2 entry's figures are returned
- **Rules:** `calculate_balance` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T3`, but `workspace_id W0.id`, `qty_after 9`, `value_after Decimal("99.00")`.
2. E1 = entry, `performed_at T4`, but `qty_after 5`, `value_after Decimal("10.00")`.
3. X2 = entry, `performed_at T1`, but `workspace_id W2.id`, `qty_after 8`, `value_after Decimal("88.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == (8, Decimal("88.00"))`.

### PCIL-BAL-26 — another workspace's component and item ids, asked under W1, give (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = entry, `performed_at T1`, but `workspace_id W2.id`, `project_component_id C9.id`, `item_id I9.id`, `qty_after 8`, `value_after Decimal("88.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C9.id, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### PCIL-BAL-27 — an unknown component id gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=MISSING, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### PCIL-BAL-28 — an unknown item id gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### PCIL-BAL-29 — component id 0 gives (0, 0.00)
- **Rules:** `calculate_balance` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=0, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (0, Decimal("0.00"))`.

### PCIL-BAL-30 — the balance of a soft-deleted project's component is returned
- **Rules:** `calculate_balance` R5 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `project_component_id CD.id`, `qty_after 30`, `value_after Decimal("75.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=CD.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (30, Decimal("75.00"))`.

### PCIL-BAL-31 — the balance of an inactive item is returned
- **Rules:** `calculate_balance` R5 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`, `qty_after 30`, `value_after Decimal("75.00")`.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (30, Decimal("75.00"))`.

### PCIL-BAL-32 — writes nothing: a newer pending entry is not seen and stays pending, an unflushed edit stays unflushed
- **Rules:** `calculate_balance` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `qty_after 5`, `value_after Decimal("10.00")`.
2. `E1.notes = "Edited"` (not flushed).
3. `P = ProjectComponentItemLedger(**ENTRY, performed_at=T5)`, then `P.qty_after = 9`, then `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == (5, Decimal("10.00"))`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `E1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"JOIN" not in sql.upper()`.
9. statement: `"FOR UPDATE" not in sql`.

## `ProjectComponentItemLedgerDAO.get_latest_entry`

### PCIL-LE-01 — with no entry the result is None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger entry exists.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PCIL-LE-02 — the newest entry is returned when it has the middle id
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`.
2. E2 = entry, `performed_at T3`.
3. E3 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProjectComponentItemLedger)`.
2. returns: `result.id == E2.id`.

### PCIL-LE-03 — the newest entry is returned when it has the lowest id
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`.
2. E2 = entry, `performed_at T1`.
3. E3 = entry, `performed_at T2`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProjectComponentItemLedger)`.
2. returns: `result.id == E1.id`.

### PCIL-LE-04 — the newest entry is returned when it has the highest id
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. E2 = entry, `performed_at T2`.
3. E3 = entry, `performed_at T3`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, ProjectComponentItemLedger)`.
2. returns: `result.id == E3.id`.

### PCIL-LE-05 — an older entry with a higher id inside the same day does not win
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T2`.
2. E2 = entry, `performed_at T1`, but `id HIGH_ID`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-06 — the full row is returned with its money columns as stored
- **Rules:** `get_latest_entry` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `unit_cost Decimal("2.50")`, `total_cost Decimal("7.50")`, `value_before Decimal("10.00")`, `value_after Decimal("17.50")`, `avg_price_before Decimal("2.50")`, `avg_price_after Decimal("2.50")`, `qty_after 7`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `(result.unit_cost, result.total_cost) == (Decimal("2.50"), Decimal("7.50"))`.
2. returns: `(result.value_before, result.value_after) == (Decimal("10.00"), Decimal("17.50"))`.
3. returns: `(result.avg_price_before, result.avg_price_after) == (Decimal("2.50"), Decimal("2.50"))`.
4. returns: `result.qty_after == 7`.

### PCIL-LE-07 — empty value and price columns come back as None
- **Rules:** `get_latest_entry` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.value_before is None`.
2. returns: `result.value_after is None`.
3. returns: `result.avg_price_before is None`.
4. returns: `result.avg_price_after is None`.

### PCIL-LE-08 — tied entries: one of them is returned, never an older entry
- **Rules:** `get_latest_entry` R2 (holds today)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. O = entry, `performed_at T1`.
2. B = entry, `performed_at T2`, but `performed_by U3.id`, `notes "Abe"`.
3. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `notes "Mid"`.
4. A = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Zed"`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in [B.id, C.id, A.id]`.

### PCIL-LE-09 — among tied entries the greatest id is returned, when the lowest id was updated
- **Rules:** `get_latest_entry` R2 [BUG-2463]
- **Kind:** bug
- **Expect:** xfail BUG-2463 (non-strict, revisit after launch)
- **Fails today on:** Then 2 (no second sort key; physical row order decides among tied entries)
- **Author:** claude

**Given**
1. B = entry, `performed_at T2`, but `performed_by U3.id`, `notes "Abe"`.
2. C = entry, `performed_at T2`, but `id HIGH_ID`, `performed_by U1.id`, `notes "Mid"`.
3. A = entry, `performed_at T2`, but `performed_by U2.id`, `notes "Zed"`.
4. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'Abe two' WHERE id = :i"), {"i": B.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id in [B.id, C.id, A.id]`.
2. returns: `result.id == C.id`.

### PCIL-LE-10 — the query asks for performed_at newest first, then id highest first
- **Rules:** `get_latest_entry` R2 [BUG-2463]
- **Kind:** bug
- **Expect:** xfail BUG-2463 (revisit after launch)
- **Fails today on:** Then 4 (the clause ends at `performed_at DESC`: no second sort key)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"project_component_item_ledger.performed_at DESC" in order_part`.
4. statement: `"project_component_item_ledger.performed_at DESC, project_component_item_ledger.id DESC" in order_part`.

### PCIL-LE-11 — it returns the entry whose figures calculate_balance reads
- **Rules:** `get_latest_entry` R3 · `calculate_balance` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T3`, but `qty_after 4`, `value_after Decimal("12.00")`.
2. E2 = entry, `performed_at T1`, but `id HIGH_ID`, `qty_after 9`, `value_after Decimal("27.00")`.
3. E3 = entry, `performed_at T2`, but `qty_after 6`, `value_after Decimal("18.00")`.

**When**
- `latest, bal = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id), dao.calculate_balance(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)` (one step).

**Then**
1. returns: `latest.id == E1.id`.
2. returns: `bal == (latest.qty_after, latest.value_after)`.
3. returns: `bal == (4, Decimal("12.00"))`.

### PCIL-LE-12 — a newer entry of a lower component id is not considered
- **Rules:** `get_latest_entry` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X = entry, `performed_at T5`, but `project_component_id CL.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-13 — a newer entry of a higher component id is not considered
- **Rules:** `get_latest_entry` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X = entry, `performed_at T5`, but `project_component_id C2.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-14 — a newer entry of a lower item id is not considered
- **Rules:** `get_latest_entry` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X = entry, `performed_at T5`, but `item_id IL.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-15 — a newer entry of a higher item id is not considered
- **Rules:** `get_latest_entry` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X = entry, `performed_at T5`, but `item_id I2.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-16 — a newer entry of W0 with the same ids is not considered
- **Rules:** `get_latest_entry` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X = entry, `performed_at T5`, but `workspace_id W0.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-17 — a newer entry of W2 with the same ids is not considered
- **Rules:** `get_latest_entry` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. X = entry, `performed_at T5`, but `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-18 — when only entries of W0 and W2 exist the result is None
- **Rules:** `get_latest_entry` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T1`, but `workspace_id W0.id`.
2. X2 = entry, `performed_at T2`, but `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PCIL-LE-19 — asked for W0, the W0 entry is returned
- **Rules:** `get_latest_entry` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T1`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T4`.
3. X2 = entry, `performed_at T5`, but `workspace_id W2.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W0.id)`.

**Then**
1. returns: `result.id == X0.id`.

### PCIL-LE-20 — another workspace's component and item ids, asked under W1, give None
- **Rules:** `get_latest_entry` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = entry, `performed_at T1`, but `workspace_id W2.id`, `project_component_id C9.id`, `item_id I9.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C9.id, item_id=I9.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PCIL-LE-21 — an unknown component id gives None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=MISSING, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PCIL-LE-22 — an unknown item id gives None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PCIL-LE-23 — item id 0 gives None
- **Rules:** `get_latest_entry` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PCIL-LE-24 — the latest entry of a soft-deleted project's component is returned
- **Rules:** `get_latest_entry` R4 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `project_component_id CD.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=CD.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-25 — the latest entry of an inactive item is returned
- **Rules:** `get_latest_entry` R4 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `item_id IR.id`.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=IR.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.

### PCIL-LE-26 — writes nothing: a newer pending entry is not seen and stays pending, an unflushed edit stays unflushed
- **Rules:** `get_latest_entry` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`.
2. `E1.notes = "Edited"` (not flushed).
3. `P = ProjectComponentItemLedger(**ENTRY, performed_at=T5)`, then `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_latest_entry(db, project_component_id=C1.id, item_id=I1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == E1.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `E1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"JOIN" not in sql.upper()`.
9. statement: `"FOR UPDATE" not in sql`.

## `ProjectComponentItemLedgerDAO.calculate_total_cost_for_component`

### PCIL-TC-01 — with no rows the result is Decimal 0.00
- **Rules:** `calculate_total_cost_for_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ledger entry exists.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.00")`.

### PCIL-TC-02 — rows of added types are summed exactly, whatever their item
- **Rules:** `calculate_total_cost_for_component` R1 (added types; holds today), R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "purchase_order"`, `item_id I2.id`, `total_cost Decimal("15.00")`.
3. E3 = entry, `performed_at T3`, but `transaction_type "consumption"`, `total_cost Decimal("0.13")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("65.13")`.

### PCIL-TC-03 — every added type counts: purchase_order, manual_add, transfer_in, consumption, inventory_adjustment, cost_adjustment
- **Rules:** `calculate_total_cost_for_component` R1 (added types; holds today)
- **Kind:** happy
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "purchase_order"`, `total_cost Decimal("1.00")`.
2. E2 = entry, `performed_at T1`, but `transaction_type "manual_add"`, `total_cost Decimal("2.00")`.
3. E3 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("4.00")`.
4. E4 = entry, `performed_at T1`, but `transaction_type "consumption"`, `total_cost Decimal("8.00")`.
5. E5 = entry, `performed_at T1`, but `transaction_type "inventory_adjustment"`, `total_cost Decimal("16.00")`.
6. E6 = entry, `performed_at T1`, but `transaction_type "cost_adjustment"`, `total_cost Decimal("32.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("63.00")`.

### PCIL-TC-04 — a sum of exactly zero gives Decimal 0.00
- **Rules:** `calculate_total_cost_for_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("1.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_in"`, `total_cost Decimal("-1.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.00")`.

### PCIL-TC-05 — a negative stored cost is added as it is
- **Rules:** `calculate_total_cost_for_component` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_in"`, `total_cost Decimal("-7.25")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("-2.25")`.

### PCIL-TC-06 — costs stored as 2.125, 0.005 and 2.124 sum to 4.26: each is rounded half up when stored, then added exactly
- **Rules:** `calculate_total_cost_for_component` R3, HR-15 (database rounding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("2.125")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_in"`, `total_cost Decimal("0.005")`.
3. E3 = entry, `performed_at T3`, but `transaction_type "transfer_in"`, `total_cost Decimal("2.124")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("4.26")` (half even would give 4.24; adding unrounded values would give 4.25).

### PCIL-TC-07 — a cost stored as -1.005 counts as -1.01, half up away from zero
- **Rules:** `calculate_total_cost_for_component` R3, HR-15 (database rounding)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_in"`, `total_cost Decimal("-1.005")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("3.99")` (half even would give 4.00).

### PCIL-TC-08 — a large sum with cents keeps two places exactly
- **Rules:** `calculate_total_cost_for_component` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("0.10")`.
2. E2 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("0.20")`.
3. E3 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("0.70")`.
4. E4 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("9999999999999.99")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("10000000000000.99")`.
2. returns: `str(result) == "10000000000000.99"`.

### PCIL-TC-09 — transfer_out is subtracted: 50.00 in, 15.00 out, 0.13 consumed give 35.13
- **Rules:** `calculate_total_cost_for_component` R1 [BUG-654]
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 65.13)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`, `total_cost Decimal("15.00")`.
3. E3 = entry, `performed_at T3`, but `transaction_type "consumption"`, `total_cost Decimal("0.13")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("35.13")`.

### PCIL-TC-10 — damaged is subtracted: 50.00 in, 7.50 damaged give 42.50
- **Rules:** `calculate_total_cost_for_component` R1 [BUG-654]
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 57.50)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "damaged"`, `total_cost Decimal("7.50")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("42.50")`.

### PCIL-TC-11 — a net of exactly zero gives Decimal 0.00: 15.00 in, 15.00 out
- **Rules:** `calculate_total_cost_for_component` R1 [BUG-654], R2
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 30.00)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("15.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`, `total_cost Decimal("15.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.00")`.

### PCIL-TC-12 — only outgoing rows give a negative net
- **Rules:** `calculate_total_cost_for_component` R1 [BUG-654]
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 17.50)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_out"`, `total_cost Decimal("15.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "damaged"`, `total_cost Decimal("2.50")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("-17.50")`.

### PCIL-TC-13 — a subtracted cost stored as 2.125 counts as 2.13: 10.00 in, 2.125 out give 7.87
- **Rules:** `calculate_total_cost_for_component` R1 [BUG-654], HR-15 (database rounding)
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 12.13)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("10.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`, `total_cost Decimal("2.125")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("7.87")` (half even would give 7.88).

### PCIL-TC-14 — the look-alike transfer_in is added next to a subtracted transfer_out
- **Rules:** `calculate_total_cost_for_component` R1 [BUG-654]
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 26.00)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("20.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`, `total_cost Decimal("5.00")`.
3. E3 = entry, `performed_at T3`, but `transaction_type "transfer_in"`, `total_cost Decimal("1.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("16.00")`.

### PCIL-TC-15 — a row of a lower component id does not count
- **Rules:** `calculate_total_cost_for_component` R1a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
2. X = entry, `performed_at T2`, but `project_component_id CL.id`, `total_cost Decimal("100.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("5.00")`.

### PCIL-TC-16 — a row of a higher component id does not count
- **Rules:** `calculate_total_cost_for_component` R1a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
2. X = entry, `performed_at T2`, but `project_component_id C2.id`, `total_cost Decimal("100.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("5.00")`.

### PCIL-TC-17 — a row of W0 with the same component id does not count
- **Rules:** `calculate_total_cost_for_component` R1a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
2. X = entry, `performed_at T2`, but `workspace_id W0.id`, `total_cost Decimal("100.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("5.00")`.

### PCIL-TC-18 — a row of W2 with the same component id does not count
- **Rules:** `calculate_total_cost_for_component` R1a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
2. X = entry, `performed_at T2`, but `workspace_id W2.id`, `total_cost Decimal("100.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("5.00")`.

### PCIL-TC-19 — asked for W2, only the W2 row counts
- **Rules:** `calculate_total_cost_for_component` R1a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T1`, but `workspace_id W0.id`, `total_cost Decimal("1.00")`.
2. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
3. X2 = entry, `performed_at T1`, but `workspace_id W2.id`, `total_cost Decimal("3.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == Decimal("3.00")`.

### PCIL-TC-20 — another workspace's component id, asked under W1, gives Decimal 0.00
- **Rules:** `calculate_total_cost_for_component` R1a
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X2 = entry, `performed_at T1`, but `workspace_id W2.id`, `project_component_id C9.id`, `item_id I9.id`, `total_cost Decimal("3.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C9.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.00")`.

### PCIL-TC-21 — an unknown component id gives Decimal 0.00
- **Rules:** `calculate_total_cost_for_component` R1a, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("0.00")`.

### PCIL-TC-22 — rows of a soft-deleted project's component and of an inactive item count
- **Rules:** `calculate_total_cost_for_component` R1a
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `project_component_id CD.id`, `total_cost Decimal("4.00")`.
2. E2 = entry, `performed_at T2`, but `project_component_id CD.id`, `item_id IR.id`, `total_cost Decimal("6.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=CD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("10.00")`.

### PCIL-TC-23 — writes nothing: a pending row does not count and stays pending, an unflushed edit stays unflushed
- **Rules:** `calculate_total_cost_for_component` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("5.00")`.
2. `E1.total_cost = Decimal("9.00")` (not flushed).
3. `P = ProjectComponentItemLedger(**ENTRY, performed_at=T2)`, then `P.total_cost = Decimal("100.00")`, then `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == Decimal("5.00")`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `E1 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"JOIN" not in sql.upper()`.

### PCIL-TC-24 — a stored "Transfer_Out" is not the outgoing type: it is added
- **Rules:** `calculate_total_cost_for_component` R1b (holds today and after the fix), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "Transfer_Out"`, `total_cost Decimal("15.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("65.00")`.

### PCIL-TC-25 — a stored "DAMAGED" is not the outgoing type: it is added
- **Rules:** `calculate_total_cost_for_component` R1b (holds today and after the fix), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "DAMAGED"`, `total_cost Decimal("7.50")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("57.50")`.

### PCIL-TC-26 — a stored " transfer_out" with a leading space is added
- **Rules:** `calculate_total_cost_for_component` R1b (holds today and after the fix), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("20.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type " transfer_out"`, `total_cost Decimal("5.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("25.00")`.

### PCIL-TC-27 — a stored "damaged " with a trailing space is added
- **Rules:** `calculate_total_cost_for_component` R1b (holds today and after the fix), R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("20.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "damaged "`, `total_cost Decimal("2.50")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("22.50")`.

### PCIL-TC-28 — transfer_out is subtracted while "Transfer_Out" next to it is added: 50.00 in, 15.00 out, 7.00 look-alike give 42.00
- **Rules:** `calculate_total_cost_for_component` R1b, R1 [BUG-654]
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 72.00)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "transfer_out"`, `total_cost Decimal("15.00")`.
3. E3 = entry, `performed_at T3`, but `transaction_type "Transfer_Out"`, `total_cost Decimal("7.00")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("42.00")`.

### PCIL-TC-29 — damaged is subtracted while "DAMAGED" next to it is added: 50.00 in, 7.50 damaged, 2.50 look-alike give 45.00
- **Rules:** `calculate_total_cost_for_component` R1b, R1 [BUG-654]
- **Kind:** bug
- **Expect:** xfail BUG-654 (revisit after launch)
- **Fails today on:** Then 2 (today a plain sum: 60.00)

**Given**
1. E1 = entry, `performed_at T1`, but `transaction_type "transfer_in"`, `total_cost Decimal("50.00")`.
2. E2 = entry, `performed_at T2`, but `transaction_type "damaged"`, `total_cost Decimal("7.50")`.
3. E3 = entry, `performed_at T3`, but `transaction_type "DAMAGED"`, `total_cost Decimal("2.50")`.

**When**
- `result = dao.calculate_total_cost_for_component(db, project_component_id=C1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Decimal)`.
2. returns: `result == Decimal("45.00")`.

## Inherited `BaseDAO` methods

### PCIL-INH-01 — get_by_workspace returns the workspace's rows only, with W0 and W2 rows present
- **Rules:** `inherited` R1, R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X0 = entry, `performed_at T1`, but `workspace_id W0.id`.
2. E1 = entry, `performed_at T1`.
3. E2 = entry, `performed_at T2`, but `project_component_id C2.id`.
4. X2 = entry, `performed_at T1`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {E1.id, E2.id}`.

### PCIL-INH-02 — get_by_workspace returns rows by id ascending, when the lowest id was updated
- **Rules:** `inherited` R2 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100 (non-strict)
- **Fails today on:** Then 2 (no order is requested; physical row order decides)
- **Author:** claude

**Given**
1. A = entry, `performed_at T3`.
2. B = entry, `performed_at T1`, but `id HIGH_ID`.
3. C = entry, `performed_at T2`.
4. `db.execute(text("UPDATE project_component_item_ledger SET notes = 'x' WHERE id = :i"), {"i": A.id})`, then `db.expire_all()`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, C.id}`.
2. returns: `ids(result) == [A.id, C.id, B.id]`.

### PCIL-INH-03 — get_by_workspace orders by id ascending
- **Rules:** `inherited` R2 [BUG-100]
- **Kind:** bug
- **Expect:** xfail BUG-100
- **Fails today on:** Then 2 (no ORDER BY is sent)

**Given**
1. E1 = entry, `performed_at T1`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [E1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"project_component_item_ledger.id" in order_part`.

## OQ-27 — answered: revisit after launch (owner 2026-11-10)

No card. The owner answered OQ-27 on 2026-11-10: projects are skipped until after launch, and the tests keep today's behaviour, with no bug. No rule of this DAO changed, and every card above builds its own rows. The bug cards that only matter once rows exist carry *revisit after launch* (see Conventions, xfail cards). When a writer is built after launch, its own spec gets the cards.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-642 (HR-7) | `GET /ledgers/project-component/` (ledger endpoints) | `limit` below 1 is refused with 422 before the DAO is called; the DAO's own `limit=0` / negative behaviour stays as pinned here. |
| BUG-647 (+ BUG-646, BUG-648) | `LedgerManager` / item movement report | the `project` list: one item's entries, each date bound on its own, paged; the fix adds `item_id` and a `None` bound meaning no bound to `get_by_date_range` (PCIL-DR ArgumentError cards then change). |
| BUG-991 | ledger endpoints | a date-only end bound means the whole day. |
| BUG-654 type list | `tests/unit/managers/ledger_manager.spec.md` `calculate_project_component_total_cost` R1 | the full list of subtracted types and the default for future types. |
| BUG-645 caller | `LedgerManager.get_transactions_by_user` | `GET /ledgers/reports/user-transactions/{user_id}/` answers without `AttributeError` once the method exists. |
| BUG-1278 | `require_component_access` | who may open a deleted project's component ledger. |
| FU-1 | `ProjectComponentItemLedgerResponse` schema | other stored types / negative costs must not make the list answer 500 (BUG-990 precedent). |
| FU-2 | project component item service spec | the sentence "written by work orders" is corrected. |
| FU-3 | profile deletion | hard-deleting a profile with ledger entries (`performed_by` NOT NULL, ON DELETE SET NULL). |
| OQ-27 | the future writer of this ledger (not built) | which movements write rows, priced at the source's average cost, half up. |
| Inherited R1 | `tests/unit/dao/base.cases.md` | `get`, `get_by_id_and_workspace`, `get_multi`, `create`, `update`, `remove` (not repeated here). |

## Spec gaps
None. Revision 1's gaps are closed by the spec's Gap log (2026-11-10):
- Gap 1, G1 (fact): both fallbacks are `Decimal('0.00')`. The `isinstance(..., Decimal)` cards stand.
- Gap 2, G2 (intent): `calculate_total_cost_for_component` R1b, exact match → PCIL-TC-24 … TC-29.
- Gap 3, G3 (intent): `get_by_performer` R3–R6 → PCIL-PF-09 (R4), PF-10 … PF-17.
- Gap 4, G4 (intent): `get_by_date_range` R2b, each bound normalised on its own → PCIL-DR-46 … DR-51.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_component_and_item` | R1 | PCIL-CI-01, PCIL-CI-02, PCIL-CI-03, PCIL-CI-04, PCIL-CI-05, PCIL-CI-16, PCIL-CI-17, PCIL-CI-27, PCIL-CI-28, PCIL-CI-29, PCIL-CI-30 |
| `get_by_component_and_item` | R3 (newest first; holds today) | PCIL-CI-01, PCIL-CI-06, PCIL-CI-18 |
| `get_by_component_and_item` | Returns | PCIL-CI-01 |
| `get_by_component_and_item` | R5 | PCIL-CI-06, PCIL-CI-07, PCIL-CI-08, PCIL-CI-09, PCIL-CI-10, PCIL-CI-11, PCIL-CI-12, PCIL-CI-13, PCIL-CI-14, PCIL-CI-15, PCIL-CI-16, PCIL-CI-17, PCIL-CI-20 |
| `get_by_component_and_item` | Errors | PCIL-CI-14, PCIL-CI-15 |
| `get_by_component_and_item` | R3 [BUG-640] | PCIL-CI-19, PCIL-CI-20, PCIL-CI-21 |
| `get_by_component_and_item` | Side effects | PCIL-CI-22 |
| `get_by_component_and_item` | R4 | PCIL-CI-22 |
| `get_by_component_and_item` | R2 | PCIL-CI-23, PCIL-CI-24, PCIL-CI-25, PCIL-CI-26 |
| `get_by_component_and_item` | R4 (P1) | PCIL-CI-31, PCIL-CI-32 |
| `get_by_component` | R1 | PCIL-CO-01, PCIL-CO-02, PCIL-CO-03, PCIL-CO-04, PCIL-CO-05, PCIL-CO-16, PCIL-CO-17, PCIL-CO-23, PCIL-CO-24, PCIL-CO-25, PCIL-CO-28 |
| `get_by_component` | R2 | PCIL-CO-01, PCIL-CO-02, PCIL-CO-03, PCIL-CO-04, PCIL-CO-05, PCIL-CO-16, PCIL-CO-17, PCIL-CO-26, PCIL-CO-27 |
| `get_by_component` | R3 (newest first; holds today) | PCIL-CO-01, PCIL-CO-06, PCIL-CO-18 |
| `get_by_component` | Returns | PCIL-CO-01 |
| `get_by_component` | R5 | PCIL-CO-06, PCIL-CO-07, PCIL-CO-08, PCIL-CO-09, PCIL-CO-10, PCIL-CO-11, PCIL-CO-12, PCIL-CO-13, PCIL-CO-14, PCIL-CO-15, PCIL-CO-16, PCIL-CO-17, PCIL-CO-20 |
| `get_by_component` | Errors | PCIL-CO-14, PCIL-CO-15 |
| `get_by_component` | R3 [BUG-640] | PCIL-CO-19, PCIL-CO-20, PCIL-CO-21 |
| `get_by_component` | Side effects | PCIL-CO-22 |
| `get_by_component` | R4 | PCIL-CO-22 |
| `get_by_component` | R4 (P1) | PCIL-CO-29, PCIL-CO-30 |
| `get_by_transaction_type` | R1 | PCIL-TT-01, PCIL-TT-02, PCIL-TT-03, PCIL-TT-04, PCIL-TT-05, PCIL-TT-16, PCIL-TT-17, PCIL-TT-23, PCIL-TT-24, PCIL-TT-25, PCIL-TT-26, PCIL-TT-27, PCIL-TT-28, PCIL-TT-29, PCIL-TT-30, PCIL-TT-31, PCIL-TT-32, PCIL-TT-33, PCIL-TT-34, PCIL-TT-35, PCIL-TT-36, PCIL-TT-37 |
| `get_by_transaction_type` | R2 | PCIL-TT-01, PCIL-TT-02, PCIL-TT-03, PCIL-TT-04, PCIL-TT-05, PCIL-TT-16, PCIL-TT-17, PCIL-TT-38 |
| `get_by_transaction_type` | R3 (newest first; holds today) | PCIL-TT-01, PCIL-TT-06, PCIL-TT-18 |
| `get_by_transaction_type` | Returns | PCIL-TT-01 |
| `get_by_transaction_type` | R5 | PCIL-TT-06, PCIL-TT-07, PCIL-TT-08, PCIL-TT-09, PCIL-TT-10, PCIL-TT-11, PCIL-TT-12, PCIL-TT-13, PCIL-TT-14, PCIL-TT-15, PCIL-TT-16, PCIL-TT-17, PCIL-TT-20 |
| `get_by_transaction_type` | Errors | PCIL-TT-14, PCIL-TT-15 |
| `get_by_transaction_type` | R3 [BUG-2462] | PCIL-TT-19, PCIL-TT-20, PCIL-TT-21 |
| `get_by_transaction_type` | Side effects | PCIL-TT-22 |
| `get_by_transaction_type` | R4 | PCIL-TT-22 |
| `get_by_transaction_type` | R4 (P1) | PCIL-TT-39 |
| `get_by_date_range` | R1 | PCIL-DR-01, PCIL-DR-02, PCIL-DR-03, PCIL-DR-04, PCIL-DR-05, PCIL-DR-16, PCIL-DR-17, PCIL-DR-23, PCIL-DR-24, PCIL-DR-25, PCIL-DR-26, PCIL-DR-27, PCIL-DR-28, PCIL-DR-29, PCIL-DR-36, PCIL-DR-37 |
| `get_by_date_range` | R5 | PCIL-DR-01, PCIL-DR-02, PCIL-DR-03, PCIL-DR-04, PCIL-DR-05, PCIL-DR-16, PCIL-DR-17, PCIL-DR-22, PCIL-DR-33 |
| `get_by_date_range` | R4 (newest first; holds today) | PCIL-DR-01, PCIL-DR-06, PCIL-DR-18 |
| `get_by_date_range` | Returns | PCIL-DR-01 |
| `get_by_date_range` | R6 | PCIL-DR-06, PCIL-DR-07, PCIL-DR-08, PCIL-DR-09, PCIL-DR-10, PCIL-DR-11, PCIL-DR-12, PCIL-DR-13, PCIL-DR-14, PCIL-DR-15, PCIL-DR-16, PCIL-DR-17, PCIL-DR-20 |
| `get_by_date_range` | Errors row 2 | PCIL-DR-14, PCIL-DR-15 |
| `get_by_date_range` | R4 [BUG-2462] | PCIL-DR-19, PCIL-DR-20, PCIL-DR-21 |
| `get_by_date_range` | Side effects | PCIL-DR-22 |
| `get_by_date_range` | R2 | PCIL-DR-30, PCIL-DR-31, PCIL-DR-32 |
| `get_by_date_range` | R3 | PCIL-DR-34, PCIL-DR-35 |
| `get_by_date_range` | Errors row 1 | PCIL-DR-34, PCIL-DR-35 |
| `get_by_date_range` | R2a [BUG-2464] | PCIL-DR-38, PCIL-DR-39, PCIL-DR-40, PCIL-DR-41 |
| `get_by_date_range` | R2a | PCIL-DR-42, PCIL-DR-43, PCIL-DR-44 |
| `get_by_date_range` | R5 (P1) | PCIL-DR-45 |
| `get_by_date_range` | R2b [BUG-2464] | PCIL-DR-46, PCIL-DR-47, PCIL-DR-48, PCIL-DR-49 |
| `get_by_date_range` | R2b (holds today) | PCIL-DR-50, PCIL-DR-51 |
| `get_by_performer` | R1 [BUG-645] | PCIL-PF-01, PCIL-PF-02, PCIL-PF-03, PCIL-PF-04, PCIL-PF-09 |
| `get_by_performer` | R2 [BUG-645] | PCIL-PF-01, PCIL-PF-05, PCIL-PF-06, PCIL-PF-07, PCIL-PF-08 |
| `get_by_performer` | R3 [BUG-645] | PCIL-PF-06, PCIL-PF-10, PCIL-PF-11, PCIL-PF-12, PCIL-PF-13 |
| `get_by_performer` | Errors | PCIL-PF-11, PCIL-PF-12 |
| `get_by_performer` | R4 [BUG-645] | PCIL-PF-09, PCIL-PF-14, PCIL-PF-15 |
| `get_by_performer` | R5 [BUG-645] | PCIL-PF-16 |
| `get_by_performer` | R6 [BUG-645] / Side effects | PCIL-PF-17 |
| `calculate_balance` | R1 | PCIL-BAL-01, PCIL-BAL-18, PCIL-BAL-19, PCIL-BAL-20, PCIL-BAL-21, PCIL-BAL-22, PCIL-BAL-23, PCIL-BAL-24, PCIL-BAL-25, PCIL-BAL-26, PCIL-BAL-27, PCIL-BAL-28, PCIL-BAL-29 |
| `calculate_balance` | R2 | PCIL-BAL-02, PCIL-BAL-03, PCIL-BAL-04, PCIL-BAL-05, PCIL-BAL-06, PCIL-BAL-07, PCIL-BAL-08, PCIL-BAL-09, PCIL-BAL-10, PCIL-BAL-11, PCIL-BAL-12, PCIL-BAL-13, PCIL-BAL-14, PCIL-BAL-18, PCIL-BAL-19, PCIL-BAL-20, PCIL-BAL-21, PCIL-BAL-22, PCIL-BAL-23, PCIL-BAL-25, PCIL-LE-11 |
| `calculate_balance` | R4 | PCIL-BAL-02, PCIL-BAL-09 |
| `calculate_balance` | HR-15 (database rounding) | PCIL-BAL-11, PCIL-BAL-12, PCIL-BAL-13, PCIL-BAL-14 |
| `calculate_balance` | R3 (holds today) | PCIL-BAL-15 |
| `calculate_balance` | R3 [BUG-2463] | PCIL-BAL-16, PCIL-BAL-17 |
| `calculate_balance` | R5 (P2) | PCIL-BAL-30, PCIL-BAL-31 |
| `calculate_balance` | Side effects | PCIL-BAL-32 |
| `get_latest_entry` | R1 | PCIL-LE-01, PCIL-LE-12, PCIL-LE-13, PCIL-LE-14, PCIL-LE-15, PCIL-LE-16, PCIL-LE-17, PCIL-LE-18, PCIL-LE-19, PCIL-LE-20, PCIL-LE-21, PCIL-LE-22, PCIL-LE-23 |
| `get_latest_entry` | R2 | PCIL-LE-02, PCIL-LE-03, PCIL-LE-04, PCIL-LE-05, PCIL-LE-06, PCIL-LE-07, PCIL-LE-12, PCIL-LE-13, PCIL-LE-14, PCIL-LE-15, PCIL-LE-16, PCIL-LE-17 |
| `get_latest_entry` | R2 (holds today) | PCIL-LE-08 |
| `get_latest_entry` | R2 [BUG-2463] | PCIL-LE-09, PCIL-LE-10 |
| `get_latest_entry` | R3 | PCIL-LE-11 |
| `get_latest_entry` | R4 (P2) | PCIL-LE-24, PCIL-LE-25 |
| `get_latest_entry` | Side effects | PCIL-LE-26 |
| `calculate_total_cost_for_component` | R2 | PCIL-TC-01, PCIL-TC-04, PCIL-TC-11, PCIL-TC-21 |
| `calculate_total_cost_for_component` | R1 (added types; holds today) | PCIL-TC-02, PCIL-TC-03 |
| `calculate_total_cost_for_component` | R3 | PCIL-TC-02, PCIL-TC-05, PCIL-TC-06, PCIL-TC-07, PCIL-TC-08 |
| `calculate_total_cost_for_component` | HR-15 (database rounding) | PCIL-TC-06, PCIL-TC-07, PCIL-TC-13 |
| `calculate_total_cost_for_component` | R1 [BUG-654] | PCIL-TC-09, PCIL-TC-10, PCIL-TC-11, PCIL-TC-12, PCIL-TC-13, PCIL-TC-14 |
| `calculate_total_cost_for_component` | R1a | PCIL-TC-15, PCIL-TC-16, PCIL-TC-17, PCIL-TC-18, PCIL-TC-19, PCIL-TC-20, PCIL-TC-21, PCIL-TC-22 |
| `calculate_total_cost_for_component` | Side effects | PCIL-TC-23 |
| `calculate_total_cost_for_component` | R1b (holds today) | PCIL-TC-24, PCIL-TC-25, PCIL-TC-26, PCIL-TC-27 |
| `calculate_total_cost_for_component` | R1b [BUG-654] | PCIL-TC-28, PCIL-TC-29 |
| `inherited` | R1 | PCIL-INH-01 |
| `inherited` | R2 | PCIL-INH-01 |
| `inherited` | R2 [BUG-100] | PCIL-INH-02, PCIL-INH-03 |
| `get_by_order` | Not specified (Q2, dead code) | — |
| all | OQ-27 (answered, revisit after launch) | no rule changed; see section |
