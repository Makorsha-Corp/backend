# Test cases — `app/services/help_ticket_service.py`

> **Spec:** `tests/unit/services/help_ticket_service.spec.md` (source commit e48a092)
> **Status:** READY
> **Revision:** 2 (2026-11-04) — from `help_ticket_service.verify.md`: finding 1 → new HTS-P-08 (the platform list's default limit, mutant #10). Finding 2 / gap 2 closed: the spec now marks the "re-read finds nothing" fallback not unit-testable (spec revision 2026-11-04), so it gets no card. No card changed or retired.
> **Counts:** 88 cases · 62 expected-to-pass · 26 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `create_ticket` 10 (5 bug) · `list_tickets` 16 (2 bug) · `get_ticket` 16 · `update_ticket` 34 (18 bug) · `list_platform_tickets` 8 (1 bug) · `get_platform_ticket` 4.
- **Depth:** full for who may see and who may change a ticket (`get_ticket` R1–R4, `update_ticket` R1, R3, R3a, R5: owner's OQ-8, BUG-1863); lighter for the rest (support messages, no stock, money or order state). Transaction contract TC1–TC6 from `department_service.spec.md`.
- **BUG-1863 (strict, 10 cards, HTS-U-16 … U-25):** one shape per card: ground-team-manager × title / description / category / `category: null` / the unchanged title / title + `status closed`; owner × title; platform admin × description; owner on a ticket whose creator is gone; and the TC3 card (an uncommitted change elsewhere in the session is discarded). Each asserts the exact type and message, `unchanged(T)` and nothing written.
- **Kept passing beside BUG-1863:** the creator edits text (U-01, also as an owner U-02); a manager, an owner and an admin close or reopen (U-04 … U-06).
- **Ids both sides:** the acting non-creator has a lower id (MGR) in some cards and a higher id (OWN, FIN, ADM) in others; workspace filters are tested W1 → W2 and W2 → W1; by-id reads have tickets at lower and higher ids.
- **Other xfail:** BUG-1574 8 (strict), BUG-1575 2, BUG-1576 1, BUG-1577 1, BUG-1578 1; pass-through BUG-1441 1 (strict), BUG-1443 1 (strict), BUG-1442 1 (non-strict, `Author: claude`).
- **Notable design choices:** lists are compared as sets except in the one BUG-1442 card; refusals run without a savepoint after a commit point, so a write the refusal fails to undo stays visible; the BUG-1577 card uses the real clock (spec Notes), every other close patches `utcnow` and asserts only `closed_at is not None`.
- **Needs a decision:** None blocking. Gap 1 (where `HelpTicketStatusEnum` is imported from). Gap 2 closed in Revision 2.

## Conventions for this module

**IDs.** `HTS` = `app/services/help_ticket_service.py`. `C` create_ticket · `L` list_tickets · `G` get_ticket · `U` update_ticket · `P` list_platform_tickets · `Q` get_platform_ticket.

**Actors and fixed values.**
- `svc` = `help_ticket_service` (`from app.services.help_ticket_service import HelpTicketService, help_ticket_service`). `db` = the test's real session, first argument; the rest by keyword. `result` = what the When returns.
- `HelpTicketNotFoundError`, `HelpTicketForbiddenError` (`app.managers.help_ticket_manager`). `HelpTicket` (`app.models.help_ticket`). `HelpTicketCreate`, `HelpTicketUpdate`, `HelpTicketResponse`, `PlatformHelpTicketListItem` (`app.schemas.help_ticket`). `HelpTicketStatusEnum` (spec gap 1). `RoleEnum` (`app.models.enums`). `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError`, `DataError` (`sqlalchemy.exc`). `select`, `func`, `text` (`sqlalchemy`). `patch` (`unittest.mock`). `datetime`, `timezone`, `timedelta` (`datetime`).
- OWNER_R = `RoleEnum("owner")`, GTM_R = `RoleEnum("ground-team-manager")`, GT_R = `RoleEnum("ground-team")`, FIN_R = `RoleEnum("finance")`. OPEN = `HelpTicketStatusEnum("open")`, CLOSED = `HelpTicketStatusEnum("closed")`.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. PAST = `datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)`.
- FORBID = `"You do not have access to this help ticket."`. NOTFOUND = `"Help ticket not found."`.

**Standing rows** (every test, in this order, no Given line): W1 = `make_workspace(db, name=f"Gamma {TAG}")`, W2 = `make_workspace(db, name=f"Delta {TAG}")`; then profiles by `make_profile(db, name=…)`: MGR `"Karim"`, CR `"Rahim"`, OWN `"Owen"`, ADM `"Sam"` with `is_platform_admin=True`, FIN `"Fatima"`. So MGR.id < CR.id < OWN.id < ADM.id < FIN.id. No membership rows: the role is an argument. No ticket exists unless the Given builds it.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written.
- **ticket** = `HelpTicket(workspace_id=W1.id, ticket_number=N, title="Printer jam", description="It jams", category="hardware", created_by=CR.id)`; `status` left to its default `"open"`. The card gives `ticket_number`; after "but" every other column that differs.
- **closed ticket** = a ticket, but `status "closed"`, `closed_at PAST`, `closed_by MGR.id`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint under the `db` fixture). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (only where a card lists it, after the commit point) = `X = HelpTicket(workspace_id=W2.id, ticket_number=f"HELP-X-{TAG}", title="Extra", description="Extra", created_by=FIN.id)`, `db.add(X)`, `db.flush()`; not committed. `X_ID = X.id`.
- A Given line written as code is a step to run exactly.

**Externals.**
- **clock** (every `C` card unless it says otherwise): around the When, patch `app.dao.help_ticket.datetime` with a subclass of `datetime` whose `now()` returns `datetime(2026, 6, 1, 12, 0)`, and patch `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow` to return `datetime(2026, 6, 1, 12, 0)`.
- **close clock** (every `U` card unless it says "real clock"): around the When, patch `app.managers.help_ticket_manager.utcnow` to return `datetime(2026, 6, 1, 12, 0)`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(HelpTicket, X.id)`; database values.
- **unchanged(T)** = after re-read, `title`, `description`, `category`, `status`, `closed_at`, `closed_by`, `created_by` of T equal their values at the commit point.
- **nothing written** = the numbers of `help_tickets` rows with `workspace_id` W1 and with W2 equal their values at the commit point.
- **x_gone** = `db.scalar(select(func.count()).select_from(HelpTicket).where(HelpTicket.id == X_ID)) == 0`.
- **idset(r)** = `{t.id for t in r}`. **own(r)** = `{t.id for t in r if t.id in OWN}`, OWN = the ids of the tickets the Given made.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint; further lines on `exc.value` after the block. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call. A `schema` card wraps only building the schema.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.
- **pending P** = `P = HelpTicket(workspace_id=W2.id, ticket_number=f"HELP-P-{TAG}", title="Pending", description="Pending", created_by=FIN.id)`, `db.add(P)`, `db.flush()`, after the commit point. `pending:` lines check it after the call.
- **seqscan** = `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown; a non-strict card's assertion is never weakened.

**Race simulations.** None.

## `HelpTicketService.create_ticket`

### HTS-C-01 — the ticket is created, committed and answered with its creator's name
- **Rules:** `create_ticket` R1, R3, TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- `result = svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="Printer jam", description="It jams", category="hardware"))`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. returns: `result.ticket_number == "HELP-2026-001"`, `result.status == OPEN`.
3. returns: `result.workspace_id == W1.id`, `result.created_by == CR.id`, `result.creator_name == "Rahim"`.
4. returns: `result.title == "Printer jam"`, `result.description == "It jams"`, `result.category == "hardware"`.
5. returns: `result.closed_at is None`, `result.closed_by is None`.
6. returns: `result.created_at is not None`, `result.updated_at is not None`.
7. committed: the row with id `result.id` exists, `ticket_number == "HELP-2026-001"`, `created_by == CR.id`.

### HTS-C-02 — an unknown user rolls back, reaches the caller, and discards other pending changes
- **Rules:** `create_ticket` R4, TC3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No ticket in W1 (commit point after this line).
2. extra row X.

**When**
- `svc.create_ticket(db, workspace=W1, user=SimpleNamespace(id=MISSING, name="Ghost"), payload=HelpTicketCreate(title="Printer jam", description="It jams"))` (`SimpleNamespace` from `types`).

**Then**
1. raises: `IntegrityError`.
2. count: x_gone.
3. nothing written.
4. session: `db.execute(text("SELECT 1")).scalar() == 1`.

### HTS-C-03 — a failing commit rolls back and nothing is saved
- **Rules:** `create_ticket` R4, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- failing commit: `svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="Printer jam", description="It jams"))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. nothing written.

### HTS-C-04 — a failing re-read after the commit leaves the ticket saved
- **Rules:** `create_ticket` R4, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- failing refresh: `svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="Printer jam", description="It jams"))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: W1 has exactly 1 ticket, `title == "Printer jam"`, `created_by == CR.id`.

