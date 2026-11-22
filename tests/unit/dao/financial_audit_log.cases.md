# Test cases — `app/dao/financial_audit_log.py`

> **Spec:** `tests/unit/dao/financial_audit_log.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-06; revised 2026-11-07). OQ-23 (who may read the log) was answered by the owner on 2026-11-07: deferred to the permissions work, no bug. It lives in the endpoints and no rule of this DAO depends on it, so there is no pending section here.
> **Revision:** 2 (2026-11-07) — spec fill-gaps G1–G2. G1: keyword-only calls stay a note by design, no card. G2: new rule `get_recent_logs` R1a → new FAL-RC-12 (`skip=` raises `TypeError` before any query). The OQ-23 Deferred row now records the owner's answer. No card changed or retired.
> **Revision:** 3 (2026-11-09) — wording only, `financial_audit_log.verify.md` n1: the Reviewer summary now counts 13 BUG-2370 cards (6 tie cards, BE-17, 6 SQL recorders). No card changed.
> **Counts:** 115 cases · 99 expected-to-pass · 16 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_by_entity` 29 (3 bug) · `get_related_logs` 19 (2 bug) · `get_by_action_type` 18 (2 bug) · `get_by_user` 14 (2 bug) · `get_by_date_range` 21 (4 bug) · `get_recent_logs` 12 (2 bug) · model fact N1 2 (1 bug).
- **Depth:** lighter target (skill step 1a). Six workspace-scoped reads of an append-only log; nothing here writes money or order state, and amounts are only read back. Each reader is its own query, so each gets its own isolation, paging, order and "writes nothing" cards; the exact-compare shapes (part, `_`, capitals, leading space, stored side) are applied once per compared column.
- **Expected-to-fail:** BUG-2370 13 — per reader one non-strict tie card and one strict SQL recorder (6 + 6), plus the page-one-at-a-time card BE-17 on `get_by_entity`. BUG-2371 2 strict (aware bounds under `Asia/Dhaka` and `America/New_York`). BUG-2372 1 strict (N1, under `Asia/Dhaka`).
- **Notable design choices:**
  - Workspace filters: W0 (built before W1) and W2 (after) hold matching rows in every isolation card. `entity_id`, `related_entity_id` and `performed_by` filters sit between a lower and a higher value.
  - Time-zone cards set the zone themselves (`zone(...)`); BUG-2371's passing companions (naive bounds under Dhaka, aware bounds under `UTC`) hold today and after the fix.
  - DR-09 puts a second row where today's wrong compare lands, so the fix must both find the right row and drop the wrong one.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None. Gaps 1–2 of revision 1 are closed by the spec's Gap log (2026-11-07).

## Conventions for this module

**IDs.** `FAL` = `app/dao/financial_audit_log.py`. `BE` `get_by_entity` · `RL` `get_related_logs` · `AT` `get_by_action_type` · `BU` `get_by_user` · `DR` `get_by_date_range` · `RC` `get_recent_logs` · `N` model fact N1.

