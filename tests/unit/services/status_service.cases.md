# Test cases — `app/services/status_service.py`

> **Spec:** `tests/unit/services/status_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — spec Gap log G1–G4 close gaps 1–4. G1 (`delete_status` R4 shape): changed SSV-D-09, D-10, D-11 (now `AppValidationError`, detail `Status is used by orders`, exact `errors` list); new D-17 (sales order), D-18 (blocker order, other-workspace entry last). G2 (`update_status` R4a): changed SSV-U-08, U-09, D-06, D-07, D-08 (exact detail text); new U-20 (two workflows, plural, by id), U-21 (stage status names the purchase workflow row), U-22 (stage status in the purchase sequence named once), U-23 (another workspace's workflow never named). G3 (S2a): new U-19, D-14, D-15 (refusal rolls back first: the uncommitted extra row is gone). G4 (`update_status` R4b): new U-24 (`"receiving"` renamed), D-16 (`" Complete"` deleted); U-12, D-12 now also cite R4b. Conventions: `SalesOrder`, `Account`, `Factory`, `AppValidationError`, sales builder, purchase builder per spec Notes. No card retired. **Fix 2026-11-04** (executor DISCREPANCY-1): SSV-U-20's second workflow G now has `type "STM"`. Two W1 workflows of type `PFM` broke the unique key on `(workspace_id, type)`. `STM` is one of the docstring types the order workflow DAO spec names, and `type` is unvalidated text. The card's intent and Then lines are unchanged. Counts are unchanged.
> **Revision:** 3 (2026-11-04) — from `status_service.verify.md`: R-ST-0 → SSV-L-01 added to the BUG-035 retire list (summary); R-ST-1 → **failing commit** now raises a prebuilt `boom`, and SSV-C-12, U-17, D-13 gain a last Then line `exc.value is boom`; R-ST-2 → new SSV-L-12 (the default `skip=0`: every row of a small table comes back; with BUG-035 it gains `workspace_id=W1.id` and expects 2). No card retired.
> **Revision:** 4 (2026-11-04) — the owner answered OQ-13 (spec revision note): stage names match ignoring capitals and outer spaces (`update_status` R4b, BUG-1880). Changed: SSV-U-24 (`"receiving"`) and SSV-D-16 (`" Complete"`) are now refusals, strict xfail BUG-1880, with the exact detail text. New: SSV-U-25 (rename of `" Receiving "` refused), SSV-D-19 (delete of `"COMPLETE"` refused), both xfail BUG-1880; SSV-U-26 (`"Re ceiving"`, a space inside, is not a stage name: renamed, pass). SSV-U-12, D-12 unchanged. No card retired.
> **Revision:** 5 (2026-11-04) — from `status_service.verify.md` round 3: R-ST-3 → new SSV-D-20 (`"Com plete"`, a space inside, is deleted, pass). The Expect lines of SSV-U-24, U-25, D-16, D-19 now read `xfail BUG-1220, BUG-1880`: both fixes are needed before they pass. No card retired.
> **Counts:** 76 cases · 37 expected-to-pass · 39 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_statuses` 12 (3 bug) · `get_by_id` 5 (1 bug) · `create_status` 13 (9 bug) · `update_status` 26 (13 bug) · `delete_status` 20 (13 bug).
- **Depth:** lighter target (skill step 1a): reference rows, no stock, money or order state written. Every rule and Errors row has a card; the transaction rules S1–S4 get one card per write (S2 failing commit, S3 spies on "not found") and per read (S4); TC5's failing re-read on update (create cannot reach it today).
- **BUG-035 note (as `notification_service.cases.md` did for BUG-1534):** today no method has `workspace_id`. Every card that is not about BUG-035 calls the method as it is today, without it; when the fix lands each gains `workspace_id=W1.id` and nothing else. The five cards that document today's leak or today's failing create (SSV-L-01, SSV-G-04, SSV-C-02, SSV-U-06, SSV-D-04) are retired with the fix. Every create card except SSV-C-02 must pass `workspace_id` to store anything, so it is xfail BUG-035 (or a later bug) and fails today inside the call (`TypeError`).
- **Expected-to-fail:** BUG-035 9, BUG-1221 3, BUG-1680 4, BUG-1681 2 (L-09 non-strict, L-10 strict SQL recorder), BUG-1220 11, BUG-1218 6, BUG-1880 4. All strict except SSV-L-09. The create cards of BUG-1221 also need BUG-035's parameter; they fail today inside the call.
- **Notable design choices:**
  - Without BUG-035's fix the list is a page of the whole table, so list cards compare sets, use **n_all** (all rows at the commit point) for paging, and read W1's rows out of the page for the order card.
  - The protection of BUG-1220 is pinned on both sides with passing cards: a stage status keeps its comment edit and its own name (U-10, U-11), a name that only contains a stage name ("Receiving Bay", "Completed") and a status listed only in another workspace's workflow are not protected (U-12, U-13, D-12).
  - BUG-1218: one card per blocker type (purchase, sales, transfer, other workspace), each with an exact `errors` list, and one card for the order of a full list. Every blocking order sits on a plain status (not a stage name, in no sequence), so BUG-1220 does not answer first (spec Notes).
  - **S2a differs on purpose from the tag services:** a BUG-1220 or BUG-1218 refusal rolls back first, so the uncommitted extra row of U-19, D-14, D-15 must be **gone** (all xfail: the refusals do not exist yet).
  - R4b (OQ-13, BUG-1880): a stage name differing only in capitals or outer spaces is protected (U-24, U-25, D-16, D-19, xfail); a longer name or a space inside is not (`"Receiving Bay"` U-12, `"Re ceiving"` U-26, `"Completed"` D-12, `"Com plete"` D-20, pass); the four refusal cards are xfail on both BUG-1220 and BUG-1880. The detail quotes the stored name as it is.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `SSV` = `app/services/status_service.py`. `L` get_statuses · `G` get_by_id · `C` create_status · `U` update_status · `D` delete_status.