### HTS-C-05 — the year of the number is the UTC year (pass-through)
- **Rules:** `create_ticket` R1 (DAO `create_with_user` R2 [BUG-1441])
- **Kind:** bug
- **Expect:** xfail BUG-1441
- **Fails today on:** Then 2 (the local clock's year: `HELP-2027-001`)

**Given**
1. No ticket in W1 (commit point after this line).
2. Instead of clock: `app.dao.help_ticket.datetime` patched with a `datetime` subclass whose `now()` returns `datetime(2027, 1, 1, 5, 0)`; `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow` patched to return `datetime(2026, 12, 31, 23, 0)`.

**When**
- `result = svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="Printer jam", description="It jams"))`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. returns: `result.ticket_number == "HELP-2026-001"`.

### HTS-C-06 — title, description and category are stored trimmed
- **Rules:** `create_ticket` R2 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 2 (stored as typed: `"  Printer  "`)

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- `result = svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="  Printer  ", description="  It jams  ", category=" hardware "))`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. re-read the row `result.id`: `title == "Printer"`.
3. re-read the row `result.id`: `description == "It jams"`.
4. re-read the row `result.id`: `category == "hardware"`.

### HTS-C-07 — a whitespace-only title is refused by the schema
- **Rules:** `create_ticket` R2 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. No ticket in W1.

**When**
- build `HelpTicketCreate(title="   ", description="It jams")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### HTS-C-08 — a whitespace-only description is refused by the schema
- **Rules:** `create_ticket` R2 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. No ticket in W1.

**When**
- build `HelpTicketCreate(title="Printer jam", description="   ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### HTS-C-09 — a whitespace-only category is stored as None
- **Rules:** `create_ticket` R2 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 2 (stored `"   "`)

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- `result = svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="Printer jam", description="It jams", category="   "))`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. re-read the row `result.id`: `category is None`.

### HTS-C-10 — inner spaces and capitals are kept
- **Rules:** `create_ticket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- `result = svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="Printer  JAM", description="It  jams", category="Hard  ware"))`.

**Then**
1. returns: `result.title == "Printer  JAM"`.
2. re-read the row `result.id`: `title == "Printer  JAM"`, `description == "It  jams"`, `category == "Hard  ware"`.

## `HelpTicketService.list_tickets`

### HTS-L-01 — an owner sees every ticket of the workspace, not another workspace's
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TO = ticket `"HELP-2026-003"`, but `created_by OWN.id`.
4. TN = ticket `"HELP-2026-004"`, but `created_by None`.
5. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `all(isinstance(t, HelpTicketResponse) for t in result)`.
2. returns: `idset(result) == {TM.id, TC.id, TO.id, TN.id}`.

### HTS-L-02 — a ground-team-manager sees every ticket of the workspace
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TO = ticket `"HELP-2026-003"`, but `created_by OWN.id`.
4. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=MGR, role=GTM_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id, TC.id, TO.id}`.

