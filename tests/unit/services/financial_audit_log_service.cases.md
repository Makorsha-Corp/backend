# Test cases — `app/services/financial_audit_log_service.py`

> **Spec:** `tests/unit/services/financial_audit_log_service.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-06; revised 2026-11-07). OQ-23 (who may read the log) is answered by the owner: decided in the permissions work, today's behaviour (every active member) stays. No rule of this service depends on it, so there is no pending section here.
> **Revision:** 2 (2026-11-07) — spec apply-review: OQ-23 answered (no bug, no rule changed). Changed: Status, Reviewer summary (No xfail line), the OQ-23 Deferred row. No card added, changed or retired.
> **Revision:** 3 (2026-11-09) — `financial_audit_log_service.verify.md` finding 1 (a service that caps `limit` at its default passed): new FALS-R-06 (52 rows, `limit=51` → 51) and FALS-E-05 (102 rows, `limit=101` → 101). No card changed or retired.
> **Counts:** 24 cases · 24 expected-to-pass · 0 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_recent_logs` 6 · `get_by_entity` 5 · `get_related_logs` 3 · `get_by_action_type` 3 · `get_by_user` 3 · `get_by_date_range` 4.
- **Depth:** lighter target (skill step 1a). Six one-line pass-throughs to `financial_audit_log_dao`, no writes, no money computed. Of the transaction contract only TC6 applies (spec header). Per method: one happy card with rows of W0 (built before W1) and W2 (built after) and rows that differ in the key the method filters on; one card that proves `skip` and `limit` are passed on; one card that proves the default `limit` (101 rows, or 51 for `get_recent_logs`) and, in the same call, TC6; and on `get_recent_logs` and `get_by_entity` one card asking for one more row than the default, so a cap at the default fails (commit / rollback spies, a flushed row of another table still pending after the call).
- **Order:** every row has its own `performed_at`, so no card depends on the tie-break of BUG-2370 (the DAO's bug, carded in `financial_audit_log.cases.md`). Each happy card also compares with a direct DAO call in the same session (spec Notes).
- **No xfail:** BUG-2370, BUG-2371 are the DAO's; BUG-2373 sits in the endpoints (integration-only); OQ-23 (answered 2026-11-07) moves to the permissions work. All Deferred.
- **Notable design choices:** the DAO errors that reach the caller unchanged (R2) are tested once on `get_recent_logs` (negative `limit`, named in its R1) and once on `get_by_entity` (negative `skip`); the other four methods share the same one-line shape and get no error card.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `FALS` = `app/services/financial_audit_log_service.py`. `R` get_recent_logs · `E` get_by_entity · `L` get_related_logs · `A` get_by_action_type · `U` get_by_user · `D` get_by_date_range.

**Actors and fixed values.**
- `svc` = `financial_audit_log_service` (`from app.services.financial_audit_log_service import FinancialAuditLogService, financial_audit_log_service`). `dao` = `financial_audit_log_dao` (`from app.dao.financial_audit_log import financial_audit_log_dao`). `db` = the test's real session, first argument; every other argument by keyword unless the card says "positional". `result` = what the When returns.
- `FinancialAuditLog` (`app.models.financial_audit_log`), `Workspace` (`app.models.workspace`). `DataError` (`sqlalchemy.exc`). `patch` (`unittest.mock`). `datetime`, `timedelta` (`datetime`).
- MISSING = `999999999`. H(k) = `datetime(2026, 4, 1, 9, 0, 0) + timedelta(minutes=k)` (naive UTC).

**Standing rows** (every test, in this order, no Given line): W0, W1, W2 = `make_workspace(db)` three times, so `W0.id < W1.id < W2.id`; then UA, UB, UC = `make_profile(db)` three times, so `UA.id < UB.id < UC.id`. No log row exists unless the Given builds it.

**Given rows.** Inserted directly (never through `svc` or `dao`), flushed one at a time in the order written, so ids rise in that order.
- **log** = `FinancialAuditLog(workspace_id=W1.id, entity_type="invoice", entity_id=10, action_type="updated", performed_by=UB.id, performed_at=…)`. The card always gives `performed_at`; after "but" it lists every other column that differs (`related_entity_type`, `related_entity_id` are not passed otherwise).
- **X** (a pending row of another table, where the card lists it) = `X = make_workspace(db)`, flushed, not committed; `X_ID = X.id`.

**Named checks.**
- **ids(r)** = `[row.id for row in r]`, in the order returned; the order is part of the check.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- `session:` lines check the session directly after the call, before anything expires it.
- **x_gone** = after the test runs `db.rollback()` once (written as its own Then line, after the session lines), `db.get(Workspace, X_ID) is None`.
- `raises: DataError` = `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the When; further `raises:` lines assert on `exc.value` after the block, one `assert` per line.

**xfail cards.** None in this module.

**Race simulations.** None.

## `FinancialAuditLogService.get_recent_logs`

### FALS-R-01 — returns the workspace's latest rows, newest first, as the DAO does
- **Rules:** `get_recent_logs` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = log, `performed_at H(30)`, but `workspace_id W0.id`.
2. A = log, `performed_at H(10)`.
3. B = log, `performed_at H(20)`, but `entity_type "payment"`, `entity_id 7`, `action_type "voided"`, `performed_by UA.id`.
4. Z2 = log, `performed_at H(40)`, but `workspace_id W2.id`.

**When**
- `result = svc.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `ids(result) == ids(dao.get_recent_logs(db, workspace_id=W1.id))`.
4. returns: `isinstance(result[0], FinancialAuditLog)`.

### FALS-R-02 — limit is passed on
- **Rules:** `get_recent_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. B = log, `performed_at H(20)`.
3. C = log, `performed_at H(30)`.

**When**
- `result = svc.get_recent_logs(db, workspace_id=W1.id, limit=2)`.

**Then**
1. returns: `ids(result) == [C.id, B.id]`.

### FALS-R-03 — with no limit, 51 rows give the newest 50; the read neither commits nor rolls back
- **Rules:** `get_recent_logs` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 logs E1 … E51, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E51, E50, … E1, in that order.
3. X.

**When**
- spies: `result = svc.get_recent_logs(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 50`.
2. returns: `ids(result) == newest[:50]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. count: x_gone.

### FALS-R-04 — limit=0 is passed on and returns an empty list
- **Rules:** `get_recent_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.

**When**
- `result = svc.get_recent_logs(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### FALS-R-05 — a negative limit: the DAO's DataError reaches the caller, no rollback by the service
- **Rules:** `get_recent_logs` R1, R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. X.

**When**
- spies, inside the wrap of `raises: DataError`: `svc.get_recent_logs(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. count: x_gone.

### FALS-R-06 — a limit above the default is passed on: 52 rows with limit=51 give the newest 51
- **Rules:** `get_recent_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 52 logs E1 … E52, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E52, E51, … E1, in that order.

**When**
- `result = svc.get_recent_logs(db, workspace_id=W1.id, limit=51)`.

**Then**
1. returns: `len(result) == 51`.
2. returns: `ids(result) == newest[:51]`.

## `FinancialAuditLogService.get_by_entity`

### FALS-E-01 — returns the rows of that entity in the workspace, newest first, as the DAO does
- **Rules:** `get_by_entity` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = log, `performed_at H(50)`, but `workspace_id W0.id`.
2. A = log, `performed_at H(10)`.
3. N1 = log, `performed_at H(60)`, but `entity_id 9`.
4. B = log, `performed_at H(20)`, but `action_type "status_changed"`.
5. N2 = log, `performed_at H(70)`, but `entity_type "payment"`.
6. Z2 = log, `performed_at H(80)`, but `workspace_id W2.id`.

**When**
- `result = svc.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `ids(result) == ids(dao.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id))`.

### FALS-E-02 — skip and limit are passed on; positional arguments work
- **Rules:** `get_by_entity` R1; Facts (positional-or-keyword)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. B = log, `performed_at H(20)`.
3. C = log, `performed_at H(30)`.

**When**
- positional: `result = svc.get_by_entity(db, "invoice", 10, W1.id, 1, 1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### FALS-E-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back
- **Rules:** `get_by_entity` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.
3. X.

**When**
- spies: `result = svc.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. count: x_gone.

### FALS-E-04 — a negative skip: the DAO's DataError reaches the caller, no rollback by the service
- **Rules:** `get_by_entity` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. X.

**When**
- spies, inside the wrap of `raises: DataError`: `svc.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. count: x_gone.

### FALS-E-05 — a limit above the default is passed on: 102 rows with limit=101 give the newest 101
- **Rules:** `get_by_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 102 logs E1 … E102, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E102, E101, … E1, in that order.

**When**
- `result = svc.get_by_entity(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, limit=101)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest[:101]`.

## `FinancialAuditLogService.get_related_logs`

### FALS-L-01 — returns the entity's rows and the rows related to it, in the workspace, as the DAO does
- **Rules:** `get_related_logs` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = log, `performed_at H(50)`, but `workspace_id W0.id`, `entity_type "payment"`, `entity_id 3`, `related_entity_type "invoice"`, `related_entity_id 10`.
2. A = log, `performed_at H(10)`.
3. P = log, `performed_at H(20)`, but `entity_type "payment"`, `entity_id 3`, `action_type "created"`, `related_entity_type "invoice"`, `related_entity_id 10`.
4. N = log, `performed_at H(60)`, but `entity_type "payment"`, `entity_id 10`.
5. Z2 = log, `performed_at H(70)`, but `workspace_id W2.id`.

**When**
- `result = svc.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [P.id, A.id]`.
3. returns: `ids(result) == ids(dao.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id))`.

### FALS-L-02 — skip and limit are passed on
- **Rules:** `get_related_logs` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. B = log, `performed_at H(20)`, but `entity_type "payment"`, `entity_id 3`, `related_entity_type "invoice"`, `related_entity_id 10`.
3. C = log, `performed_at H(30)`.

**When**
- `result = svc.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### FALS-L-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back
- **Rules:** `get_related_logs` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.
3. X.

**When**
- spies: `result = svc.get_related_logs(db, entity_type="invoice", entity_id=10, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. count: x_gone.

## `FinancialAuditLogService.get_by_action_type`

### FALS-A-01 — returns the workspace's rows of that action, newest first, as the DAO does
- **Rules:** `get_by_action_type` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = log, `performed_at H(50)`, but `workspace_id W0.id`, `action_type "voided"`.
2. A = log, `performed_at H(10)`, but `action_type "voided"`.
3. N = log, `performed_at H(60)`.
4. B = log, `performed_at H(20)`, but `entity_type "payment"`, `entity_id 3`, `action_type "voided"`.
5. Z2 = log, `performed_at H(70)`, but `workspace_id W2.id`, `action_type "voided"`.

**When**
- `result = svc.get_by_action_type(db, action_type="voided", workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `ids(result) == ids(dao.get_by_action_type(db, action_type="voided", workspace_id=W1.id))`.

### FALS-A-02 — skip and limit are passed on
- **Rules:** `get_by_action_type` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. B = log, `performed_at H(20)`.
3. C = log, `performed_at H(30)`.

**When**
- `result = svc.get_by_action_type(db, action_type="updated", workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### FALS-A-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back
- **Rules:** `get_by_action_type` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.
3. X.

**When**
- spies: `result = svc.get_by_action_type(db, action_type="updated", workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. count: x_gone.

## `FinancialAuditLogService.get_by_user`

### FALS-U-01 — returns the person's rows in the workspace, newest first, as the DAO does
- **Rules:** `get_by_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = log, `performed_at H(50)`, but `workspace_id W0.id`.
2. NA = log, `performed_at H(60)`, but `performed_by UA.id`.
3. A = log, `performed_at H(10)`.
4. NC = log, `performed_at H(70)`, but `performed_by UC.id`.
5. B = log, `performed_at H(20)`, but `entity_type "account"`, `entity_id 5`, `action_type "created"`.
6. Z2 = log, `performed_at H(80)`, but `workspace_id W2.id`.

**When**
- `result = svc.get_by_user(db, user_id=UB.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `ids(result) == ids(dao.get_by_user(db, user_id=UB.id, workspace_id=W1.id))`.

### FALS-U-02 — skip and limit are passed on
- **Rules:** `get_by_user` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. B = log, `performed_at H(20)`.
3. C = log, `performed_at H(30)`.

**When**
- `result = svc.get_by_user(db, user_id=UB.id, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### FALS-U-03 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back
- **Rules:** `get_by_user` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.
3. X.

**When**
- spies: `result = svc.get_by_user(db, user_id=UB.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. count: x_gone.

## `FinancialAuditLogService.get_by_date_range`

### FALS-D-01 — returns the workspace's rows inside the inclusive range, newest first, as the DAO does
- **Rules:** `get_by_date_range` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = log, `performed_at H(15)`, but `workspace_id W0.id`.
2. N1 = log, `performed_at H(9)`.
3. A = log, `performed_at H(10)`.
4. B = log, `performed_at H(20)`, but `action_type "created"`.
5. N2 = log, `performed_at H(21)`.
6. Z2 = log, `performed_at H(16)`, but `workspace_id W2.id`.

**When**
- `result = svc.get_by_date_range(db, start_date=H(10), end_date=H(20), workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `ids(result) == ids(dao.get_by_date_range(db, start_date=H(10), end_date=H(20), workspace_id=W1.id))`.

### FALS-D-02 — a start after the end is passed on unchecked and returns an empty list
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. B = log, `performed_at H(20)`.

**When**
- `result = svc.get_by_date_range(db, start_date=H(20), end_date=H(10), workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### FALS-D-03 — skip and limit are passed on
- **Rules:** `get_by_date_range` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = log, `performed_at H(10)`.
2. B = log, `performed_at H(20)`.
3. C = log, `performed_at H(30)`.

**When**
- `result = svc.get_by_date_range(db, start_date=H(0), end_date=H(40), workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### FALS-D-04 — with no skip or limit, 101 rows give the newest 100; the read neither commits nor rolls back
- **Rules:** `get_by_date_range` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 logs E1 … E101, built with `add_all` and one flush: Ek = log, `performed_at H(k)`.
2. `newest` = the ids of E101, E100, … E1, in that order.
3. X.

**When**
- spies: `result = svc.get_by_date_range(db, start_date=H(0), end_date=H(200), workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. session: `X in db`.
6. session: `not db.new and not db.dirty and not db.deleted`.
7. count: x_gone.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-2370 — tie-break by `id` on all six readers | `tests/unit/dao/financial_audit_log.cases.md` | the ordering and paging cards, non-strict plus one SQL recorder per query |
| BUG-2371 — aware bounds in `get_by_date_range` | `tests/unit/dao/financial_audit_log.cases.md` | time-zone cards; the service passes the bounds as given |
| DAO filters, exact compares, related-row logic, inclusive bounds | `tests/unit/dao/financial_audit_log.cases.md` | full filter shapes; here one happy card per method checks the pass-through |
| BUG-2373 (HR-7) — `limit >= 1` on the six endpoints | `app/api/v1/endpoints/financial_audit_logs.py` (integration) | 422 for `limit=0` and negative values; the cap of 200 |
| OQ-23 — who may read the log (owner 2026-11-07: decided in the permissions work; today every active member) | permissions work (`docs/future/permissions.md`), `app/api/v1/endpoints/financial_audit_logs.py` (integration) | the access gate when that work defines it; no service rule changes |
| Module singleton `financial_audit_log_service` | none (no logic) | used as the entry point of every card |

## Spec gaps
None. (Revision 1 reported none; nothing open.)

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_recent_logs` | R1 | FALS-R-01, FALS-R-02, FALS-R-03, FALS-R-04, FALS-R-05, FALS-R-06 |
| `get_recent_logs` | R2 (TC6) | FALS-R-03, FALS-R-05 |
| `get_by_entity` | R1 | FALS-E-01, FALS-E-02, FALS-E-03, FALS-E-05 |
| `get_by_entity` | R2 (TC6) | FALS-E-03, FALS-E-04 |
| `get_by_entity` | Facts: positional-or-keyword | FALS-E-02 |
| `get_related_logs` | R1 | FALS-L-01, FALS-L-02, FALS-L-03 |
| `get_related_logs` | R2 (TC6) | FALS-L-03 |
| `get_by_action_type` | R1 | FALS-A-01, FALS-A-02, FALS-A-03 |
| `get_by_action_type` | R2 (TC6) | FALS-A-03 |
| `get_by_user` | R1 | FALS-U-01, FALS-U-02, FALS-U-03 |
| `get_by_user` | R2 (TC6) | FALS-U-03 |
| `get_by_date_range` | R1 | FALS-D-01, FALS-D-02, FALS-D-03, FALS-D-04 |
| `get_by_date_range` | R2 (TC6) | FALS-D-04 |