**Actors and fixed values.**
- `svc` = the singleton `status_service` (`from app.services.status_service import StatusService, status_service`). `db` = the test's real session, always the first argument; the rest by keyword. `result` = what the When call returns.
- `Status` (`app.models.status`), `OrderWorkflow` (`app.models.order_workflow`), `TransferOrder` (`app.models.transfer_order`), `PurchaseOrder` (`app.models.purchase_order`), `SalesOrder` (`app.models.sales_order`), `Account` (`app.models.account`), `Factory` (`app.models.factory`), `AppValidationError` = `ValidationError` of `app.core.exceptions` (not pydantic's), `StatusCreate`, `StatusUpdate`, `StatusResponse` (`app.schemas.status`). `PydanticValidationError` = `pydantic.ValidationError`. `HTTPException` (`fastapi`); `IntegrityError`, `DataError`, `DBAPIError` (`sqlalchemy.exc`); `inspect`, `text`, `select`, `func` (`sqlalchemy`); `patch` (`unittest.mock`); `re`.
- W1, W2 = two `workspaces` rows (`make_workspace`), U1 = a `profiles` row (`make_profile`); they exist in every test. Neither workspace is seeded: no status exists unless a Given line builds it. MISSING = `999999999`.

**Externals.** None is mocked.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, ids rising in that order. A Given line written as code is a step to run exactly.
- **status** = `Status(workspace_id=W1.id, name="Feat", comment="A note")`. After "but" the card lists every column that differs. Never two statuses of one workspace with names equal ignoring case and outer spaces (BUG-1221's index), except in the cards about exactly that.
- **transfer on S** = `TransferOrder(workspace_id=W1.id, transfer_number="TO-1", source_location_type="storage", source_location_id=1, destination_location_type="storage", destination_location_id=2, current_status_id=S.id, created_by=U1.id)`.
- **purchase on S** = `PurchaseOrder(workspace_id=W1.id, po_number="PO-1", destination_type="storage", destination_id=1, current_status_id=S.id, created_by=U1.id)`.
- **sales on S** = `SalesOrder(workspace_id=W1.id, sales_order_number="SO-1", account_id=AC.id, factory_id=FA.id, current_status_id=S.id, created_by=U1.id)`, where AC = `Account(workspace_id=W1.id, name="Acme")` and FA = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`, built just before it in the order written.
- A card's "but" after an order builder lists every column that differs (e.g. `workspace_id W2.id`, `po_number "PO-2"`).
- **Purchase Order** = `'Purchase Order'`, the name a refusal gives when the workspace has no purchase workflow row; neither workspace has one unless the Given builds it.
- **workflow on [ids]** = `OrderWorkflow(workspace_id=W1.id, name="Flow", type="PFM", status_sequence=[ids])`.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted.
- **n_all** = `db.scalar(select(func.count()).select_from(Status))`, taken at the commit point (statuses of every workspace).

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value at the commit point.
- **nothing written** = the number of `statuses` rows (all workspaces) equals n_all.
- `count:` lines count `statuses` rows with a fresh query, with the filter stated. **ids(x)** = `sorted(r.id for r in x)`; **idset(x)** = `{r.id for r in x}`.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `schema:` lines check a model or schema class itself, not a row.
- `session:` lines check `db` itself: "usable" = `db.execute(text("SELECT 1")).scalar() == 1`; "aborted" = `db.execute(text("SELECT 1"))` raises `DBAPIError` (wrap in `pytest.raises`).
- `raises: <Type>`: plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block. A schema card wraps only the schema's construction (target `schema`).
- **failing commit** = `boom = RuntimeError("boom")` built first, then `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=boom), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When (no `rb`).
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (inside any `raises:` wrap); `mock called:` lines check `cm`, `rb` after it.
- `remove` may emit `LegacyAPIWarning`; warnings are not errors here.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the one `SELECT` from `statuses`; `order_part` = the text of `sql` after `ORDER BY` and before `LIMIT` (`""` when there is none). A `statement:` line is a check on these.

**xfail cards.** Write the call and checks as shown, also when a parameter does not exist yet. Strict unless the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `StatusService.get_statuses`

### SSV-L-01 — today every workspace's statuses are listed (documents BUG-035)
- **Rules:** `get_statuses` R1 (today), R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = status, but `workspace_id W2.id`, `name "Early"`.
2. A = status.
3. Z2 = status, but `workspace_id W2.id`, `name "Late"`.

**When**
- `result = svc.get_statuses(db, skip=0, limit=n_all)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `{Z1.id, A.id, Z2.id} <= idset(result)`.
3. returns: `len(result) == n_all`.

### SSV-L-02 — only the caller's workspace's statuses are listed
- **Rules:** `get_statuses` R1 [BUG-035]
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. Z1 = status, but `workspace_id W2.id`, `name "Early"`.
2. A = status.
3. B = status, but `name "Beta"`.
4. Z2 = status, but `workspace_id W2.id`, `name "Late"`.

**When**
- `result = svc.get_statuses(db, workspace_id=W1.id, skip=0, limit=1000)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### SSV-L-03 — limit=0 gives an empty list
- **Rules:** `get_statuses` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Beta"`.

**When**
- `result = svc.get_statuses(db, skip=0, limit=0)`.

**Then**
1. returns: `result == []`.

### SSV-L-04 — limit=1 gives one status
- **Rules:** `get_statuses` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Beta"`.

**When**
- `result = svc.get_statuses(db, skip=0, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### SSV-L-05 — with the default skip and limit, 101 statuses give 100
- **Rules:** `get_statuses` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 statuses, by `add_all`: k = 0 … 100, status, but `name f"s{k:03d}"`.

**When**
- `result = svc.get_statuses(db)`.

**Then**
1. returns: `len(result) == 100`.

### SSV-L-06 — skip leaves out that many rows: skip=n_all-1 with limit=1000 gives one
- **Rules:** `get_statuses` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Beta"`.

**When**
- `result = svc.get_statuses(db, skip=n_all - 1, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### SSV-L-07 — a negative limit raises DataError and leaves the session aborted
- **Rules:** `get_statuses` R2, R4, Errors; S4
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status.

**When**
- `svc.get_statuses(db, skip=0, limit=-1)`.

**Then**
1. raises: `DataError`.
2. session: aborted.

### SSV-L-08 — a negative skip raises DataError
- **Rules:** `get_statuses` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status.

**When**
- `svc.get_statuses(db, skip=-1, limit=10)`.

**Then**
1. raises: `DataError`.

### SSV-L-09 — statuses come by name, case-insensitive ascending
- **Rules:** `get_statuses` R3 [BUG-1681]
- **Kind:** bug
- **Expect:** xfail BUG-1681 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (no order is asked for; insertion order usually comes back)

**Given**
1. Z = status, but `name "zeta"`.
2. A = status, but `name "Alpha"`.
3. B = status, but `name "beta"`.

**When**
- `result = svc.get_statuses(db, skip=0, limit=n_all)`.

**Then**
1. returns: `{Z.id, A.id, B.id} <= idset(result)`.
2. returns: `[r.name for r in result if r.workspace_id == W1.id] == ["Alpha", "beta", "zeta"]`.

### SSV-L-10 — the query orders by lower(name), then id last, before the page
- **Rules:** `get_statuses` R3 [BUG-1681]
- **Kind:** bug
- **Expect:** xfail BUG-1681
- **Fails today on:** Then 2 (the query does not order by name: `order_part` has no `lower(`)

**Given**
1. A = status.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = svc.get_statuses(db, skip=0, limit=10)`.

**Then**
1. returns: `isinstance(result, list)`.
2. statement: `"lower(" in order_part.lower()`.
3. statement: `"ORDER BY" in sql`.
4. statement: `order_part.lower().index("name") < order_part.lower().index(".id")`.
5. statement: `re.search(r"\.id(\s+asc)?\s*$", order_part, re.IGNORECASE) is not None`.
6. statement: `sql.index("ORDER BY") < sql.index("LIMIT")`.

### SSV-L-11 — the list neither commits nor rolls back
- **Rules:** `get_statuses` R4; S4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Other"`.
3. P = status, but `name "Pending"` (after the commit point).
4. `B.comment = "Changed"` (after the commit point, not flushed).

**When**
- `result = svc.get_statuses(db, skip=0, limit=n_all + 1)`, with **spies**.

**Then**
1. returns: `{A.id, P.id} <= idset(result)`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `B in db.dirty`.
5. committed: `statuses` rows with `name == "Pending"`: exactly 0.

### SSV-L-12 — with no skip given, the list starts at the first row
- **Rules:** `get_statuses` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Beta"`.

**When**
- `result = svc.get_statuses(db)`.

**Then**
1. returns: `n_all <= 100` (a precondition of the card).
2. returns: `len(result) == n_all`.

## `StatusService.get_by_id`

### SSV-G-01 — the status with that id is returned
- **Rules:** `get_by_id` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Other"`.

**When**
- `result = svc.get_by_id(db, status_id=A.id)`.

**Then**
1. returns: `isinstance(result, Status)`.
2. returns: `result.id == A.id`, `result.name == "Feat"`, `result.comment == "A note"`.

### SSV-G-02 — id 0 returns None, no error
- **Rules:** `get_by_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = svc.get_by_id(db, status_id=0)`.

**Then**
1. returns: `result is None`.

### SSV-G-03 — the read neither commits nor rolls back; an unknown id returns None
- **Rules:** `get_by_id` R2, R4; S4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Other"`.
3. P = status, but `name "Pending"` (after the commit point).
4. `B.comment = "Changed"` (after the commit point, not flushed).

**When**
- `result = svc.get_by_id(db, status_id=MISSING)`, with **spies**.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `B in db.dirty`.
5. committed: `statuses` rows with `name == "Pending"`: exactly 0.

### SSV-G-04 — today another workspace's status is returned (documents BUG-035)
- **Rules:** `get_by_id` R3 (today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status.
2. Z = status, but `workspace_id W2.id`, `name "Far"`.

**When**
- `result = svc.get_by_id(db, status_id=Z.id)`.

**Then**
1. returns: `result.id == Z.id`, `result.workspace_id == W2.id`.

### SSV-G-05 — another workspace's status is not found
- **Rules:** `get_by_id` R3 [BUG-035]
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. A = status.
2. Z = status, but `workspace_id W2.id`, `name "Far"`.

**When**
- `result = svc.get_by_id(db, status_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `StatusService.create_status`

### SSV-C-01 — a new status is stored in the caller's workspace, committed and returned re-read
- **Rules:** `create_status` R1, Returns [BUG-035]; S1
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. W1 has no statuses.

**When**
- `result = svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=W1.id)`.

**Then**
1. loaded: `id`, `name`, `comment`, `workspace_id`.
2. returns: `isinstance(result, Status)`.
3. returns: `result.workspace_id == W1.id`, `result.name == "Feat"`, `result.comment == "A note"`.
4. committed: the row with `id == result.id`: `workspace_id == W1.id`, `name == "Feat"`, `comment == "A note"`.
5. committed: `statuses` rows of W1: exactly 1.

### SSV-C-02 — today every create fails on workspace_id, is rolled back, and discards other changes (documents BUG-035)
- **Rules:** `create_status` R1 (today), R6; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status, but `name "Other"`.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"))`, with **spies**, inside the `raises:` wrap.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23502"`.
3. raises: `"workspace_id" in str(exc.value.orig)`.
4. mock called: `rb.call_count >= 1`.
5. mock called: `cm.call_count == 0`.
6. count: `statuses` rows with `name == "Feat"`: exactly 0.
7. count: `statuses` rows with `name == "Extra"`: exactly 0.
8. unchanged: unchanged(A).
9. session: usable.

### SSV-C-03 — no acting user or audit column exists on statuses
- **Rules:** `create_status` R2; `update_status` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no statuses.

**When**
- read the columns of `Status.__table__` (target `schema`).

**Then**
1. schema: `{c.name for c in Status.__table__.columns} == {"id", "workspace_id", "name", "comment"}`.

### SSV-C-04 — comment is required by StatusCreate
- **Rules:** `create_status` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no statuses.

**When**
- build `StatusCreate.model_validate({"name": "Feat"})` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### SSV-C-05 — an empty comment is stored
- **Rules:** `create_status` R3 [BUG-035]
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. W1 has no statuses.

**When**
- `result = svc.create_status(db, status_in=StatusCreate(name="Feat", comment=""), workspace_id=W1.id)`.

**Then**
1. returns: `result.comment == ""`.
2. committed: the row with `id == result.id` has `comment == ""`.

### SSV-C-06 — a whitespace-only name is refused by StatusCreate
- **Rules:** `create_status` R4 [BUG-1680], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1680
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. W1 has no statuses.

**When**
- build `StatusCreate(name="   ", comment="A note")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. nothing written: nothing written.

### SSV-C-07 — StatusCreate trims the name
- **Rules:** `create_status` R4 [BUG-1680]
- **Kind:** bug
- **Expect:** xfail BUG-1680
- **Fails today on:** Then 1 (the name keeps its spaces)

**Given**
1. W1 has no statuses.

**When**
- `data = StatusCreate(name=" Feat ", comment="A note")` (target `schema`).

**Then**
1. returns: `data.name == "Feat"`.

### SSV-C-08 — the response schema still reads a blank name
- **Rules:** `create_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no statuses.

**When**
- `data = StatusResponse(id=1, name="   ", comment="A note")` (target `schema`).

**Then**
1. returns: `data.name == "   "`.

### SSV-C-09 — a name already used in the workspace is refused after the rollback; other changes go too
- **Rules:** `create_status` R5 [BUG-1221], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1221
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet; after BUG-035, no error: a second "Feat" is stored)

**Given**
1. A = status.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.create_status(db, status_in=StatusCreate(name="Feat", comment="Again"), workspace_id=W1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `statuses` rows of W1 with `name == "Feat"`: exactly 1.
4. count: `statuses` rows with `name == "Extra"`: exactly 0.
5. unchanged: unchanged(A).
6. session: usable.

### SSV-C-10 — the same name in capitals and with spaces collides too
- **Rules:** `create_status` R5 [BUG-1221], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1221
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet; after BUG-035, no error: `" FEAT "` is stored)

**Given**
1. A = status.

**When**
- `svc.create_status(db, status_in=StatusCreate(name=" FEAT ", comment="Again"), workspace_id=W1.id)`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. count: `statuses` rows of W1: exactly 1.

### SSV-C-11 — the same name in another workspace is stored
- **Rules:** `create_status` R5 [BUG-035]
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. Z = status, but `workspace_id W2.id`.

**When**
- `result = svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=W1.id)`.

**Then**
1. returns: `result.workspace_id == W1.id`.
2. committed: `statuses` rows with `name == "Feat"`: exactly 2.
3. committed: re-read Z: `workspace_id == W2.id`, `name == "Feat"`.

### SSV-C-12 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `create_status` R6 [BUG-035]; S2
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. A = status, but `name "Other"`.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=W1.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. count: `statuses` rows with `name == "Feat"`: exactly 0.
4. count: `statuses` rows with `name == "Extra"`: exactly 0.
5. raises: `exc.value is boom`.

### SSV-C-13 — a failing re-read after the commit leaves the status saved
- **Rules:** `create_status` R6 [BUG-035]; S1
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. W1 has no statuses.

**When**
- `svc.create_status(db, status_in=StatusCreate(name="Feat", comment="A note"), workspace_id=W1.id)`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: `statuses` rows of W1 with `name == "Feat"`: exactly 1.

## `StatusService.update_status`

### SSV-U-01 — name and comment are written, committed and returned re-read
- **Rules:** `update_status` R3, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = svc.update_status(db, status_id=A.id, status_in=StatusUpdate(name="Done", comment="Finished"))`.

**Then**
1. loaded: `name`, `comment`.
2. returns: `result.id == A.id`, `result.name == "Done"`, `result.comment == "Finished"`.
3. committed: re-read A: `name == "Done"`, `comment == "Finished"`, `workspace_id == W1.id`.

### SSV-U-02 — an omitted name stays
- **Rules:** `update_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = svc.update_status(db, status_id=A.id, status_in=StatusUpdate(comment="Finished"))`.

**Then**
1. returns: `result.comment == "Finished"`.
2. committed: re-read A: `name == "Feat"`, `comment == "Finished"`.

### SSV-U-03 — fields sent as null stay unchanged; the status is returned
- **Rules:** `update_status` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = svc.update_status(db, status_id=A.id, status_in=StatusUpdate(name=None, comment=None))`.

**Then**
1. returns: `result.id == A.id`, `result.name == "Feat"`, `result.comment == "A note"`.
2. unchanged: unchanged(A).

### SSV-U-04 — id 0 returns None, writes nothing, neither commits nor rolls back
- **Rules:** `update_status` R1; S3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `result = svc.update_status(db, status_id=0, status_in=StatusUpdate(name="Done"))`, with **spies**.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `statuses` rows with `name == "Extra"`: exactly 1.
5. unchanged: unchanged(A).
6. committed: `statuses` rows with `name == "Extra"`: exactly 0.

### SSV-U-05 — an unknown id returns None
- **Rules:** `update_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = svc.update_status(db, status_id=MISSING, status_in=StatusUpdate(name="Done"))`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(A).

### SSV-U-06 — today another workspace's status is changed and committed (documents BUG-035)
- **Rules:** `update_status` R2 (today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status.
2. Z = status, but `workspace_id W2.id`, `name "Far"`.

**When**
- `result = svc.update_status(db, status_id=Z.id, status_in=StatusUpdate(name="Hacked"))`.

**Then**
1. returns: `result.id == Z.id`.
2. committed: re-read Z: `name == "Hacked"`, `workspace_id == W2.id`.

### SSV-U-07 — another workspace's status is not found and stays unchanged
- **Rules:** `update_status` R2 [BUG-035]
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. A = status.
2. Z = status, but `workspace_id W2.id`, `name "Far"`.

**When**
- `result = svc.update_status(db, status_id=Z.id, status_in=StatusUpdate(name="Hacked"), workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(Z).

### SSV-U-08 — a purchase order stage status refuses a rename, naming 'Purchase Order'
- **Rules:** `update_status` R4, R4a, R4b [BUG-1220], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status, but `name "Receiving"`.

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Goods in"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status 'Receiving' is used by order workflow 'Purchase Order' and cannot be renamed"`.
4. unchanged: unchanged(S).

### SSV-U-09 — a status in the workspace's workflow sequence refuses a rename, naming the workflow
- **Rules:** `update_status` R4, R4a [BUG-1220], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status.
2. F = workflow on [S.id].

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Done"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status 'Feat' is used by order workflow 'Flow' and cannot be renamed"`.
4. unchanged: unchanged(S).

### SSV-U-10 — a stage status may change its comment
- **Rules:** `update_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = status, but `name "Receiving"`.

**When**
- `result = svc.update_status(db, status_id=S.id, status_in=StatusUpdate(comment="Goods arriving"))`.

**Then**
1. returns: `result.comment == "Goods arriving"`.
2. committed: re-read S: `name == "Receiving"`, `comment == "Goods arriving"`.

### SSV-U-11 — a sequence status may be sent with its current name
- **Rules:** `update_status` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = status.
2. F = workflow on [S.id].

**When**
- `result = svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Feat", comment="Kept"))`.

**Then**
1. returns: `result.name == "Feat"`.
2. committed: re-read S: `name == "Feat"`, `comment == "Kept"`.

### SSV-U-12 — a name that only contains a stage name is not protected
- **Rules:** `update_status` R4, R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = status, but `name "Receiving Bay"`.

**When**
- `result = svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Dock"))`.

**Then**
1. returns: `result.name == "Dock"`.
2. committed: re-read S: `name == "Dock"`.

### SSV-U-13 — a status listed only in another workspace's workflow is not protected
- **Rules:** `update_status` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = status.
2. F9 = workflow on [S.id], but `workspace_id W2.id`.

**When**
- `result = svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Done"))`.

**Then**
1. returns: `result.name == "Done"`.
2. committed: re-read S: `name == "Done"`.

### SSV-U-14 — a whitespace-only new name is refused by StatusUpdate
- **Rules:** `update_status` R6 [BUG-1680], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1680
- **Fails today on:** Then 1 (the schema builds the object)

**Given**
1. A = status.

**When**
- build `StatusUpdate(name="   ")` (target `schema`; `svc` is not called).

**Then**
1. raises: `PydanticValidationError`.
2. unchanged: unchanged(A).

### SSV-U-15 — StatusUpdate trims a new name
- **Rules:** `update_status` R6 [BUG-1680]
- **Kind:** bug
- **Expect:** xfail BUG-1680
- **Fails today on:** Then 1 (the name keeps its spaces)

**Given**
1. W1 has no statuses.

**When**
- `data = StatusUpdate(name=" Done ")` (target `schema`).

**Then**
1. returns: `data.name == "Done"`.

### SSV-U-16 — a rename onto another status's name is refused after the rollback; other changes go too
- **Rules:** `update_status` R7 [BUG-1221], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1221
- **Fails today on:** Then 1 (no error: the rename is stored)

**Given**
1. A = status.
2. B = status, but `name "Other"`.
3. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.update_status(db, status_id=B.id, status_in=StatusUpdate(name=" FEAT "))`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23505"`.
3. unchanged: unchanged(B).
4. count: `statuses` rows with `name == "Extra"`: exactly 0.
5. session: usable.

### SSV-U-17 — a failing commit is rolled back and re-raised; other uncommitted changes go too
- **Rules:** `update_status` R8; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.update_status(db, status_id=A.id, status_in=StatusUpdate(name="Done"))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A).
4. count: `statuses` rows with `name == "Extra"`: exactly 0.
5. raises: `exc.value is boom`.

### SSV-U-18 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_status` R8; S1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status.

**When**
- `svc.update_status(db, status_id=A.id, status_in=StatusUpdate(name="Done"))`, inside **failing refresh**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: re-read A: `name == "Done"`.

### SSV-U-19 — a refused rename rolls back first: other uncommitted changes go
- **Rules:** `update_status` R4 [BUG-1220]; S2a
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status, but `name "Receiving"`.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Goods in"))`, with **spies**, inside the `raises:` wrap.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. mock called: `rb.call_count >= 1`.
4. mock called: `cm.call_count == 0`.
5. count: `statuses` rows with `name == "Extra"`: exactly 0.
6. unchanged: unchanged(S).

### SSV-U-20 — two workflows: both named, in id order, with "order workflows"
- **Rules:** `update_status` R4a [BUG-1220], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status.
2. F = workflow on [S.id].
3. G = workflow on [S.id], but `name "Alt Flow"`, `type "STM"`.

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Done"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Status 'Feat' is used by order workflows 'Flow', 'Alt Flow' and cannot be renamed"`.
3. unchanged: unchanged(S).

### SSV-U-21 — a stage status in no sequence names the workspace's purchase workflow row
- **Rules:** `update_status` R4a [BUG-1220], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status, but `name "Receiving"`.
2. PF = workflow on [], but `name "PO Flow"`, `type "purchase"`.

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Goods in"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Status 'Receiving' is used by order workflow 'PO Flow' and cannot be renamed"`.
3. unchanged: unchanged(S).

### SSV-U-22 — a stage status in the purchase sequence names that workflow once
- **Rules:** `update_status` R4a [BUG-1220], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status, but `name "Draft"`.
2. PF = workflow on [S.id], but `name "PO Flow"`, `type "purchase"`.

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Started"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Status 'Draft' is used by order workflow 'PO Flow' and cannot be renamed"`.
3. unchanged: unchanged(S).

### SSV-U-23 — another workspace's workflow is never named
- **Rules:** `update_status` R4a [BUG-1220], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status, but `name "Receiving"`.
2. F9 = workflow on [S.id], but `workspace_id W2.id`, `name "Far Flow"`.
3. PF9 = workflow on [], but `workspace_id W2.id`, `name "Far PO"`, `type "purchase"`.

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Goods in"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.detail == "Status 'Receiving' is used by order workflow 'Purchase Order' and cannot be renamed"`.
3. unchanged: unchanged(S).

### SSV-U-24 — a stage name in other capitals is a stage status: rename refused
- **Rules:** `update_status` R4, R4a, R4b [BUG-1880], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220, BUG-1880
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status, but `name "receiving"`.

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Goods in"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status 'receiving' is used by order workflow 'Purchase Order' and cannot be renamed"`.
4. unchanged: unchanged(S).

### SSV-U-25 — a stage name with outer spaces is a stage status: rename refused
- **Rules:** `update_status` R4, R4a, R4b [BUG-1880], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220, BUG-1880
- **Fails today on:** Then 1 (no error: the status is renamed)

**Given**
1. S = status, but `name " Receiving "`.

**When**
- `svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Goods in"))`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status ' Receiving ' is used by order workflow 'Purchase Order' and cannot be renamed"`.
4. unchanged: unchanged(S).

### SSV-U-26 — a space inside a stage name is not a stage status: renamed
- **Rules:** `update_status` R4, R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = status, but `name "Re ceiving"`.

**When**
- `result = svc.update_status(db, status_id=S.id, status_in=StatusUpdate(name="Goods in"))`.

**Then**
1. returns: `result.name == "Goods in"`.
2. committed: re-read S: `name == "Goods in"`.

## `StatusService.delete_status`

### SSV-D-01 — a status nothing uses is hard-deleted and committed; True is returned
- **Rules:** `delete_status` R5, Returns; S1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = status.
2. B = status, but `name "Other"`.
3. `a_id = A.id`.

**When**
- `result = svc.delete_status(db, status_id=A.id)`.

**Then**
1. returns: `result is True`.
2. committed: `statuses` rows with `id == a_id`: exactly 0.
3. committed: re-read B: `name == "Other"`.

### SSV-D-02 — id 0 returns False, writes nothing, neither commits nor rolls back
- **Rules:** `delete_status` R1; S3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `result = svc.delete_status(db, status_id=0)`, with **spies**.

**Then**
1. returns: `result is False`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `statuses` rows with `name == "Extra"`: exactly 1.
5. unchanged: unchanged(A).
6. committed: `statuses` rows with `name == "Extra"`: exactly 0.

### SSV-D-03 — an unknown id returns False
- **Rules:** `delete_status` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = status.

**When**
- `result = svc.delete_status(db, status_id=MISSING)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(A).

### SSV-D-04 — today another workspace's status is deleted (documents BUG-035)
- **Rules:** `delete_status` R2 (today)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = status.
2. Z = status, but `workspace_id W2.id`, `name "Far"`.
3. `z_id = Z.id`.

**When**
- `result = svc.delete_status(db, status_id=Z.id)`.

**Then**
1. returns: `result is True`.
2. committed: `statuses` rows with `id == z_id`: exactly 0.

### SSV-D-05 — another workspace's status is not found and stays
- **Rules:** `delete_status` R2 [BUG-035]
- **Kind:** bug
- **Expect:** xfail BUG-035
- **Fails today on:** Then 1 (the call raises TypeError: no `workspace_id` parameter yet)

**Given**
1. A = status.
2. Z = status, but `workspace_id W2.id`, `name "Far"`.

**When**
- `result = svc.delete_status(db, status_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(Z).

### SSV-D-06 — an unused purchase order stage status is refused, naming 'Purchase Order'
- **Rules:** `delete_status` R3 [BUG-1220]; `update_status` R4a, R4b; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is deleted, `True`)

**Given**
1. S = status, but `name "Complete"`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status 'Complete' is used by order workflow 'Purchase Order' and cannot be deleted"`.
4. unchanged: unchanged(S).

### SSV-D-07 — a status in the workspace's workflow sequence is refused, naming the workflow
- **Rules:** `delete_status` R3 [BUG-1220]; `update_status` R4a; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is deleted, `True`)