### HTS-L-03 — a ground-team member sees only their own, not lower or higher creators'
- **Rules:** `list_tickets` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TO = ticket `"HELP-2026-003"`, but `created_by OWN.id`.
4. TN = ticket `"HELP-2026-004"`, but `created_by None`.
5. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=CR, role=GT_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TC.id}`.

### HTS-L-04 — a finance member sees only their own
- **Rules:** `list_tickets` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TO = ticket `"HELP-2026-003"`, but `created_by OWN.id`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=CR, role=FIN_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TC.id}`.

### HTS-L-05 — no role sees only their own
- **Rules:** `list_tickets` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TO = ticket `"HELP-2026-003"`, but `created_by OWN.id`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=CR, role=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TC.id}`.

### HTS-L-06 — the later workspace's list does not show the earlier workspace's tickets
- **Rules:** `list_tickets` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.
2. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_tickets(db, workspace_id=W2.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TZ.id}`.

### HTS-L-07 — status closed keeps only closed tickets
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TB = closed ticket `"HELP-2026-002"`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=CLOSED, limit=1000)`.

**Then**
1. returns: `idset(result) == {TB.id}`.

### HTS-L-08 — status open keeps only open tickets
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = closed ticket `"HELP-2026-001"`.
2. TB = ticket `"HELP-2026-002"`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=OPEN, limit=1000)`.

**Then**
1. returns: `idset(result) == {TB.id}`.