**Actors and fixed values.**
- `dao` = `financial_audit_log_dao` (`from app.dao.financial_audit_log import financial_audit_log_dao`). `FinancialAuditLog` = `app.models.financial_audit_log.FinancialAuditLog`. `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `datetime`, `timedelta`, `timezone` = the `datetime` module's. `TypeError` = the builtin. `text` = `sqlalchemy.text`. `DataError` = `sqlalchemy.exc.DataError`. `utcnow` = `app.utils.time.utcnow`. US = `timedelta(microseconds=1)`. PLUS6 = `timezone(timedelta(hours=6))`.
- MISSING = `999999999`. T9, T10, T11, T12 = `datetime(2026, 3, 4, 9, 0, 0)` … `datetime(2026, 3, 4, 12, 0, 0)` (naive UTC).
- **zone(z)** = the step `db.execute(text(f"SET LOCAL TIME ZONE '{z}'"))`.

**Externals.** None. Nothing is mocked.

**Standing rows** (every test, this order, no Given line): W0, W1, W2 = `make_workspace(db)` three times (`W0.id < W1.id < W2.id`); U1, U2, U3 = `make_profile(db)` three times (`U1.id < U2.id < U3.id`). No log row exists unless the Given builds it.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. After "but" a line lists every column that differs. A line written as code is a step to run exactly.
- **log** = `FinancialAuditLog(workspace_id=W1.id, entity_type="invoice", entity_id=10, action_type="created", performed_by=U1.id)`; the card always gives `performed_at`.
- **payment row** = log, but `entity_type "payment"`, `entity_id 7`, `related_entity_type "invoice"`, `related_entity_id 10`, and what the card lists.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, order part of the check. **idset(result)** = `{r.id for r in result}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **nothing written** = the number of `financial_audit_logs` rows (all workspaces) equals its value before the call.
- `pending:` lines check P after the call. `session:` lines check the session directly after the call.
- `raises: DataError` = `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the When; later `raises:` lines assert on `exc.value`.
- **Statement recorder** = the SQL the session sends during the When is recorded. `sql` = the one `SELECT` sent; `order_part` = the text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **writes-nothing setup** = the three steps `B = ` log with `performed_at T9`, but `workspace_id W2.id`; `B.description = "Edited"` (not flushed); `P = FinancialAuditLog(workspace_id=W1.id, entity_type="invoice", entity_id=10, action_type="created", performed_by=U1.id, performed_at=T12)`, `db.add(P)` (not flushed).

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and checks exactly as shown; never weaken a non-strict assertion.

**Race simulations.** None.

## `FinancialAuditLogDAO.get_by_entity`

### FAL-BE-01 — the entity's rows, newest first
- **Rules:** `get_by_entity` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = log, `performed_at T11`, but `action_type "status_changed"`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `isinstance(result[0], FinancialAuditLog)`.

### FAL-BE-02 — rows of a lower and a higher entity id are not returned
- **Rules:** `get_by_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = log, `performed_at T12`, but `entity_id 9`.
2. A = log, `performed_at T10`.
3. Y = log, `performed_at T12`, but `entity_id 11`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-BE-03 — a row of another type with the same id is not returned
- **Rules:** `get_by_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. X = log, `performed_at T12`, but `entity_type "payment"`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-BE-04 — a row naming the entity only as its related entity is not returned
- **Rules:** `get_by_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. X = payment row, `performed_at T12`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-BE-05 — rows of an earlier and a later workspace are not returned
- **Rules:** `get_by_entity` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, `performed_at T12`, but `workspace_id W0.id`.
2. A = log, `performed_at T10`.
3. Y = log, `performed_at T12`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-BE-06 — an unknown workspace returns an empty list
- **Rules:** `get_by_entity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### FAL-BE-07 — "Invoice" in capitals finds nothing
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="Invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-BE-08 — an empty type finds nothing
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-BE-09 — part of the type finds nothing
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="voic", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-BE-10 — `_` is no wildcard in the type
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="inv_ice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-BE-11 — a leading space in the type finds nothing
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type=" invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-BE-12 — a stored type with a leading space is not found: the stored side is not trimmed
- **Rules:** `get_by_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `entity_type " invoice"`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-BE-13 — rows come newest first, whatever their ids and actions
- **Rules:** `get_by_entity` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type "updated"`.
2. B = log, `performed_at T12`, but `action_type "created"`.
3. C = log, `performed_at T11`, but `action_type "voided"`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### FAL-BE-14 — the order is applied before the page is cut
- **Rules:** `get_by_entity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = log, `performed_at T12`.
3. C = log, `performed_at T11`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### FAL-BE-15 — on a tie both rows are returned, between the newer and the older
- **Rules:** `get_by_entity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T11`.
3. C = log, `performed_at T12`.
4. D = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### FAL-BE-16 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_entity` R4 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical row order decides)

**Given**
1. A = log, `performed_at T11`, but `action_type "voided"`.
2. B = log, `performed_at T11`, but `action_type "updated"`.
3. C = log, `performed_at T11`, but `action_type "created"`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### FAL-BE-17 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_entity` R4 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370 (non-strict)
- **Fails today on:** Then 2 (the spec saw one row twice and one never)

**Given**
1. A, B, C, D, E = five logs, built in that order, each `performed_at T11`.
2. `A.description = "Edited"`, then `db.flush()`.
3. `db.expire_all()`

**When**
- `pages = [dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [E.id, D.id, C.id, B.id, A.id]`.

### FAL-BE-18 — the query orders by performed_at, then id, both descending
- **Rules:** `get_by_entity` R4 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370
- **Fails today on:** Then 4 (the query orders by `performed_at` alone)