**Given**
1. S = status.
2. F = workflow on [S.id].

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status 'Feat' is used by order workflow 'Flow' and cannot be deleted"`.
4. unchanged: unchanged(S).
5. re-read F: `status_sequence == [S.id]`.

### SSV-D-08 — the protection is checked before the in-use refusal
- **Rules:** `delete_status` R3 [BUG-1220], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (the call raises IntegrityError: the in-use delete fails on `current_status_id`)

**Given**
1. S = status.
2. F = workflow on [S.id].
3. T = transfer on S.
4. `db.expire_all()`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status 'Feat' is used by order workflow 'Flow' and cannot be deleted"`.
4. unchanged: unchanged(S).

### SSV-D-09 — a status a transfer order uses is refused, listing the transfer
- **Rules:** `delete_status` R4 [BUG-1218], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1218
- **Fails today on:** Then 1 (the call raises IntegrityError 23502 on `current_status_id`)

**Given**
1. S = status.
2. T = transfer on S.
3. `db.expire_all()`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status is used by orders"`.
4. raises: `exc.value.errors == [{"type": "transfer_order", "id": T.id}]`.
5. unchanged: unchanged(S).
6. re-read T: `current_status_id == S.id`.

### SSV-D-10 — a status a purchase order uses is refused, listing the purchase order
- **Rules:** `delete_status` R4 [BUG-1218], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1218
- **Fails today on:** Then 1 (the call raises IntegrityError 23502 on `current_status_id`)