### HTS-L-09 — the default limit is 100
- **Rules:** `list_tickets` R1 (paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets, the k-th (k = 1 … 101) = ticket `f"HELP-2026-{k:03d}"`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `len(result) == 100`.

### HTS-L-10 — skip reaches the query
- **Rules:** `list_tickets` R1 (paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TB = ticket `"HELP-2026-002"`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, skip=2, limit=1000)`.

**Then**
1. returns: `result == []`.

### HTS-L-11 — limit reaches the query
- **Rules:** `list_tickets` R1 (paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TB = ticket `"HELP-2026-002"`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1)`.

**Then**
1. returns: `len(result) == 1`.
2. returns: `idset(result) <= {TA.id, TB.id}`.

### HTS-L-12 — a platform admin without a role sees every ticket of the workspace
- **Rules:** `list_tickets` R2 [BUG-1578]
- **Kind:** bug
- **Expect:** xfail BUG-1578
- **Fails today on:** Then 1 (only the admin's own tickets: `[]`)

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=ADM, role=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id, TC.id}`.

### HTS-L-13 — each entry carries its creator's name, None without a creator
- **Rules:** `list_tickets` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TN = ticket `"HELP-2026-003"`, but `created_by None`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `{t.id: t.creator_name for t in result} == {TM.id: "Karim", TC.id: "Rahim", TN.id: None}`.

### HTS-L-14 — a list neither commits nor rolls back
- **Rules:** `list_tickets` R4, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. TC = ticket `"HELP-2026-001"` (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TC.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. pending: `db.get(HelpTicket, P.id) is not None`.

### HTS-L-15 — a negative limit raises DataError when called directly
- **Rules:** `list_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. TC = ticket `"HELP-2026-001"`.

**When**
- `svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### HTS-L-16 — tied times come back id descending (pass-through)
- **Rules:** `list_tickets` R1 (DAO `list_by_workspace` R5 [BUG-1442])
- **Kind:** bug
- **Expect:** xfail BUG-1442 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no `id` tie-break; the updated row follows physical order)

**Given**
1. seqscan.
2. TA = ticket `"HELP-2026-001"`.
3. TB = ticket `"HELP-2026-002"`.
4. TC = ticket `"HELP-2026-003"`.
5. `db.execute(text("UPDATE help_tickets SET title = 'Printer jam!' WHERE id = :i"), {"i": TA.id})`, then `db.expire_all()`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `[t.id for t in result] == [TC.id, TB.id, TA.id]`.

## `HelpTicketService.get_ticket`

### HTS-G-01 — the creator gets their ticket with every field, not a neighbour
- **Rules:** `get_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `title "Other"`.
2. T = ticket `"HELP-2026-002"`.
3. TB = ticket `"HELP-2026-003"`, but `title "Third"`.

**When**
- `result = svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R)`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. returns: `result.id == T.id`, `result.ticket_number == "HELP-2026-002"`, `result.workspace_id == W1.id`.
3. returns: `result.title == "Printer jam"`, `result.description == "It jams"`, `result.category == "hardware"`.
4. returns: `result.status == OPEN`, `result.created_by == CR.id`, `result.creator_name == "Rahim"`.

### HTS-G-02 — an owner (higher id than the creator) gets a member's ticket
- **Rules:** `get_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result.id == T.id`, `result.creator_name == "Rahim"`.

### HTS-G-03 — a ground-team-manager (lower id than the creator) gets a member's ticket
- **Rules:** `get_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R)`.

**Then**
1. returns: `result.id == T.id`.

### HTS-G-04 — a platform admin without a role gets a member's ticket
- **Rules:** `get_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None)`.

**Then**
1. returns: `result.id == T.id`.

### HTS-G-05 — a ground-team member with a lower id than the creator is refused
- **Rules:** `get_ticket` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GT_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `type(exc.value) is HelpTicketForbiddenError`.
3. raises: `str(exc.value) == FORBID`.

### HTS-G-06 — a finance member with a higher id than the creator is refused
- **Rules:** `get_ticket` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTS-G-07 — no role and not a platform admin is refused
- **Rules:** `get_ticket` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=None)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTS-G-08 — an unknown id is not found
- **Rules:** `get_ticket` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=MISSING, user=OWN, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `type(exc.value) is HelpTicketNotFoundError`.
3. raises: `str(exc.value) == NOTFOUND`.