**Given**
1. A = log, `performed_at T10`.
2. Statement recorder.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"performed_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("performed_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### FAL-BE-19 — skip and limit cut a window
- **Rules:** `get_by_entity` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T12`.
2. B = log, `performed_at T11`.
3. C = log, `performed_at T10`.
4. D = log, `performed_at T9`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### FAL-BE-20 — with the defaults 101 rows give the newest 100
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### FAL-BE-21 — limit=1000 gives all 101
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### FAL-BE-22 — limit=0 returns an empty list
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FAL-BE-23 — limit=1 returns one row
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-BE-24 — skip past the end returns an empty list
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### FAL-BE-25 — skip at the last row returns it
- **Rules:** `get_by_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T10`.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### FAL-BE-26 — a negative limit raises
- **Rules:** `get_by_entity` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.

**When**
- `dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FAL-BE-27 — a negative skip raises
- **Rules:** `get_by_entity` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.

**When**
- `dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FAL-BE-28 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_by_entity` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. `P = FinancialAuditLog(workspace_id=W1.id, entity_type="invoice", entity_id=10, action_type="created", performed_by=U1.id, performed_at=T12)`
3. `db.add(P)` (not flushed).
4. Statement recorder.

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. statement: `written == []`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).

### FAL-BE-29 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_entity` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = log, `performed_at T9`, but `workspace_id W2.id`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## `FinancialAuditLogDAO.get_related_logs`

### FAL-RL-01 — an invoice's own rows and its payments' rows, newest first
- **Rules:** `get_related_logs` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type "status_changed"`.
2. P1 = payment row, `performed_at T11`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [P1.id, A.id]`.

### FAL-RL-02 — a row that is both the entity's own and related to it is returned once
- **Rules:** `get_related_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `related_entity_type "invoice"`, `related_entity_id 10`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-RL-03 — one level only: an account's invoice and that invoice's payment are not returned
- **Rules:** `get_related_logs` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. C = log, `performed_at T9`, but `entity_type "account"`, `entity_id 5`.
2. I = log, `performed_at T10`.
3. P1 = payment row, `performed_at T11`.

**When**
- `result = dao.get_related_logs(db, entity_type="account", entity_id=5, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### FAL-RL-04 — both halves need type and id: other types and lower or higher ids are not returned
- **Rules:** `get_related_logs` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T9`.
2. X1 = log, `performed_at T12`, but `entity_type "payment"` (entity 10, no related entity).
3. X2 = payment row, `performed_at T12`, but `related_entity_type "account"`.
4. X3 = payment row, `performed_at T12`, but `related_entity_id 9`.
5. X4 = payment row, `performed_at T12`, but `related_entity_id 11`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-RL-05 — own and related rows of an earlier and a later workspace are not returned
- **Rules:** `get_related_logs` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X1 = log, `performed_at T12`, but `workspace_id W0.id`.
2. X2 = payment row, `performed_at T12`, but `workspace_id W0.id`.
3. A = log, `performed_at T10`.
4. Y1 = log, `performed_at T12`, but `workspace_id W2.id`.
5. Y2 = payment row, `performed_at T12`, but `workspace_id W2.id`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-RL-06 — "Invoice" in capitals finds neither own nor related rows
- **Rules:** `get_related_logs` R4 (exact compare)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. P1 = payment row, `performed_at T11`.

**When**
- `result = dao.get_related_logs(db, entity_type="Invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-RL-07 — a stored related type in capitals, or with a leading space, is not matched
- **Rules:** `get_related_logs` R4 (exact compare, stored side)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T9`.
2. X1 = payment row, `performed_at T11`, but `related_entity_type "Invoice"`.
3. X2 = payment row, `performed_at T12`, but `related_entity_type " invoice"`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-RL-08 — the combined rows come newest first, whatever their ids
- **Rules:** `get_related_logs` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. P1 = payment row, `performed_at T12`.
3. B = log, `performed_at T11`, but `action_type "updated"`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [P1.id, B.id, A.id]`.

### FAL-RL-09 — skip and limit cut a window from the combined, ordered rows
- **Rules:** `get_related_logs` R4, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. P1 = payment row, `performed_at T12`.
3. B = log, `performed_at T11`, but `action_type "updated"`.
4. P2 = payment row, `performed_at T9`, but `entity_id 8`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### FAL-RL-10 — with the defaults 101 rows give the newest 100
- **Rules:** `get_related_logs` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)` when k is odd; payment row, same `performed_at`, when k is even.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### FAL-RL-11 — limit=1000 gives all 101
- **Rules:** `get_related_logs` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 rows E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)` when k is odd; payment row, same `performed_at`, when k is even.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### FAL-RL-12 — limit=0 returns an empty list
- **Rules:** `get_related_logs` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. P1 = payment row, `performed_at T11`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FAL-RL-13 — skip past the end returns an empty list
- **Rules:** `get_related_logs` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. P1 = payment row, `performed_at T11`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### FAL-RL-14 — a negative limit raises
- **Rules:** `get_related_logs` Errors (as `get_by_entity` row 1)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### FAL-RL-15 — a negative skip raises
- **Rules:** `get_related_logs` Errors (as `get_by_entity` row 2)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### FAL-RL-16 — on a tie both rows are returned, between the newer and the older
- **Rules:** `get_related_logs` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. P1 = payment row, `performed_at T11`.
3. C = log, `performed_at T12`, but `action_type "updated"`.
4. D = log, `performed_at T10`, but `action_type "voided"`.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, P1.id}`.
4. returns: `result[3].id == D.id`.

### FAL-RL-17 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_related_logs` R5 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical row order decides)