**Given**
1. S = status.
2. O = purchase on S.
3. `db.expire_all()`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status is used by orders"`.
4. raises: `exc.value.errors == [{"type": "purchase_order", "id": O.id}]`.
5. unchanged: unchanged(S).
6. re-read O: `current_status_id == S.id`.

### SSV-D-11 — a status used only by another workspace's order is refused with the generic entry alone
- **Rules:** `delete_status` R4 [BUG-1218], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1218
- **Fails today on:** Then 1 (the call raises IntegrityError 23502 on `current_status_id`)

**Given**
1. S = status.
2. T9 = transfer on S, but `workspace_id W2.id`, `transfer_number "TO-9"`.
3. `db.expire_all()`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.errors == [{"type": "other_workspace"}]`.
4. unchanged: unchanged(S).

### SSV-D-12 — a name that only contains a stage name, and a status in another workspace's workflow, are deleted
- **Rules:** `delete_status` R3, R5; `update_status` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = status, but `name "Completed"`.
2. F9 = workflow on [S.id], but `workspace_id W2.id`.
3. `s_id = S.id`.

**When**
- `result = svc.delete_status(db, status_id=S.id)`.

**Then**
1. returns: `result is True`.
2. committed: `statuses` rows with `id == s_id`: exactly 0.
3. committed: re-read F9: `status_sequence == [s_id]`.

### SSV-D-13 — a failing commit is rolled back and re-raised: the status stays
- **Rules:** `delete_status` R6; S2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = status.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.delete_status(db, status_id=A.id)`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(A).
4. count: `statuses` rows with `name == "Extra"`: exactly 0.
5. raises: `exc.value is boom`.