### HTS-G-09 — id 0 is not found
- **Rules:** `get_ticket` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=0, user=OWN, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTS-G-10 — the later workspace's ticket asked in the earlier workspace is not found, even by its creator
- **Rules:** `get_ticket` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=TZ.id, user=CR, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTS-G-11 — the earlier workspace's ticket asked in the later workspace is not found
- **Rules:** `get_ticket` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_ticket(db, workspace_id=W2.id, ticket_id=T.id, user=OWN, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTS-G-12 — another workspace's ticket gives "not found" before any access check
- **Rules:** `get_ticket` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=TZ.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTS-G-13 — a ticket whose creator is gone is refused to a plain member
- **Rules:** `get_ticket` R4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTS-G-14 — a ticket whose creator is gone shows creator_name None to an owner
- **Rules:** `get_ticket` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result.id == T.id`.
2. returns: `result.created_by is None`, `result.creator_name is None`.

### HTS-G-15 — a get neither commits nor rolls back
- **Rules:** `get_ticket` R4, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R)`.

**Then**
1. returns: `result.id == T.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. pending: `db.get(HelpTicket, P.id) is not None`.

### HTS-G-16 — a refused get does not roll back the session
- **Rules:** `get_ticket` R2, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. pending P.

**When**
- spies: `svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. mock called: `rb.call_count == 0`.
3. pending: `db.get(HelpTicket, P.id) is not None`.

## `HelpTicketService.update_ticket`

### HTS-U-01 — the creator changes title, description and category; committed
- **Rules:** `update_ticket` R3, R2, R7, TC1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `title "Other"`.
2. T = ticket `"HELP-2026-002"`.
3. TB = ticket `"HELP-2026-003"`, but `title "Third"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(title="Toner low", description="Grey prints", category="supplies"))`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. returns: `result.id == T.id`, `result.title == "Toner low"`, `result.creator_name == "Rahim"`.
3. committed: T has `title == "Toner low"`, `description == "Grey prints"`, `category == "supplies"`, `status == "open"`.
4. committed: TA has `title == "Other"`; TB has `title == "Third"`.

### HTS-U-02 — a creator who is an owner changes their own ticket's text
- **Rules:** `update_ticket` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by OWN.id` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(title="Toner low"))`.

**Then**
1. returns: `result.title == "Toner low"`.
2. committed: T has `title == "Toner low"`, `description == "It jams"`.

### HTS-U-03 — an empty payload changes nothing
- **Rules:** `update_ticket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate())`.

**Then**
1. returns: `result.id == T.id`, `result.title == "Printer jam"`, `result.status == OPEN`.
2. unchanged: unchanged(T).

### HTS-U-04 — a ground-team-manager closes a member's ticket
- **Rules:** `update_ticket` R5, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. returns: `result.status == CLOSED`, `result.closed_by == MGR.id`, `result.creator_name == "Rahim"`.
2. committed: T has `status == "closed"`, `closed_by == MGR.id`, `title == "Printer jam"`.
3. committed: T has `closed_at is not None`.

### HTS-U-05 — an owner reopens a closed ticket: closed_at and closed_by are cleared
- **Rules:** `update_ticket` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(status="open"))`.

**Then**
1. returns: `result.status == OPEN`, `result.closed_at is None`, `result.closed_by is None`.
2. committed: T has `status == "open"`, `closed_at is None`, `closed_by is None`.

### HTS-U-06 — a platform admin without a role closes a member's ticket
- **Rules:** `update_ticket` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. returns: `result.status == CLOSED`.
2. committed: T has `status == "closed"`, `closed_by == ADM.id`.

### HTS-U-07 — status null leaves status, closed_at and closed_by
- **Rules:** `update_ticket` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(status=None))`.

**Then**
1. returns: `result.status == CLOSED`.
2. unchanged: unchanged(T).

### HTS-U-08 — a text change without status leaves the closed state
- **Rules:** `update_ticket` R5, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(category="network"))`.

**Then**
1. returns: `result.category == "network"`.
2. committed: T has `category == "network"`, `status == "closed"`, `closed_at == PAST`, `closed_by == MGR.id`.

### HTS-U-09 — reopening an open ticket changes nothing
- **Rules:** `update_ticket` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(status="open"))`.

**Then**
1. returns: `result.status == OPEN`.
2. unchanged: unchanged(T).

### HTS-U-10 — closing an already closed ticket keeps who closed it and when
- **Rules:** `update_ticket` R6 [BUG-1576]
- **Kind:** bug
- **Expect:** xfail BUG-1576
- **Fails today on:** Then 2 (`closed_by` rewritten to OWN)

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. returns: `result.status == CLOSED`.
2. re-read T: `closed_by == MGR.id`.
3. re-read T: `closed_at == PAST`.