**Given**
1. A = log, `performed_at T11`.
2. P1 = payment row, `performed_at T11`.
3. C = log, `performed_at T11`, but `action_type "updated"`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, P1.id, A.id]`.

### FAL-RL-18 — the query orders by performed_at, then id, both descending
- **Rules:** `get_related_logs` R5 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370
- **Fails today on:** Then 4 (the query orders by `performed_at` alone)

**Given**
1. A = log, `performed_at T10`.
2. Statement recorder.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"performed_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("performed_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### FAL-RL-19 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `get_related_logs` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. writes-nothing setup.
3. Statement recorder.

**When**
- `result = dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `FinancialAuditLogDAO.get_by_action_type`

### FAL-AT-01 — every row of the action, of any entity type, newest first
- **Rules:** `get_by_action_type` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type "status_changed"`.
2. B = payment row, `performed_at T11`, but `action_type "status_changed"`.
3. C = log, `performed_at T12`, but `entity_type "account"`, `entity_id 5`, `action_type "status_changed"`.
4. X = log, `performed_at T12`, but `action_type "created"`.

**When**
- `result = dao.get_by_action_type(db, action_type="status_changed", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### FAL-AT-02 — the action in capitals finds nothing
- **Rules:** `get_by_action_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type "status_changed"`.

**When**
- `result = dao.get_by_action_type(db, action_type="STATUS_CHANGED", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-AT-03 — part of the action finds nothing
- **Rules:** `get_by_action_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type "status_changed"`.

**When**
- `result = dao.get_by_action_type(db, action_type="tus_chan", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-AT-04 — `_` is no wildcard in the action
- **Rules:** `get_by_action_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type "status_changed"`.

**When**
- `result = dao.get_by_action_type(db, action_type="status_chang_d", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-AT-05 — a leading space in the action finds nothing
- **Rules:** `get_by_action_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type "status_changed"`.

**When**
- `result = dao.get_by_action_type(db, action_type=" status_changed", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-AT-06 — a stored action with a leading space is not found
- **Rules:** `get_by_action_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`, but `action_type " status_changed"`.

**When**
- `result = dao.get_by_action_type(db, action_type="status_changed", workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-AT-07 — rows of an earlier and a later workspace are not returned
- **Rules:** `get_by_action_type` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, `performed_at T12`, but `workspace_id W0.id`.
2. A = log, `performed_at T10`.
3. Y = log, `performed_at T12`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-AT-08 — rows come newest first, whatever their ids
- **Rules:** `get_by_action_type` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = log, `performed_at T12`, but `entity_id 3`.
3. C = log, `performed_at T11`, but `entity_id 20`.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### FAL-AT-09 — on a tie both rows are returned, between the newer and the older
- **Rules:** `get_by_action_type` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T11`.
3. C = log, `performed_at T12`.
4. D = log, `performed_at T10`.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### FAL-AT-10 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_action_type` R3 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical row order decides)

**Given**
1. A = log, `performed_at T11`, but `entity_id 30`.
2. B = log, `performed_at T11`, but `entity_id 20`.
3. C = log, `performed_at T11`, but `entity_id 25`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### FAL-AT-11 — the query orders by performed_at, then id, both descending
- **Rules:** `get_by_action_type` R3 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370
- **Fails today on:** Then 4 (the query orders by `performed_at` alone)

**Given**
1. A = log, `performed_at T10`.
2. Statement recorder.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"performed_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("performed_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### FAL-AT-12 — skip and limit cut a window after the order
- **Rules:** `get_by_action_type` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T12`.
2. B = log, `performed_at T10`.
3. C = log, `performed_at T11`.
4. D = log, `performed_at T9`.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [C.id, B.id]`.

### FAL-AT-13 — with the defaults 101 rows give the newest 100
- **Rules:** `get_by_action_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`, but `entity_id` = `k`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### FAL-AT-14 — limit=1000 gives all 101
- **Rules:** `get_by_action_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`, but `entity_id` = `k`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### FAL-AT-15 — limit=0 returns an empty list
- **Rules:** `get_by_action_type` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FAL-AT-16 — a negative limit raises
- **Rules:** `get_by_action_type` Errors (as `get_by_entity` row 1)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_by_action_type(db, action_type="created", workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### FAL-AT-17 — a negative skip raises
- **Rules:** `get_by_action_type` Errors (as `get_by_entity` row 2)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_by_action_type(db, action_type="created", workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### FAL-AT-18 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `get_by_action_type` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. writes-nothing setup.
3. Statement recorder.

**When**
- `result = dao.get_by_action_type(db, action_type="created", workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `FinancialAuditLogDAO.get_by_user`

### FAL-BU-01 — one person's rows, not those of a lower or a higher user id
- **Rules:** `get_by_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = log, `performed_at T12`, but `performed_by U1.id`.
2. A = log, `performed_at T10`, but `performed_by U2.id`.
3. B = payment row, `performed_at T11`, but `performed_by U2.id`.
4. Y = log, `performed_at T12`, but `performed_by U3.id`.

**When**
- `result = dao.get_by_user(db, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.

### FAL-BU-02 — the same person's rows in an earlier and a later workspace are not returned
- **Rules:** `get_by_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, `performed_at T12`, but `workspace_id W0.id`, `performed_by U2.id`.
2. A = log, `performed_at T10`, but `performed_by U2.id`.
3. Y = log, `performed_at T12`, but `workspace_id W2.id`, `performed_by U2.id`.

**When**
- `result = dao.get_by_user(db, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-BU-03 — an unknown user returns an empty list
- **Rules:** `get_by_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_user(db, user_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-BU-04 — rows come newest first, whatever their ids
- **Rules:** `get_by_user` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = log, `performed_at T12`, but `entity_id 3`.
3. C = log, `performed_at T11`, but `entity_id 20`.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### FAL-BU-05 — on a tie both rows are returned, between the newer and the older
- **Rules:** `get_by_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T11`.
3. C = log, `performed_at T12`.
4. D = log, `performed_at T10`.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### FAL-BU-06 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_user` R3 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical row order decides)

**Given**
1. A = log, `performed_at T11`, but `action_type "voided"`.
2. B = log, `performed_at T11`, but `action_type "updated"`.
3. C = log, `performed_at T11`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### FAL-BU-07 — the query orders by performed_at, then id, both descending
- **Rules:** `get_by_user` R3 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370
- **Fails today on:** Then 4 (the query orders by `performed_at` alone)

**Given**
1. A = log, `performed_at T10`.
2. Statement recorder.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"performed_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("performed_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### FAL-BU-08 — skip and limit cut a window after the order
- **Rules:** `get_by_user` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T12`.
2. B = log, `performed_at T10`.
3. C = log, `performed_at T11`.
4. D = log, `performed_at T9`.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [C.id, B.id]`.

### FAL-BU-09 — with the defaults 101 rows give the newest 100
- **Rules:** `get_by_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### FAL-BU-10 — limit=1000 gives all 101
- **Rules:** `get_by_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### FAL-BU-11 — limit=0 returns an empty list
- **Rules:** `get_by_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FAL-BU-12 — a negative limit raises
- **Rules:** `get_by_user` Errors (as `get_by_entity` row 1)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### FAL-BU-13 — a negative skip raises
- **Rules:** `get_by_user` Errors (as `get_by_entity` row 2)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### FAL-BU-14 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `get_by_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. writes-nothing setup.
3. Statement recorder.

**When**
- `result = dao.get_by_user(db, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `FinancialAuditLogDAO.get_by_date_range`

### FAL-DR-01 — rows between two naive bounds, both inclusive, newest first
- **Rules:** `get_by_date_range` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. X = log, `performed_at T9`.
2. A = log, `performed_at T10`.
3. B = log, `performed_at T11`.
4. Y = log, `performed_at T12`.

**When**
- `result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.

### FAL-DR-02 — one microsecond outside either bound is not returned
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = log, `performed_at T10 - US`.
2. A = log, `performed_at T10`.
3. Y = log, `performed_at T11 + US`.

**When**
- `result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-03 — start equal to end returns the row at that moment
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. X = log, `performed_at T11`.

**When**
- `result = dao.get_by_date_range(db, start_date=T10, end_date=T10, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-04 — start after end returns an empty list, no error
- **Rules:** `get_by_date_range` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = log, `performed_at T11`.

**When**
- `result = dao.get_by_date_range(db, start_date=T11, end_date=T10, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FAL-DR-05 — rows of an earlier and a later workspace in the range are not returned
- **Rules:** `get_by_date_range` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, `performed_at T11`, but `workspace_id W0.id`.
2. A = log, `performed_at T10`.
3. Y = log, `performed_at T11`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-06 — naive bounds mean UTC, also under Asia/Dhaka
- **Rules:** `get_by_date_range` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. zone('Asia/Dhaka').
2. A = log, `performed_at T12`.

**When**
- `result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 11, 30), end_date=datetime(2026, 3, 4, 12, 30), workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-07 — UTC-aware bounds find the moment under UTC
- **Rules:** `get_by_date_range` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. zone('UTC').
2. A = log, `performed_at T12`.

**When**
- `result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 11, 30, tzinfo=timezone.utc), end_date=datetime(2026, 3, 4, 12, 30, tzinfo=timezone.utc), workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-08 — +06:00 bounds find the same moment under UTC
- **Rules:** `get_by_date_range` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. zone('UTC').
2. A = log, `performed_at T12`.

**When**
- `result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 17, 30, tzinfo=PLUS6), end_date=datetime(2026, 3, 4, 18, 30, tzinfo=PLUS6), workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-09 — UTC-aware bounds name the moment under Asia/Dhaka: the 12:00 row, not the 18:00 one
- **Rules:** `get_by_date_range` R3 [BUG-2371]
- **Kind:** bug
- **Expect:** xfail BUG-2371
- **Fails today on:** Then 1 (the bounds are read as Dhaka time, 17:30–18:30 stored, so X is returned instead of A)

**Given**
1. zone('Asia/Dhaka').
2. A = log, `performed_at T12`.
3. X = log, `performed_at datetime(2026, 3, 4, 18, 0, 0)`.

**When**
- `result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 11, 30, tzinfo=timezone.utc), end_date=datetime(2026, 3, 4, 12, 30, tzinfo=timezone.utc), workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-10 — +06:00 bounds name the moment under America/New_York
- **Rules:** `get_by_date_range` R3 [BUG-2371]
- **Kind:** bug
- **Expect:** xfail BUG-2371
- **Fails today on:** Then 1 (the bounds are read as New York time, 06:30–07:30 stored, so nothing is found)

**Given**
1. zone('America/New_York').
2. A = log, `performed_at T12`.

**When**
- `result = dao.get_by_date_range(db, start_date=datetime(2026, 3, 4, 17, 30, tzinfo=PLUS6), end_date=datetime(2026, 3, 4, 18, 30, tzinfo=PLUS6), workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-DR-11 — rows come newest first, whatever their ids
- **Rules:** `get_by_date_range` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = log, `performed_at T12`.
3. C = log, `performed_at T11`.

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### FAL-DR-12 — on a tie both rows are returned, between the newer and the older
- **Rules:** `get_by_date_range` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T11`.
3. C = log, `performed_at T12`.
4. D = log, `performed_at T10`.

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### FAL-DR-13 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_date_range` R5 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; physical row order decides)

**Given**
1. A = log, `performed_at T11`, but `action_type "voided"`.
2. B = log, `performed_at T11`, but `action_type "updated"`.
3. C = log, `performed_at T11`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### FAL-DR-14 — the query orders by performed_at, then id, both descending
- **Rules:** `get_by_date_range` R5 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370
- **Fails today on:** Then 4 (the query orders by `performed_at` alone)

**Given**
1. A = log, `performed_at T10`.
2. Statement recorder.

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"performed_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("performed_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### FAL-DR-15 — the range is applied before the page, and skip and limit cut a window
- **Rules:** `get_by_date_range` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = log, `performed_at datetime(2026, 3, 4, 13, 0, 0)`.
2. A = log, `performed_at T12`.
3. B = log, `performed_at T11`.
4. C = log, `performed_at T10`.

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### FAL-DR-16 — with the defaults 101 rows give the newest 100
- **Rules:** `get_by_date_range` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(seconds=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### FAL-DR-17 — limit=1000 gives all 101
- **Rules:** `get_by_date_range` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(seconds=k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_date_range(db, start_date=T10, end_date=T11, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### FAL-DR-18 — limit=0 returns an empty list
- **Rules:** `get_by_date_range` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FAL-DR-19 — a negative limit raises
- **Rules:** `get_by_date_range` Errors (as `get_by_entity` row 1)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### FAL-DR-20 — a negative skip raises
- **Rules:** `get_by_date_range` Errors (as `get_by_entity` row 2)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### FAL-DR-21 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `get_by_date_range` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. writes-nothing setup.
3. Statement recorder.

**When**
- `result = dao.get_by_date_range(db, start_date=T9, end_date=T12, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `FinancialAuditLogDAO.get_recent_logs`

### FAL-RC-01 — the workspace's rows, newest first, whatever their ids
- **Rules:** `get_recent_logs` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. B = payment row, `performed_at T12`.
3. C = log, `performed_at T11`, but `entity_type "account"`, `entity_id 5`.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, C.id, A.id]`.

### FAL-RC-02 — newer rows of an earlier and a later workspace are not returned
- **Rules:** `get_recent_logs` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. X = log, `performed_at T12`, but `workspace_id W0.id`.
2. A = log, `performed_at T10`.
3. Y = log, `performed_at T12`, but `workspace_id W2.id`.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-RC-03 — with the default 51 rows give the newest 50
- **Rules:** `get_recent_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 logs E1 … E51, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`.
2. `newest` = the ids of E51, E50, … E1, in that order.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 50`.
2. returns: `ids(result) == newest[:50]`.

### FAL-RC-04 — limit=1000 gives all 51
- **Rules:** `get_recent_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 logs E1 … E51, built with `add_all` then one flush: Ek = log, `performed_at` = `T10 + timedelta(minutes=k)`.
2. `newest` = the ids of E51, E50, … E1, in that order.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 51`.
2. returns: `ids(result) == newest`.

### FAL-RC-05 — limit=0 returns an empty list
- **Rules:** `get_recent_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FAL-RC-06 — limit=1 returns the newest row
- **Rules:** `get_recent_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T10`.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### FAL-RC-07 — a negative limit raises
- **Rules:** `get_recent_logs` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.

**When**
- `dao.get_recent_logs(db, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### FAL-RC-08 — on a tie both rows are returned, between the newer and the older
- **Rules:** `get_recent_logs` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T11`.
3. C = log, `performed_at T12`.
4. D = log, `performed_at T10`.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### FAL-RC-09 — with a tie at the cut-off, the latest two are the two highest ids
- **Rules:** `get_recent_logs` R2 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; which rows fall inside the cut is not fixed)

**Given**
1. A = log, `performed_at T11`.
2. B = log, `performed_at T11`.
3. C = log, `performed_at T11`.
4. `A.description = "Edited"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [C.id, B.id]`.

### FAL-RC-10 — the query orders by performed_at, then id, both descending
- **Rules:** `get_recent_logs` R2 [BUG-2370]
- **Kind:** bug
- **Expect:** xfail BUG-2370
- **Fails today on:** Then 4 (the query orders by `performed_at` alone)

**Given**
1. A = log, `performed_at T10`.
2. Statement recorder.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"performed_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("performed_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### FAL-RC-11 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `get_recent_logs` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. writes-nothing setup.
3. Statement recorder.

**When**
- `result = dao.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

### FAL-RC-12 — a `skip` keyword raises TypeError before any query
- **Rules:** `get_recent_logs` R1a
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at T10`.
2. Statement recorder.

**When**
- `dao.get_recent_logs(db, workspace_id=W1.id, skip=1)`, inside `with pytest.raises(TypeError) as exc:`.

**Then**
1. raises: `"got an unexpected keyword argument 'skip'" in str(exc.value)` (contains).
2. statement: no statement was sent during the When (the recorder holds 0 statements).
3. nothing written: nothing written.

## Model fact N1 (`performed_at` default)

### FAL-N-01 — a row flushed without performed_at gets a value
- **Rules:** N1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `A = FinancialAuditLog(workspace_id=W1.id, entity_type="invoice", entity_id=10, action_type="created", performed_by=U1.id)` (no `performed_at`).

**When**
- `db.add(A); db.flush(); db.refresh(A)` (one step).

**Then**
1. re-read A: `performed_at is not None`.

### FAL-N-02 — a row flushed without performed_at gets naive UTC, whatever the database's time zone
- **Rules:** N1 [BUG-2372]
- **Kind:** bug
- **Expect:** xfail BUG-2372
- **Fails today on:** Then 2 (today the database's local `now()`, six hours ahead under `Asia/Dhaka`, and the transaction start, before `before`)

**Given**
1. zone('Asia/Dhaka').
2. `A = FinancialAuditLog(workspace_id=W1.id, entity_type="invoice", entity_id=10, action_type="created", performed_by=U1.id)` (no `performed_at`).
3. `before = utcnow()`.

**When**
- `db.add(A); db.flush(); db.refresh(A); after = utcnow()` (one step).

**Then**
1. re-read A: `A.performed_at.tzinfo is None`.
2. re-read A: `before <= A.performed_at <= after`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| OQ-23 — who may read the log (owner 2026-11-07: deferred to the permissions work, no bug) | `app/api/v1/endpoints/financial_audit_logs.py` / permissions work (`docs/future/permissions.md`) | access per role, when the permissions work is specified |
| FU-1 (b) — `get_related_logs` docstrings say two levels | DAO and endpoint docstrings | text only, no behaviour |
| FU-1 (c) BUG-2373 — `limit >= 1` on the six endpoints | `FinancialAuditLogService` / endpoints | 422 on `limit=0` |
| `FinancialAuditLogCreate` content (BUG-142, BUG-144) | `tests/unit/utils/audit_logger.spec.md` | what the writer puts in |
| Inherited `BaseDAO` methods (`create` the only one called) | `tests/unit/dao/base.cases.md` | generic behaviour |
| Module singleton | none (no logic) | entry point of every card |

## Spec gaps
None open. Gaps 1–2 of revision 1 were closed by the spec's Gap log (2026-11-07):
- G1: keyword-only parameters stay a note for the test designer by design; no card.
- G2: `get_recent_logs` R1a — `skip=` raises `TypeError` → FAL-RC-12.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_entity` | R1, Returns | FAL-BE-01, BE-02, BE-03, BE-04 |
| | R2 | FAL-BE-05, BE-06 |
| | R3 | FAL-BE-07 … BE-12 |
| | R4 | FAL-BE-13, BE-14, BE-15 |
| | R4 [BUG-2370] | FAL-BE-16, BE-17, BE-18 |
| | R5 | FAL-BE-19 … BE-25 |
| | Errors rows 1, 2 | FAL-BE-26, BE-27 |
| | Side effects | FAL-BE-28, BE-29 |
| `get_related_logs` | R1, Returns | FAL-RL-01, RL-02 |
| | R2 | FAL-RL-03 |
| | R3 | FAL-RL-04 |
| | R4 | FAL-RL-05, RL-06, RL-07, RL-09 … RL-13 |
| | R5 | FAL-RL-08, RL-09, RL-16 |
| | R5 [BUG-2370] | FAL-RL-17, RL-18 |
| | Errors | FAL-RL-14, RL-15 |
| | Side effects | FAL-RL-19 |
| `get_by_action_type` | R1, Returns | FAL-AT-01 … AT-06 |
| | R2 | FAL-AT-07, AT-12 … AT-15 |
| | R3 | FAL-AT-08, AT-09 |
| | R3 [BUG-2370] | FAL-AT-10, AT-11 |
| | Errors | FAL-AT-16, AT-17 |
| | Side effects | FAL-AT-18 |
| `get_by_user` | R1, Returns | FAL-BU-01 |
| | R2 | FAL-BU-02, BU-03, BU-08 … BU-11 |
| | R3 | FAL-BU-04, BU-05 |
| | R3 [BUG-2370] | FAL-BU-06, BU-07 |
| | Errors | FAL-BU-12, BU-13 |
| | Side effects | FAL-BU-14 |
| `get_by_date_range` | R1, Returns | FAL-DR-01, DR-02, DR-03 |
| | R2 | FAL-DR-04 |
| | R3 (holds today) | FAL-DR-06, DR-07, DR-08 |
| | R3 [BUG-2371] | FAL-DR-09, DR-10 |
| | R4 | FAL-DR-05, DR-15 … DR-18 |
| | R5 | FAL-DR-11, DR-12 |
| | R5 [BUG-2370] | FAL-DR-13, DR-14 |
| | Errors | FAL-DR-19, DR-20 |
| | Side effects | FAL-DR-21 |
| `get_recent_logs` | R1, Returns | FAL-RC-01, RC-03 … RC-06 |
| | R2 | FAL-RC-01, RC-08 |
| | R2 [BUG-2370] | FAL-RC-09, RC-10 |
| | R3 | FAL-RC-02 |
| | R1a | FAL-RC-12 |
| | Errors | FAL-RC-07 |
| | Side effects | FAL-RC-11 |
| Model fact | N1 | FAL-N-01 |
| | N1 [BUG-2372] | FAL-N-02 |