### SSV-D-14 — a refused stage-status delete rolls back first: other uncommitted changes go
- **Rules:** `delete_status` R3 [BUG-1220]; S2a
- **Kind:** bug
- **Expect:** xfail BUG-1220
- **Fails today on:** Then 1 (no error: the status is deleted, `True`)

**Given**
1. S = status, but `name "Complete"`.
2. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.delete_status(db, status_id=S.id)`, with **spies**, inside the `raises:` wrap.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. mock called: `rb.call_count >= 1`.
4. mock called: `cm.call_count == 0`.
5. count: `statuses` rows with `name == "Extra"`: exactly 0.
6. unchanged: unchanged(S).

### SSV-D-15 — a refused in-use delete rolls back first: other uncommitted changes go
- **Rules:** `delete_status` R4 [BUG-1218]; S2a
- **Kind:** bug
- **Expect:** xfail BUG-1218
- **Fails today on:** Then 1 (the call raises IntegrityError 23502 on `current_status_id`)

**Given**
1. S = status.
2. T = transfer on S.
3. `db.expire_all()`.
4. X = status, but `name "Extra"` (after the commit point).

**When**
- `svc.delete_status(db, status_id=S.id)`, with **spies**, inside the `raises:` wrap.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. mock called: `rb.call_count >= 1`.
4. mock called: `cm.call_count == 0`.
5. count: `statuses` rows with `name == "Extra"`: exactly 0.
6. unchanged: unchanged(S).

### SSV-D-16 — a stage name with a leading space is a stage status: delete refused
- **Rules:** `delete_status` R3 [BUG-1880]; `update_status` R4a, R4b; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220, BUG-1880
- **Fails today on:** Then 1 (no error: the status is deleted, `True`)

**Given**
1. S = status, but `name " Complete"`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status ' Complete' is used by order workflow 'Purchase Order' and cannot be deleted"`.
4. unchanged: unchanged(S).