### HTS-U-11 — closed_at is the true moment whatever the database's time zone
- **Rules:** `update_ticket` R6 [BUG-1577]
- **Kind:** bug
- **Expect:** xfail BUG-1577
- **Fails today on:** Then 2 (5 hours off under `America/New_York`)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`.
2. T = ticket `"HELP-2026-001"` (commit point after this line).
3. Real clock: no close clock in this card.

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. returns: `result.status == CLOSED`.
2. re-read T: `abs(closed_at - created_at) < timedelta(seconds=60)`.

### HTS-U-12 — an unknown id is not found, rolled back, other pending changes discarded
- **Rules:** `update_ticket` R1, TC3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. extra row X.

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=MISSING, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.
3. count: x_gone.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-13 — another workspace's ticket is not found and not changed
- **Rules:** `update_ticket` R1, Errors row 1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=TZ.id, user=CR, role=OWNER_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.
3. unchanged: unchanged(TZ).

### HTS-U-14 — a finance member (higher id) who did not create it may not close it
- **Rules:** `update_ticket` R1, TC3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. extra row X.

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=FIN, role=FIN_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. count: x_gone.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-15 — a ground-team member (lower id) who did not create it may not close it
- **Rules:** `update_ticket` R1, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GT_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).

### HTS-U-16 — a ground-team-manager may not change a member's title
- **Rules:** `update_ticket` R3a [BUG-1863], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(title="Work order missing"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `type(exc.value) is HelpTicketForbiddenError`.
3. raises: `str(exc.value) == FORBID`.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-17 — a ground-team-manager may not change a member's description
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the description is replaced)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(description="Nothing happened"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).
4. nothing written.

### HTS-U-18 — a ground-team-manager may not change a member's category
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the category is replaced)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(category="other"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).
4. re-read T: `category == "hardware"`.

### HTS-U-19 — sending category null counts as a text change and is refused
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the category is cleared)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(category=None))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. re-read T: `category == "hardware"`.
4. unchanged: unchanged(T).

### HTS-U-20 — an owner (higher id than the creator) may not change a member's title
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(title="Work order missing"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).
4. nothing written.

### HTS-U-21 — a platform admin may not change a member's description
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the description is replaced)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(description="Nothing happened"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).
4. nothing written.

### HTS-U-22 — a text change combined with a close is refused whole: the ticket stays open
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: title replaced and ticket closed)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(title="Work order missing", status="closed"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. re-read T: `status == "open"`, `closed_at is None`, `closed_by is None`.
4. unchanged: unchanged(T).

### HTS-U-23 — sending the unchanged title still counts as a text change
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the same title is written)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(title="Printer jam"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).

### HTS-U-24 — a ticket whose creator is gone has its text changed by nobody
- **Rules:** `update_ticket` R3a [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced)

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(title="Work order missing"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).
4. nothing written.

### HTS-U-25 — a refused text change rolls back other pending changes of the session
- **Rules:** `update_ticket` R3a [BUG-1863], TC3
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced and committed)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. extra row X.

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(title="Work order missing"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. count: x_gone.
3. unchanged: unchanged(T).
4. session: `db.execute(text("SELECT 1")).scalar() == 1`.

### HTS-U-26 — a sent title, description and category are stored trimmed
- **Rules:** `update_ticket` R4 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 2 (stored as typed: `"  Toner low  "`)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(title="  Toner low  ", description="  Grey  ", category=" supplies "))`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `title == "Toner low"`.
3. re-read T: `description == "Grey"`.
4. re-read T: `category == "supplies"`.

### HTS-U-27 — a whitespace-only title is refused by the update schema
- **Rules:** `update_ticket` R4 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. No ticket needed.

**When**
- build `HelpTicketUpdate(title="   ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### HTS-U-28 — a whitespace-only description is refused by the update schema
- **Rules:** `update_ticket` R4 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 1 (the schema accepts `"   "`)

**Given**
1. No ticket needed.

**When**
- build `HelpTicketUpdate(description="   ")` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### HTS-U-29 — a whitespace-only category is stored as None
- **Rules:** `update_ticket` R4 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 2 (stored `"   "`)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(category="   "))`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `category is None`.

### HTS-U-30 — title null is refused by the update schema
- **Rules:** `update_ticket` R4a [BUG-1575]
- **Kind:** bug
- **Expect:** xfail BUG-1575
- **Fails today on:** Then 1 (the schema accepts `None`)

**Given**
1. No ticket needed.

**When**
- build `HelpTicketUpdate(title=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### HTS-U-31 — description null is refused by the update schema
- **Rules:** `update_ticket` R4a [BUG-1575]
- **Kind:** bug
- **Expect:** xfail BUG-1575
- **Fails today on:** Then 1 (the schema accepts `None`)

**Given**
1. No ticket needed.

**When**
- build `HelpTicketUpdate(description=None)` (target `schema`).

**Then**
1. raises: `PydanticValidationError`.

### HTS-U-32 — category null from the creator clears the category
- **Rules:** `update_ticket` R4a, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(category=None))`.

**Then**
1. returns: `result.category is None`.
2. committed: T has `category is None`, `title == "Printer jam"`.

### HTS-U-33 — a failing commit rolls back and nothing is saved
- **Rules:** `update_ticket` R7, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- failing commit: `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(T).

### HTS-U-34 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_ticket` R7, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- failing refresh: `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status="closed"))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: T has `status == "closed"`, `closed_by == MGR.id`.

## `HelpTicketService.list_platform_tickets`

### HTS-P-01 — tickets of every workspace, each with its workspace's and creator's name
- **Rules:** `list_platform_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.
2. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `created_by MGR.id`.

**When**
- `result = svc.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `all(isinstance(t, PlatformHelpTicketListItem) for t in result)`.
2. returns: `own(result) == {T1.id, T2.id}` (OWN = {T1.id, T2.id}).
3. returns: `{t.id: (t.workspace_name, t.creator_name) for t in result if t.id in OWN} == {T1.id: (f"Gamma {TAG}", "Rahim"), T2.id: (f"Delta {TAG}", "Karim")}`.

### HTS-P-02 — each entry carries the ticket's own fields
- **Rules:** `list_platform_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `[t.id for t in result if t.id == T1.id] == [T1.id]`.
2. returns: the entry E with `E.id == T1.id` has `E.ticket_number == "HELP-2026-001"`, `E.workspace_id == W2.id`, `E.title == "Printer jam"`, `E.status == OPEN`, `E.created_by == CR.id`.

### HTS-P-03 — a ticket without a creator has creator_name None
- **Rules:** `list_platform_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = svc.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `{t.id: t.creator_name for t in result if t.id == T1.id} == {T1.id: None}`.

### HTS-P-04 — status closed keeps only closed tickets
- **Rules:** `list_platform_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.
2. T2 = closed ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_platform_tickets(db, status=CLOSED, search=TAG, limit=1000)`.

**Then**
1. returns: `own(result) == {T2.id}` (OWN = {T1.id, T2.id}).

### HTS-P-05 — `_` in the search matches only a literal `_` (pass-through)
- **Rules:** `list_platform_tickets` R1 (DAO `list_platform` R6 [BUG-1443])
- **Kind:** bug
- **Expect:** xfail BUG-1443
- **Fails today on:** Then 1 (`_` is a wildcard and T2 matches too)

**Given**
1. T1 = ticket `"HELP-2026-001"`, but `title f"a_b {TAG}"`.
2. T2 = ticket `"HELP-2026-002"`, but `title f"plain {TAG}"`.

**When**
- `result = svc.list_platform_tickets(db, search="_", limit=100000)`.

**Then**
1. returns: `own(result) == {T1.id}` (OWN = {T1.id, T2.id}).

### HTS-P-06 — the platform list neither commits nor rolls back
- **Rules:** `list_platform_tickets` R2, TC6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"` (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `T1.id in {t.id for t in result}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. pending: `db.get(HelpTicket, P.id) is not None`.

### HTS-P-07 — a negative skip raises DataError when called directly
- **Rules:** `list_platform_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.

**When**
- `svc.list_platform_tickets(db, skip=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### HTS-P-08 — the platform list's default limit is 100
- **Rules:** `list_platform_tickets` R1 (paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets, the k-th (k = 1 … 101) = ticket `f"HELP-2026-{k:03d}"`, but `title f"T{k} {TAG}"`.

**When**
- `result = svc.list_platform_tickets(db, search=TAG)`.

**Then**
1. returns: `len(own(result)) == 100` (OWN = the ids of the 101 tickets).

## `HelpTicketService.get_platform_ticket`

### HTS-Q-01 — a ticket of any workspace is returned with its names, not a neighbour
- **Rules:** `get_platform_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `title "Other"`.
2. T = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
3. TB = ticket `"HELP-2026-002"`, but `title "Third"`.

**When**
- `result = svc.get_platform_ticket(db, ticket_id=T.id)`.

**Then**
1. returns: `isinstance(result, PlatformHelpTicketListItem)`.
2. returns: `result.id == T.id`, `result.workspace_id == W2.id`, `result.title == "Printer jam"`.
3. returns: `result.workspace_name == f"Delta {TAG}"`, `result.creator_name == "Rahim"`.

### HTS-Q-02 — an unknown id is not found
- **Rules:** `get_platform_ticket` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_platform_ticket(db, ticket_id=MISSING)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTS-Q-03 — id 0 is not found
- **Rules:** `get_platform_ticket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `svc.get_platform_ticket(db, ticket_id=0)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTS-Q-04 — the platform get neither commits nor rolls back
- **Rules:** `get_platform_ticket` R2 (read only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. pending P.

**When**
- spies: `result = svc.get_platform_ticket(db, ticket_id=T.id)`.

**Then**
1. returns: `result.id == T.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. pending: `db.get(HelpTicket, P.id) is not None`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Endpoint translation 404 / 403 `{"detail": …}` | `/help/tickets` endpoints | `HelpTicketNotFoundError` → 404, `HelpTicketForbiddenError` → 403 (incl. BUG-1863's text change) |
| `get_platform_admin` guard | `/platform/help/tickets` endpoints | 403 `Platform admin access required` for a non-admin |
| `limit` / `skip` bounds (HR-7) | endpoints | 422 for `limit=0`, `limit=201`, `skip=-1` |
| `IntegrityError` handler for `null` title today (P1) | global handler | replaced by 422 after BUG-1575 |
| `create_with_user` R3 [BUG-1440] (concurrent numbers) | integration test | two connections |
| FU-1: `can_access_ticket` in `AttachmentManager` after BUG-1863 | `AttachmentManager` spec | who may attach to a support ticket |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Facts for the test designer | The import path of `HelpTicketStatusEnum` | Not blocking: cards use `HelpTicketStatusEnum("open")` / `("closed")`; the executor imports it from wherever the schema module takes it. |
| 2 | `create_ticket` R3 | **Closed (Revision 2):** the spec (revision 2026-11-04) marks the "re-read finds nothing" fallback of `create_ticket` R3 / `update_ticket` R7 not unit-testable | No card, by the spec's decision. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_ticket` | R1 | HTS-C-01; BUG-1441 pass-through HTS-C-05 |
| `create_ticket` | R2 [BUG-1574] | HTS-C-06, HTS-C-07, HTS-C-08, HTS-C-09; kept HTS-C-10 |
| `create_ticket` | R3 | HTS-C-01 (fallback branch: not unit-testable per spec, gap 2 closed) |
| `create_ticket` | R4 (TC3, TC4, TC5) | HTS-C-02, HTS-C-03, HTS-C-04 |
| `create_ticket` | Errors (unknown user) | HTS-C-02 |
| `list_tickets` | R1 | HTS-L-01 … HTS-L-11; BUG-1442 pass-through HTS-L-16 |
| `list_tickets` | R2 [BUG-1578] | HTS-L-12 |
| `list_tickets` | R3 | HTS-L-13 |
| `list_tickets` | R4 (TC6) | HTS-L-14 |
| `list_tickets` | Errors (DataError) | HTS-L-15 |
| `get_ticket` | R1 | HTS-G-01, HTS-G-02, HTS-G-03, HTS-G-04 |
| `get_ticket` | R2 | HTS-G-05, HTS-G-06, HTS-G-07, HTS-G-16 |
| `get_ticket` | R3 | HTS-G-08, HTS-G-09, HTS-G-10, HTS-G-11, HTS-G-12 |
| `get_ticket` | R4 | HTS-G-13, HTS-G-14, HTS-G-15 |
| `update_ticket` | R1 | HTS-U-12, HTS-U-13, HTS-U-14, HTS-U-15 |
| `update_ticket` | R2 | HTS-U-03, HTS-U-01 |
| `update_ticket` | R3 | HTS-U-01, HTS-U-02, HTS-U-08, HTS-U-32 |
| `update_ticket` | R3a [BUG-1863] | HTS-U-16 … HTS-U-25 |
| `update_ticket` | R4 [BUG-1574] | HTS-U-26, HTS-U-27, HTS-U-28, HTS-U-29 |
| `update_ticket` | R4a [BUG-1575] | HTS-U-30, HTS-U-31; category null HTS-U-32 |
| `update_ticket` | R5 | HTS-U-04, HTS-U-05, HTS-U-06, HTS-U-07, HTS-U-08 |
| `update_ticket` | R6 [BUG-1576] | HTS-U-10; reopen-open HTS-U-09 |
| `update_ticket` | R6 [BUG-1577] | HTS-U-11 |
| `update_ticket` | R7 (TC1, TC4, TC5) | HTS-U-01, HTS-U-04, HTS-U-33, HTS-U-34 |
| `update_ticket` | Errors row 1 (not found) | HTS-U-12, HTS-U-13 |
| `update_ticket` | Errors row 2 (not allowed to see) | HTS-U-14, HTS-U-15 |
| `update_ticket` | Errors row 3 (text by non-creator) | HTS-U-16 … HTS-U-25 |
| `update_ticket` | Errors row 4 (today's `IntegrityError`) | not carded: the buggy path; intended behaviour HTS-U-30, HTS-U-31 |
| `list_platform_tickets` | R1 | HTS-P-01 … HTS-P-04, HTS-P-08 (default limit); BUG-1443 pass-through HTS-P-05 |
| `list_platform_tickets` | R2 | HTS-P-06 |
| `list_platform_tickets` | Errors (DataError) | HTS-P-07 |
| `get_platform_ticket` | R1 | HTS-Q-01 |
| `get_platform_ticket` | R2 | HTS-Q-02, HTS-Q-03, HTS-Q-04 |