### SSV-D-17 — a status a sales order uses is refused, listing the sales order
- **Rules:** `delete_status` R4 [BUG-1218], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1218
- **Fails today on:** Then 1 (the call raises IntegrityError 23502 on `current_status_id`)

**Given**
1. S = status.
2. SO = sales on S.
3. `db.expire_all()`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status is used by orders"`.
4. raises: `exc.value.errors == [{"type": "sales_order", "id": SO.id}]`.
5. unchanged: unchanged(S).

### SSV-D-18 — the blockers come by type (purchase, sales, transfer), then id, then one other-workspace entry last
- **Rules:** `delete_status` R4 [BUG-1218], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1218
- **Fails today on:** Then 1 (the call raises IntegrityError 23502 on `current_status_id`)

**Given**
1. S = status.
2. T = transfer on S.
3. T9 = transfer on S, but `workspace_id W2.id`, `transfer_number "TO-9"`.
4. SO = sales on S.
5. O1 = purchase on S.
6. O2 = purchase on S, but `po_number "PO-2"`.
7. O9 = purchase on S, but `workspace_id W2.id`, `po_number "PO-9"`.
8. `db.expire_all()`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.errors == [{"type": "purchase_order", "id": O1.id}, {"type": "purchase_order", "id": O2.id}, {"type": "sales_order", "id": SO.id}, {"type": "transfer_order", "id": T.id}, {"type": "other_workspace"}]`.
3. unchanged: unchanged(S).

### SSV-D-19 — a stage name in capitals is a stage status: delete refused
- **Rules:** `delete_status` R3 [BUG-1880]; `update_status` R4a, R4b; Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1220, BUG-1880
- **Fails today on:** Then 1 (no error: the status is deleted, `True`)

**Given**
1. S = status, but `name "COMPLETE"`.

**When**
- `svc.delete_status(db, status_id=S.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Status 'COMPLETE' is used by order workflow 'Purchase Order' and cannot be deleted"`.
4. unchanged: unchanged(S).

### SSV-D-20 — a space inside a stage name is not a stage status: deleted
- **Rules:** `delete_status` R3, R5; `update_status` R4b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = status, but `name "Com plete"`.
2. `s_id = S.id`.

**When**
- `result = svc.delete_status(db, status_id=S.id)`.

**Then**
1. returns: `result is True`.
2. committed: `statuses` rows with `id == s_id`: exactly 0.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| 404 `{"detail": "Status not found"}` made of `None` / `False`; the endpoints' workspace dependency (BUG-035) | `/statuses/` endpoints (integration) | Integration-only. |
| BUG-1217 — `GET /statuses/` accepts `limit <= 0` | endpoint | Endpoint bounds. |
| BUG-1680 / BUG-461 — schema errors answer 422 | `POST`, `PUT /statuses/` | Integration-only. |
| BUG-1221 — 409 through the global `IntegrityError` handler; the index itself | migration + handler; `tests/unit/dao/status.cases.md` (STS-CR-07, CR-08) | The index on the normalised name. |
| BUG-1218 — 400 body with the blocker list (RFC 7807 `errors`) | endpoint (integration) | Body shape over HTTP. |
| `status_service` singleton | none (no logic) | Entry point of every card. |

## Spec gaps
None. Revision 1's gaps 1–4 are closed by spec Gap log G1–G4.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_statuses` | R1 (today) | SSV-L-01 |
| `get_statuses` | R1 [BUG-035] | SSV-L-02 |
| `get_statuses` | R2 | SSV-L-01, SSV-L-03, SSV-L-04, SSV-L-05, SSV-L-06, SSV-L-07, SSV-L-08, SSV-L-12 |
| `get_statuses` | R3 [BUG-1681] | SSV-L-09, SSV-L-10 |
| `get_statuses` | R4 | SSV-L-07, SSV-L-11 |
| `get_statuses` | Errors | SSV-L-07, SSV-L-08 |
| `get_by_id` | R1 | SSV-G-01 |
| `get_by_id` | R2 | SSV-G-02, SSV-G-03 |
| `get_by_id` | R3 (today) | SSV-G-04 |
| `get_by_id` | R3 [BUG-035] | SSV-G-05 |
| `get_by_id` | R4 | SSV-G-03 |
| `create_status` | R1 (today) | SSV-C-02 |
| `create_status` | R1 [BUG-035] | SSV-C-01 |
| `create_status` | R2 | SSV-C-03 |
| `create_status` | R3 | SSV-C-04 |
| `create_status` | R3 [BUG-035] | SSV-C-05 |
| `create_status` | R4 | SSV-C-08 |
| `create_status` | R4 [BUG-1680] | SSV-C-06, SSV-C-07 |
| `create_status` | R5 [BUG-1221] | SSV-C-09, SSV-C-10 |
| `create_status` | R5 (other workspace) [BUG-035] | SSV-C-11 |
| `create_status` | R6 | SSV-C-02 |
| `create_status` | R6 [BUG-035] | SSV-C-12, SSV-C-13 |
| `create_status` | Errors | SSV-C-02, SSV-C-04, SSV-C-06, SSV-C-09, SSV-C-10 |
| `create_status` | Returns | SSV-C-01 |
| `update_status` | R1 | SSV-U-04, SSV-U-05 |
| `update_status` | R2 (today) | SSV-U-06 |
| `update_status` | R2 [BUG-035] | SSV-U-07 |
| `update_status` | R3 | SSV-U-01, SSV-U-02, SSV-U-03 |
| `update_status` | R4 | SSV-U-10, SSV-U-11, SSV-U-12, SSV-U-13 |
| `update_status` | R4 [BUG-1220] | SSV-U-08, SSV-U-09, SSV-U-19 |
| `update_status` | R4a [BUG-1220] | SSV-U-08, SSV-U-09, SSV-U-20, SSV-U-21, SSV-U-22, SSV-U-23, SSV-D-06, SSV-D-07 |
| `update_status` | R4b | SSV-U-12, SSV-U-26, SSV-D-12, SSV-D-20 |
| `update_status` | R4b [BUG-1880] | SSV-U-24, SSV-U-25, SSV-D-16, SSV-D-19 |
| `update_status` | R4b [BUG-1220] | SSV-U-08, SSV-D-06 |
| `update_status` | R5 | SSV-C-03 |
| `update_status` | R6 [BUG-1680] | SSV-U-14, SSV-U-15 |
| `update_status` | R7 [BUG-1221] | SSV-U-16 |
| `update_status` | R8 | SSV-U-17, SSV-U-18 |
| `update_status` | Errors row 1 | SSV-U-08, SSV-U-09, SSV-U-20, SSV-U-21, SSV-U-22, SSV-U-23, SSV-U-24, SSV-U-25 |
| `update_status` | Errors row 2 | SSV-U-16 |
| `update_status` | Errors row 3 | SSV-U-14 |
| `update_status` | Returns | SSV-U-01, SSV-U-04 |
| `delete_status` | R1 | SSV-D-02, SSV-D-03 |
| `delete_status` | R2 (today) | SSV-D-04 |
| `delete_status` | R2 [BUG-035] | SSV-D-05 |
| `delete_status` | R3 | SSV-D-12, SSV-D-20 |
| `delete_status` | R3 [BUG-1880] | SSV-D-16, SSV-D-19 |
| `delete_status` | R3 [BUG-1220] | SSV-D-06, SSV-D-07, SSV-D-08, SSV-D-14 |
| `delete_status` | R4 [BUG-1218] | SSV-D-09, SSV-D-10, SSV-D-11, SSV-D-15, SSV-D-17, SSV-D-18 |
| `delete_status` | R5 | SSV-D-01, SSV-D-12, SSV-D-20 |
| `delete_status` | R6 | SSV-D-13 |
| `delete_status` | Errors row 1 | SSV-D-06, SSV-D-07, SSV-D-08, SSV-D-16, SSV-D-19 |
| `delete_status` | Errors row 2 | SSV-D-09, SSV-D-10, SSV-D-11, SSV-D-17, SSV-D-18 |
| `delete_status` | Returns | SSV-D-01, SSV-D-02 |
| Transaction rules | S1 | SSV-C-01, SSV-C-13, SSV-U-01, SSV-U-18, SSV-D-01 |
| Transaction rules | S2 | SSV-C-02, SSV-C-09, SSV-C-12, SSV-U-16, SSV-U-17, SSV-D-13 |
| Transaction rules | S2a [BUG-1220] [BUG-1218] | SSV-U-19, SSV-D-14, SSV-D-15 |
| Transaction rules | S3 | SSV-U-04, SSV-D-02 |
| Transaction rules | S4 | SSV-L-07, SSV-L-11, SSV-G-03 |
