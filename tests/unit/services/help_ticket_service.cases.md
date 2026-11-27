# Test cases — `app/services/help_ticket_service.py`

> **Spec:** `tests/unit/services/help_ticket_service.spec.md` (source commit 41d5ac1)
> **Status:** READY
> **Revision:** 4 (2026-11-26) — from `help_ticket_service.verify.md` Round (2026-11-26): finding 1 (spec G2, mutant #24) → new HTS-U-60 (an object without `is_platform_admin` is refused a status change) and HTS-U-61 (the same object, as creator, still changes text: the see-right tolerates it); finding 2 (TC3 with a non-manager error) → new HTS-U-62 and HTS-V-23 (`model_construct(title=None)` → `IntegrityError` before the commit, `X not in db`, x_gone, session usable); finding 3 → Spec gaps 3–5 marked closed by spec Gap log G1–G3, Reviewer summary updated. No card changed or retired.
> **Revision:** 3 (2026-11-26) — spec revision 2026-11-26 (merge of `origin/main`: `pending | opened | closed` workflow, `type`, `update_platform_ticket`; OQ-66 → BUG-3251; P3 → BUG-3270; BUG-1576 resolved). See "Revision (2026-11-26)" below.
> **Revision:** 2 (2026-11-04) — from `help_ticket_service.verify.md`: finding 1 → new HTS-P-08 (the platform list's default limit, mutant #10). Finding 2 / gap 2 closed: the spec now marks the "re-read finds nothing" fallback not unit-testable (spec revision 2026-11-04), so it gets no card. No card changed or retired.
> **Counts:** 158 cases · 119 expected-to-pass · 39 expected-to-fail (bugs) · 6 deferred

> **Revision (2026-11-26).** Status values are now `pending` / `opened` / `closed` (new tickets `pending`); `type` `support` / `feedback`; a fixed transition table; status rights per OQ-66 (platform admin, `owner`, `ground-team-manager`; today admins only → BUG-3251); new callable `update_platform_ticket` (abbreviation `V`) with BUG-3270 and TC1–TC5.
> - **Conventions:** `OPEN` removed; PENDING, OPENED, CLOSED, SUPPORT, FEEDBACK added; the ticket's default status is `"pending"`, its type `"support"`; new **opened ticket**, **refusal spy**, `session: X not in db`; the two new manager errors imported; the enum imports now come from the spec (old gap 1 closed); the close clock also covers `V` cards.
> - **Revised (marked "(revised 2026-11-26)"):** C-01, G-01, U-01, U-03, P-02 (status `pending`, `type` answered); L-08 (`opened` filter); U-04, U-05 (owner / manager moves → strict xfail BUG-3251, U-04 on an `opened` ticket); U-06 (admin closes an `opened` ticket); U-09 (`opened → opened` refused, 400); U-10 (`closed → closed` refused, stamps kept — BUG-1576 resolved, now a pass); U-11 (BUG-1577: a platform admin closes an `opened` ticket); U-22 (manager's text + status: a passing `PermissionError` card); U-33, U-34 (TC4 / TC5: a platform admin closes an `opened` ticket).
> - **Added:** C-11; L-17 … L-23; G-17 … G-19; U-35 … U-59; P-09 … P-14; Q-05, Q-06; V-01 … V-22. U-43 (the workspace's `owner_user_id` closes, BUG-3251) follows the coordinator's alignment with `help_ticket_manager.spec.md` R5g. Refusals of R5 assert the error type only (the message changes with BUG-3251, manager R5h).
> - **Retired:** none.

## Reviewer summary
- **Per callable:** `create_ticket` 11 (5 bug) · `list_tickets` 23 (2 bug) · `get_ticket` 19 · `update_ticket` 62 (25 bug) · `update_platform_ticket` 23 (6 bug) · `list_platform_tickets` 14 (1 bug) · `get_platform_ticket` 6.
- **Depth:** full for who may see and who may change a ticket and its status (`get_ticket` R1–R4, `update_ticket` R1, R3, R3a, R5–R5d, `update_platform_ticket` R2, R3a: OQ-8, OQ-66); lighter for the rest (support messages, no stock, money or order state). Transaction contract TC1–TC6 from `base_service.spec.md`.
- **BUG-1863 (strict, 10 cards, HTS-U-16 … U-25 except U-22, plus U-58):** one shape per card: ground-team-manager × title / description / category / `category: null` / the unchanged title; owner × title; platform admin × description; owner on a ticket whose creator is gone; the TC3 card; a platform admin's text + a valid status (U-58).
- **BUG-3251 (strict, 8 cards: U-04, U-05, U-38 … U-43):** manager / owner × pending→opened, opened→closed, closed→opened, creator or not; a refused pair by a manager (400); the workspace's `owner_user_id` with a finance role (U-43). Passing beside it: plain members (creator, ground-team / finance) are refused any status (U-35 … U-37); an owner / manager mixing text and status gets a `PermissionError` (U-22, U-57).
- **Transition table (pass, as a platform admin):** every allowed move (U-06, U-44, U-45) and every refused pair (U-09, U-10, U-47 … U-50), stored `"open"` (U-52, U-53), plain-string status (U-54, U-55).
- **`update_platform_ticket`:** BUG-3270 4 strict cards (V-11, V-12, V-14, V-15), BUG-1574 and BUG-1577 one pass-through each (V-21, V-22); passing: the caller is never checked to be an admin (V-02), not found, transitions, `{}`, `type` dropped, TC3 / TC4 / TC5.
- **Ids both sides:** the acting non-creator has a lower id (MGR) in some cards and a higher id (OWN, FIN, ADM) in others; workspace filters are tested W1 → W2 and W2 → W1; by-id reads and the platform PATCH have tickets at lower and higher ids.
- **Other xfail:** BUG-1574 9 (strict), BUG-1575 2, BUG-1577 2, BUG-1578 1; pass-through BUG-1441 1 (strict), BUG-1443 1 (strict), BUG-1442 1 (non-strict, `Author: claude`).
- **Notable design choices:** lists are compared as sets except in the one BUG-1442 card; refusals run without a savepoint after a commit point; TC3 cards check `X not in db` right after the raise, and one refusal card per write method spies on `rollback`; U-44 gives a `pending` ticket leftover close stamps (not a state the app makes) so "pending → opened touches no stamp" is observable; L-21 sets `created_at` explicitly so the hidden rows sort first.
- **Needs a decision:** None. Gaps 3–5 closed by spec Gap log G1–G3 (Revision 4).

## Conventions for this module

**IDs.** `HTS` = `app/services/help_ticket_service.py`. `C` create_ticket · `L` list_tickets · `G` get_ticket · `U` update_ticket · `V` update_platform_ticket · `P` list_platform_tickets · `Q` get_platform_ticket.

**Actors and fixed values.**
- `svc` = `help_ticket_service` (`from app.services.help_ticket_service import HelpTicketService, help_ticket_service`). `db` = the test's real session, first argument; the rest by keyword. `result` = what the When returns.
- `HelpTicketNotFoundError`, `HelpTicketForbiddenError`, `HelpTicketStatusChangeForbiddenError`, `HelpTicketInvalidTransitionError` (`app.managers.help_ticket_manager`). `HelpTicket` (`app.models.help_ticket`). `HelpTicketCreate`, `HelpTicketUpdate`, `HelpTicketResponse`, `PlatformHelpTicketListItem` (`app.schemas.help_ticket`). `HelpTicketStatusEnum`, `HelpTicketTypeEnum`, `RoleEnum` (`app.models.enums`). `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError`, `DataError` (`sqlalchemy.exc`). `select`, `func`, `text` (`sqlalchemy`). `patch` (`unittest.mock`). `datetime`, `timezone`, `timedelta` (`datetime`).
- OWNER_R = `RoleEnum("owner")`, GTM_R = `RoleEnum("ground-team-manager")`, GT_R = `RoleEnum("ground-team")`, FIN_R = `RoleEnum("finance")`. PENDING = `HelpTicketStatusEnum("pending")`, OPENED = `HelpTicketStatusEnum("opened")`, CLOSED = `HelpTicketStatusEnum("closed")`. SUPPORT = `HelpTicketTypeEnum("support")`, FEEDBACK = `HelpTicketTypeEnum("feedback")`.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. PAST = `datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)`.
- FORBID = `"You do not have access to this help ticket."`. NOTFOUND = `"Help ticket not found."`.

**Standing rows** (every test, in this order, no Given line): W1 = `make_workspace(db, name=f"Gamma {TAG}")`, W2 = `make_workspace(db, name=f"Delta {TAG}")`; then profiles by `make_profile(db, name=…)`: MGR `"Karim"`, CR `"Rahim"`, OWN `"Owen"`, ADM `"Sam"` with `is_platform_admin=True`, FIN `"Fatima"`. So MGR.id < CR.id < OWN.id < ADM.id < FIN.id. No membership rows: the role is an argument. No ticket exists unless the Given builds it.

**Given rows.** Inserted directly (never through `svc`), flushed one at a time in the order written.
- **ticket** = `HelpTicket(workspace_id=W1.id, ticket_number=N, title="Printer jam", description="It jams", category="hardware", created_by=CR.id)`; `status` left to its default `"pending"`, `type` to its default `"support"`. The card gives `ticket_number`; after "but" every other column that differs.
- **opened ticket** = a ticket, but `status "opened"`.
- **closed ticket** = a ticket, but `status "closed"`, `closed_at PAST`, `closed_by MGR.id`.
- **commit point** = after the last Given line the test runs `db.commit()` (releases a savepoint under the `db` fixture). Snapshots for `unchanged` and `nothing written` are taken there.
- **extra row X** (only where a card lists it, after the commit point) = `X = HelpTicket(workspace_id=W2.id, ticket_number=f"HELP-X-{TAG}", title="Extra", description="Extra", created_by=FIN.id)`, `db.add(X)`, `db.flush()`; not committed. `X_ID = X.id`.
- A Given line written as code is a step to run exactly.

**Externals.**
- **clock** (every `C` card unless it says otherwise): around the When, patch `app.dao.help_ticket.datetime` (`create=True`) with a subclass of `datetime` whose `now()` returns `datetime(2026, 6, 1, 12, 0)`, and patch `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow` to return `datetime(2026, 6, 1, 12, 0)`.
- **close clock** (every `U` and `V` card unless it says "real clock"): around the When, patch `app.managers.help_ticket_manager.utcnow` to return `datetime(2026, 6, 1, 12, 0)`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(HelpTicket, X.id)`; database values.
- **unchanged(T)** = after re-read, `title`, `description`, `category`, `status`, `type`, `closed_at`, `closed_by`, `created_by` of T equal their values at the commit point.
- **nothing written** = the numbers of `help_tickets` rows with `workspace_id` W1 and with W2 equal their values at the commit point.
- **x_gone** = `db.scalar(select(func.count()).select_from(HelpTicket).where(HelpTicket.id == X_ID)) == 0`.
- **idset(r)** = `{t.id for t in r}`. **own(r)** = `{t.id for t in r if t.id in OWN}`, OWN = the ids of the tickets the Given made.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint; further lines on `exc.value` after the block. `raises: DataError in a savepoint` = `with pytest.raises(DataError):` then `with db.begin_nested():` then the call. A `schema` card wraps only building the schema.
- `committed:` lines: before the first, the test runs `db.rollback()` once; each line then re-reads with a fresh query.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.
- **refusal spy: raises <Type>** = `with pytest.raises(<Type>) as exc:` around `with patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (no savepoint).
- `session: X not in db` = checked as the first line after the raise, before any re-read or count (the service's rollback expunges the pending X).
- `raises: PermissionError` = `with pytest.raises(PermissionError) as exc:`; "type only" = assert `type(exc.value) is <Type>` and not the message.
- **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When. **failing refresh** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "refresh", side_effect=RuntimeError("boom")):` around the When.
- **pending P** = `P = HelpTicket(workspace_id=W2.id, ticket_number=f"HELP-P-{TAG}", title="Pending", description="Pending", created_by=FIN.id)`, `db.add(P)`, `db.flush()`, after the commit point. `pending:` lines check it after the call.
- **seqscan** = `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.

**xfail cards.** Strict unless the Expect line says `(non-strict)`: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown; a non-strict card's assertion is never weakened.

**Race simulations.** None.

## `HelpTicketService.create_ticket`

### HTS-C-01 — the ticket is created pending, committed and answered with its creator's name (revised 2026-11-26)
- **Rules:** `create_ticket` R1, R1a, R3, TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- `result = svc.create_ticket(db, workspace=W1, user=CR, payload=HelpTicketCreate(title="Printer jam", description="It jams", category="hardware"))`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. returns: `result.ticket_number == "HELP-2026-001"`, `result.status == PENDING`, `result.type == SUPPORT`.
3. returns: `result.workspace_id == W1.id`, `result.created_by == CR.id`, `result.creator_name == "Rahim"`.
4. returns: `result.title == "Printer jam"`, `result.description == "It jams"`, `result.category == "hardware"`.
5. returns: `result.closed_at is None`, `result.closed_by is None`.
6. returns: `result.created_at is not None`, `result.updated_at is not None`.
7. committed: the row with id `result.id` exists, `ticket_number == "HELP-2026-001"`, `created_by == CR.id`.
8. committed: the row with id `result.id` has `status == "pending"`, `type == "support"`, `closed_at is None`, `closed_by is None`.

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
2. Instead of clock: `app.dao.help_ticket.datetime` patched (`create=True`) with a `datetime` subclass whose `now()` returns `datetime(2027, 1, 1, 5, 0)`; `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow` patched to return `datetime(2026, 12, 31, 23, 0)`.

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

### HTS-C-11 — a feedback ticket is stored as "feedback" and answered as the enum
- **Rules:** `create_ticket` R1a, R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No ticket in W1 (commit point after this line).

**When**
- `result = svc.create_ticket(db, workspace=W1, user=FIN, payload=HelpTicketCreate(title="Nice app", description="Love the reports", type=FEEDBACK))`.

**Then**
1. returns: `result.type == FEEDBACK`, `result.status == PENDING`.
2. returns: `result.created_by == FIN.id`, `result.creator_name == "Fatima"`.
3. committed: the row with id `result.id` has `type == "feedback"`, `status == "pending"`.

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

### HTS-L-08 — status opened keeps only opened tickets (revised 2026-11-26)
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = closed ticket `"HELP-2026-001"`.
2. TB = opened ticket `"HELP-2026-002"`.
3. TC = ticket `"HELP-2026-003"` (pending).

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=OPENED, limit=1000)`.

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

### HTS-L-17 — a listed ticket with a stored status the enum does not know cannot be answered
- **Rules:** `list_tickets` R3 (`create_ticket` R3a)
- **Kind:** error
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `status "open"`.

**When**
- `svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. raises: `PydanticValidationError`.

### HTS-L-18 — status pending keeps only pending tickets
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = opened ticket `"HELP-2026-001"`.
2. TB = ticket `"HELP-2026-002"` (pending).
3. TC = closed ticket `"HELP-2026-003"`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=PENDING, limit=1000)`.

**Then**
1. returns: `idset(result) == {TB.id}`.

### HTS-L-19 — type feedback keeps only feedback tickets, each answered with its type
- **Rules:** `list_tickets` R1a, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"` (support).
2. TB = ticket `"HELP-2026-002"`, but `type "feedback"`.
3. TC = ticket `"HELP-2026-003"` (support).

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, ticket_type=FEEDBACK, limit=1000)`.

**Then**
1. returns: `idset(result) == {TB.id}`.
2. returns: `[t.type for t in result] == [FEEDBACK]`.

### HTS-L-20 — type support keeps only support tickets
- **Rules:** `list_tickets` R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `type "feedback"`.
2. TB = ticket `"HELP-2026-002"` (support).
3. TC = ticket `"HELP-2026-003"`, but `type "feedback"`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, ticket_type=SUPPORT, limit=1000)`.

**Then**
1. returns: `idset(result) == {TB.id}`.

### HTS-L-21 — status, type and the creator restriction apply together, before the limit
- **Rules:** `list_tickets` R1a, R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = opened ticket `"HELP-2026-001"`, but `type "feedback"`, `created_at datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)`.
2. M2 = opened ticket `"HELP-2026-002"`, but `type "feedback"`, `created_at datetime(2026, 5, 2, 9, 0, tzinfo=timezone.utc)`.
3. H1 = opened ticket `"HELP-2026-003"`, but `type "support"`, `created_at datetime(2026, 5, 10, 9, 0, tzinfo=timezone.utc)`.
4. H2 = ticket `"HELP-2026-004"`, but `type "feedback"`, `created_at datetime(2026, 5, 11, 9, 0, tzinfo=timezone.utc)` (pending).
5. H3 = opened ticket `"HELP-2026-005"`, but `type "feedback"`, `created_by MGR.id`, `created_at datetime(2026, 5, 12, 9, 0, tzinfo=timezone.utc)`.

**When**
- `result = svc.list_tickets(db, workspace_id=W1.id, user=CR, role=GT_R, status=OPENED, ticket_type=FEEDBACK, limit=2)`.

**Then**
1. returns: `idset(result) == {M1.id, M2.id}`.

### HTS-L-22 — a plain string for ticket_type raises AttributeError when called directly
- **Rules:** `list_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.

**When**
- `svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, ticket_type="feedback", limit=1000)`.

**Then**
1. raises: `AttributeError`.

### HTS-L-23 — a plain string for status raises AttributeError when called directly
- **Rules:** `list_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.

**When**
- `svc.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status="pending", limit=1000)`.

**Then**
1. raises: `AttributeError`.

## `HelpTicketService.get_ticket`

### HTS-G-01 — the creator gets their ticket with every field, not a neighbour (revised 2026-11-26)
- **Rules:** `get_ticket` R1, `create_ticket` R3
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
4. returns: `result.status == PENDING`, `result.type == SUPPORT`, `result.created_by == CR.id`, `result.creator_name == "Rahim"`.

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

### HTS-G-17 — a ticket with a stored status the enum does not know cannot be answered
- **Rules:** `get_ticket` R4 (`create_ticket` R3a)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R)`.

**Then**
1. raises: `PydanticValidationError`.

### HTS-G-18 — a ticket with a stored type the enum does not know cannot be answered
- **Rules:** `get_ticket` R4 (`create_ticket` R3a)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `type "bug"`.

**When**
- `svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R)`.

**Then**
1. raises: `PydanticValidationError`.

### HTS-G-19 — a closed feedback ticket is returned with its status and type
- **Rules:** `get_ticket` R1 (whatever status or type), `create_ticket` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`, but `type "feedback"`.

**When**
- `result = svc.get_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result.id == T.id`, `result.status == CLOSED`, `result.type == FEEDBACK`.
2. returns: `result.closed_by == MGR.id`, `result.closed_at == PAST`.

## `HelpTicketService.update_ticket`

### HTS-U-01 — the creator changes title, description and category; committed (revised 2026-11-26)
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
3. committed: T has `title == "Toner low"`, `description == "Grey prints"`, `category == "supplies"`, `status == "pending"`, `type == "support"`.
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

### HTS-U-03 — an empty payload changes nothing (revised 2026-11-26)
- **Rules:** `update_ticket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate())`.

**Then**
1. returns: `result.id == T.id`, `result.title == "Printer jam"`, `result.status == PENDING`.
2. unchanged: unchanged(T).

### HTS-U-04 — a ground-team-manager closes a member's opened ticket (revised 2026-11-26)
- **Rules:** `update_ticket` R5-1 [BUG-3251], R5a, R7
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises HelpTicketStatusChangeForbiddenError: only platform admins may change status today)

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. returns: `result.status == CLOSED`, `result.closed_by == MGR.id`, `result.creator_name == "Rahim"`.
2. committed: T has `status == "closed"`, `closed_by == MGR.id`, `title == "Printer jam"`.
3. committed: T has `closed_at is not None`.

### HTS-U-05 — an owner reopens a closed ticket: closed_at and closed_by are cleared (revised 2026-11-26)
- **Rules:** `update_ticket` R5-1 [BUG-3251], R5a
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises HelpTicketStatusChangeForbiddenError: only platform admins may change status today)

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.closed_at is None`, `result.closed_by is None`.
2. committed: T has `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTS-U-06 — a platform admin without a role closes a member's opened ticket (revised 2026-11-26)
- **Rules:** `update_ticket` R5, R5a, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. returns: `result.status == CLOSED`, `result.closed_by == ADM.id`, `result.creator_name == "Rahim"`.
2. returns: `result.closed_at is not None`.
3. committed: T has `status == "closed"`, `closed_by == ADM.id`, `title == "Printer jam"`.
4. committed: T has `closed_at is not None`.

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

### HTS-U-09 — asking an opened ticket to be opened is refused and changes nothing (revised 2026-11-26)
- **Rules:** `update_ticket` R5b, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `type(exc.value) is HelpTicketInvalidTransitionError`.
3. raises: `str(exc.value) == "Cannot transition from opened to opened."`.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-10 — closing an already closed ticket is refused and keeps who closed it and when (revised 2026-11-26)
- **Rules:** `update_ticket` R5b, R6 (HR-9; BUG-1576 resolved)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from closed to closed."`.
3. re-read T: `closed_by == MGR.id`.
4. re-read T: `closed_at == PAST`.
5. unchanged: unchanged(T).

### HTS-U-11 — closed_at is the true moment whatever the database's time zone (revised 2026-11-26)
- **Rules:** `update_ticket` R6 [BUG-1577]
- **Kind:** bug
- **Expect:** xfail BUG-1577
- **Fails today on:** Then 2 (5 hours off under `America/New_York`)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`.
2. T = opened ticket `"HELP-2026-001"` (commit point after this line).
3. Real clock: no close clock in this card.

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=CLOSED))`.

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
- **Rules:** `update_ticket` R3a [BUG-1863], Errors row 7
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

### HTS-U-22 — a manager's text change combined with a close is refused whole: the ticket stays opened (revised 2026-11-26)
- **Rules:** `update_ticket` R3a (D3), R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(title="Work order missing", status=CLOSED))`.

**Then**
1. raises: `PermissionError`.
2. raises: `isinstance(exc.value, (HelpTicketStatusChangeForbiddenError, HelpTicketForbiddenError))`.
3. re-read T: `status == "opened"`, `closed_at is None`, `closed_by is None`, `title == "Printer jam"`.
4. unchanged: unchanged(T).
5. nothing written.

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

### HTS-U-33 — a failing commit rolls back and nothing is saved (revised 2026-11-26)
- **Rules:** `update_ticket` R7, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- failing commit: `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(T).
4. re-read T: `status == "opened"`, `closed_by is None`.

### HTS-U-34 — a failing re-read after the commit leaves the change saved (revised 2026-11-26)
- **Rules:** `update_ticket` R7, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- failing refresh: `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: T has `status == "closed"`, `closed_by == ADM.id`.

### HTS-U-35 — the creator, a ground-team member, may not move their own ticket; rolled back
- **Rules:** `update_ticket` R5, TC3, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).
2. extra row X.

**When**
- refusal spy: raises `HelpTicketStatusChangeForbiddenError`: `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. session: `X not in db`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError` (type only).
3. mock called: `rb.call_count >= 1`.
4. count: x_gone.
5. unchanged: unchanged(T).
6. nothing written.

### HTS-U-36 — a finance creator's close with a text change is refused whole
- **Rules:** `update_ticket` R5, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`, but `created_by FIN.id` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=FIN, role=FIN_R, payload=HelpTicketUpdate(title="Toner low", status=CLOSED))`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError` (type only).
3. re-read T: `title == "Printer jam"`, `status == "opened"`, `closed_by is None`.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-37 — the creator sending the status the ticket already has gets the permission refusal, not the transition one
- **Rules:** `update_ticket` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(status=PENDING))`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError` (type only).
3. unchanged: unchanged(T).

### HTS-U-38 — a ground-team-manager opens a member's pending ticket
- **Rules:** `update_ticket` R5-1 [BUG-3251], R5a
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises HelpTicketStatusChangeForbiddenError: only platform admins may change status today)

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.closed_at is None`, `result.closed_by is None`.
2. committed: T has `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTS-U-39 — an owner (not the creator) closes a member's opened ticket
- **Rules:** `update_ticket` R5-1 [BUG-3251], R5a
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises HelpTicketStatusChangeForbiddenError: only platform admins may change status today)

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. returns: `result.status == CLOSED`, `result.closed_by == OWN.id`.
2. committed: T has `status == "closed"`, `closed_by == OWN.id`.
3. committed: T has `closed_at is not None`.

### HTS-U-40 — a ground-team-manager reopens a closed ticket
- **Rules:** `update_ticket` R5-1 [BUG-3251], R5a
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises HelpTicketStatusChangeForbiddenError: only platform admins may change status today)

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.closed_by is None`.
2. committed: T has `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTS-U-41 — a ground-team-manager who created the ticket opens it
- **Rules:** `update_ticket` R5-1 [BUG-3251] (creator or not)
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises HelpTicketStatusChangeForbiddenError: only platform admins may change status today)

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by MGR.id` (pending; commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.creator_name == "Karim"`.
2. committed: T has `status == "opened"`.

### HTS-U-42 — a ground-team-manager asking pending → closed gets the transition refusal
- **Rules:** `update_ticket` R5-1 [BUG-3251], R5b
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (today the permission refusal HelpTicketStatusChangeForbiddenError comes first)

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=MGR, role=GTM_R, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from pending to closed."`.
3. unchanged: unchanged(T).

### HTS-U-43 — the workspace's owner by `owner_user_id`, with a finance role, closes their opened ticket
- **Rules:** `update_ticket` R5-1 [BUG-3251] (workspace owner per `help_ticket_manager.spec.md` R5g; spec gap 3)
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises HelpTicketStatusChangeForbiddenError: only platform admins may change status today)

**Given**
1. `W1.owner_user_id = FIN.id`, then `db.flush()`.
2. T = opened ticket `"HELP-2026-001"`, but `created_by FIN.id` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=FIN, role=FIN_R, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. returns: `result.status == CLOSED`, `result.closed_by == FIN.id`.
2. committed: T has `status == "closed"`, `closed_by == FIN.id`.

### HTS-U-44 — a platform admin opens a pending ticket; no close stamp is touched
- **Rules:** `update_ticket` R5a (pending → opened), R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `closed_at PAST`, `closed_by MGR.id` (pending with leftover stamps; commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.closed_by == MGR.id`.
2. committed: T has `status == "opened"`, `closed_at == PAST`, `closed_by == MGR.id`, `title == "Printer jam"`.

### HTS-U-45 — a platform admin reopens a closed ticket: stamps cleared
- **Rules:** `update_ticket` R5a (closed → opened)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.closed_at is None`, `result.closed_by is None`.
2. committed: T has `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTS-U-46 — a platform admin who created the ticket changes text and status together
- **Rules:** `update_ticket` R5a (text in the same payload), R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by ADM.id` (pending; commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(title="Toner low", status=OPENED))`.

**Then**
1. returns: `result.title == "Toner low"`, `result.status == OPENED`.
2. committed: T has `title == "Toner low"`, `status == "opened"`, `description == "It jams"`.

### HTS-U-47 — pending → pending is refused
- **Rules:** `update_ticket` R5b
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=PENDING))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from pending to pending."`.
3. unchanged: unchanged(T).

### HTS-U-48 — pending → closed is refused, rolled back, other pending changes discarded
- **Rules:** `update_ticket` R5b, TC3, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).
2. extra row X.

**When**
- refusal spy: raises `HelpTicketInvalidTransitionError`: `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. session: `X not in db`.
2. raises: `str(exc.value) == "Cannot transition from pending to closed."`.
3. mock called: `rb.call_count >= 1`.
4. count: x_gone.
5. unchanged: unchanged(T).
6. nothing written.

### HTS-U-49 — opened → pending is refused
- **Rules:** `update_ticket` R5b
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=PENDING))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from opened to pending."`.
3. unchanged: unchanged(T).

### HTS-U-50 — closed → pending is refused and the stamps stay
- **Rules:** `update_ticket` R5b
- **Kind:** error
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=PENDING))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from closed to pending."`.
3. re-read T: `status == "closed"`, `closed_at == PAST`, `closed_by == MGR.id`.
4. unchanged: unchanged(T).

### HTS-U-51 — a refused transition does not apply the creator's text in the same payload
- **Rules:** `update_ticket` R5b (text included)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by ADM.id` (pending; commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(title="Toner low", status=CLOSED))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from pending to closed."`.
3. re-read T: `title == "Printer jam"`, `status == "pending"`.
4. unchanged: unchanged(T).

### HTS-U-52 — a status on a ticket whose stored status is unknown is refused
- **Rules:** `update_ticket` R5c, Errors row 6
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from invalid status 'open'."`.
3. re-read T: `status == "open"`.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-53 — a text change on a ticket with an unknown stored status is saved, then the answer fails
- **Rules:** `update_ticket` R5c, R7 (`create_ticket` R3a, TC5)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate(title="Toner low"))`.

**Then**
1. raises: `PydanticValidationError`.
2. committed: T has `title == "Toner low"`, `status == "open"`.

### HTS-U-54 — a plain-string status behaves as the enum of that value
- **Rules:** `update_ticket` R5d
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate.model_construct(status="closed"))`.

**Then**
1. returns: `result.status == CLOSED`, `result.closed_by == ADM.id`.
2. committed: T has `status == "closed"`, `closed_by == ADM.id`.

### HTS-U-55 — a plain string that is not a status raises ValueError, not the transition error
- **Rules:** `update_ticket` R5d
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate.model_construct(status="open"))`.

**Then**
1. raises: `ValueError`.
2. raises: `not isinstance(exc.value, HelpTicketInvalidTransitionError)`.
3. unchanged: unchanged(T).
4. nothing written.

### HTS-U-56 — a type key in the request is dropped: the stored type stays
- **Rules:** `update_ticket` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `type "feedback"` (commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate.model_validate({"title": "Toner low", "type": "support"}))`.

**Then**
1. returns: `result.type == FEEDBACK`, `result.title == "Toner low"`.
2. committed: T has `type == "feedback"`, `title == "Toner low"`.

### HTS-U-57 — an owner's description change combined with a close is refused whole
- **Rules:** `update_ticket` R3a (D3), R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=OWN, role=OWNER_R, payload=HelpTicketUpdate(description="Nothing happened", status=CLOSED))`.

**Then**
1. raises: `PermissionError`.
2. raises: `isinstance(exc.value, (HelpTicketStatusChangeForbiddenError, HelpTicketForbiddenError))`.
3. re-read T: `description == "It jams"`, `status == "opened"`, `closed_by is None`.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-58 — a platform admin's text change with a valid status is refused: the status does not change
- **Rules:** `update_ticket` R3a [BUG-1863] (D3), Errors row 7
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the description is replaced and the ticket opened)

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(description="Nothing happened", status=OPENED))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. re-read T: `status == "pending"`, `description == "It jams"`.
4. unchanged: unchanged(T).

### HTS-U-59 — a platform admin's text change with a refused transition writes nothing
- **Rules:** `update_ticket` R3a (D3), R5b
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=ADM, role=None, payload=HelpTicketUpdate(description="Nothing happened", status=CLOSED))`.

**Then**
1. raises: `Exception`.
2. raises: `isinstance(exc.value, (HelpTicketForbiddenError, HelpTicketInvalidTransitionError))`.
3. re-read T: `description == "It jams"`, `status == "pending"`.
4. unchanged: unchanged(T).
5. nothing written.

### HTS-U-60 — a caller object without `is_platform_admin` counts as not an admin: its status change is refused
- **Rules:** `update_ticket` Inputs `user` (spec G2), R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=SimpleNamespace(id=CR.id, name="Rahim"), role=GT_R, payload=HelpTicketUpdate(status=OPENED))` (`SimpleNamespace` from `types`; it has no `is_platform_admin`).

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError` (type only).
3. unchanged: unchanged(T).
4. nothing written.

### HTS-U-61 — a caller object without `is_platform_admin` that created the ticket may still change its text
- **Rules:** `update_ticket` Inputs `user` (spec G2), R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `result = svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=SimpleNamespace(id=CR.id, name="Rahim"), role=GT_R, payload=HelpTicketUpdate(title="Toner low"))` (`SimpleNamespace` from `types`; it has no `is_platform_admin`).

**Then**
1. returns: `result.id == T.id`, `result.title == "Toner low"`, `result.status == PENDING`.
2. committed: T has `title == "Toner low"`, `status == "pending"`.

### HTS-U-62 — a database error before the commit rolls back, reaches the caller, and discards other pending changes
- **Rules:** `update_ticket` R7, TC3 (any exception, not only the manager's)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. extra row X.

**When**
- `svc.update_ticket(db, workspace_id=W1.id, ticket_id=T.id, user=CR, role=GT_R, payload=HelpTicketUpdate.model_construct(title=None))` (the schema is skipped, so `null` reaches the NOT NULL column).

**Then**
1. raises: `IntegrityError`.
2. session: `X not in db`.
3. count: x_gone (no test-level rollback before this line).
4. nothing written.
5. session: `db.execute(text("SELECT 1")).scalar() == 1`.
6. unchanged: unchanged(T).

## `HelpTicketService.update_platform_ticket`

### HTS-V-01 — a platform admin closes another workspace's opened ticket; committed, not a neighbour
- **Rules:** `update_platform_ticket` R1, R2, R5, R6, TC1, TC2
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = opened ticket `"HELP-2026-001"`, but `title "Other"`.
2. T = opened ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
3. TB = opened ticket `"HELP-2026-002"`, but `title "Third"` (commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. returns: `type(result) is HelpTicketResponse`.
2. returns: `result.id == T.id`, `result.workspace_id == W2.id`, `result.status == CLOSED`, `result.closed_by == ADM.id`.
3. returns: `result.creator_name == "Rahim"`, `result.type == SUPPORT`, `result.updated_at is not None`.
4. returns: `"workspace_name" not in result.model_dump()`.
5. committed: T has `status == "closed"`, `closed_by == ADM.id`, `title == "Printer jam"`.
6. committed: T has `closed_at is not None`.
7. committed: TA has `status == "opened"`, `closed_by is None`; TB has `status == "opened"`, `closed_by is None`.

### HTS-V-02 — the caller is not checked to be a platform admin: a finance profile opens a ticket
- **Rules:** `update_platform_ticket` R2, R5a (pending → opened)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=FIN, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.closed_by is None`.
2. committed: T has `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTS-V-03 — reopening a closed ticket clears the stamps
- **Rules:** `update_platform_ticket` R2 (R5a closed → opened)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`, but `workspace_id W2.id` (commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. returns: `result.status == OPENED`, `result.closed_at is None`, `result.closed_by is None`.
2. committed: T has `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTS-V-04 — status null changes nothing
- **Rules:** `update_platform_ticket` R2 (no status change), R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=None))`.

**Then**
1. returns: `result.id == T.id`, `result.status == CLOSED`.
2. unchanged: unchanged(T).

### HTS-V-05 — closing a closed ticket is refused, rolled back, other pending changes discarded
- **Rules:** `update_platform_ticket` R2 (R5b), R6, TC3, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"` (commit point after this line).
2. extra row X.

**When**
- refusal spy: raises `HelpTicketInvalidTransitionError`: `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. session: `X not in db`.
2. raises: `str(exc.value) == "Cannot transition from closed to closed."`.
3. mock called: `rb.call_count >= 1`.
4. count: x_gone.
5. re-read T: `closed_at == PAST`, `closed_by == MGR.id`.
6. unchanged: unchanged(T).
7. nothing written.

### HTS-V-06 — pending → closed is refused
- **Rules:** `update_platform_ticket` R2 (R5b), Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `workspace_id W2.id` (pending; commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from pending to closed."`.
3. unchanged: unchanged(T).

### HTS-V-07 — a status on a ticket whose stored status is unknown is refused
- **Rules:** `update_platform_ticket` R2 (R5c), Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"` (commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from invalid status 'open'."`.
3. unchanged: unchanged(T).

### HTS-V-08 — an unknown id is not found, rolled back, other pending changes discarded
- **Rules:** `update_platform_ticket` R1, TC3, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).
2. extra row X.

**When**
- refusal spy: raises `HelpTicketNotFoundError`: `svc.update_platform_ticket(db, ticket_id=MISSING, user=ADM, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. session: `X not in db`.
2. raises: `type(exc.value) is HelpTicketNotFoundError`.
3. raises: `str(exc.value) == NOTFOUND`.
4. mock called: `rb.call_count >= 1`.
5. count: x_gone.
6. unchanged: unchanged(T).
7. nothing written.

### HTS-V-09 — id 0 is not found
- **Rules:** `update_platform_ticket` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=0, user=ADM, payload=HelpTicketUpdate(status=OPENED))`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.
3. unchanged: unchanged(T).

### HTS-V-10 — an empty payload changes nothing
- **Rules:** `update_platform_ticket` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate())`.

**Then**
1. returns: `result.id == T.id`, `result.status == OPENED`, `result.title == "Printer jam"`.
2. unchanged: unchanged(T).

### HTS-V-11 — a platform admin may not change a member's description
- **Rules:** `update_platform_ticket` R3a [BUG-3270], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-3270
- **Fails today on:** Then 1 (no error: the description is replaced and committed)

**Given**
1. T = ticket `"HELP-2026-001"`, but `workspace_id W2.id` (commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(description="Work order missing"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).
4. nothing written.

### HTS-V-12 — a member's text with a valid status is refused whole: the status stays
- **Rules:** `update_platform_ticket` R3a [BUG-3270] (D3), TC3
- **Kind:** bug
- **Expect:** xfail BUG-3270
- **Fails today on:** Then 1 (no error: the description is replaced and the ticket opened)

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).
2. extra row X.

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(description="Work order missing", status=OPENED))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. session: `X not in db`.
3. re-read T: `status == "pending"`, `description == "It jams"`.
4. unchanged: unchanged(T).

### HTS-V-13 — a member's text with a refused transition writes nothing
- **Rules:** `update_platform_ticket` R3a (D3), R2 (R5b)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"` (pending; commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(description="Work order missing", status=CLOSED))`.

**Then**
1. raises: `Exception`.
2. raises: `isinstance(exc.value, (HelpTicketForbiddenError, HelpTicketInvalidTransitionError))`.
3. re-read T: `description == "It jams"`, `status == "pending"`.
4. unchanged: unchanged(T).

### HTS-V-14 — a ticket whose creator is gone has its text changed by nobody
- **Rules:** `update_platform_ticket` R3a [BUG-3270]
- **Kind:** bug
- **Expect:** xfail BUG-3270
- **Fails today on:** Then 1 (no error: the title is replaced)

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None` (commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(title="Work order missing"))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. unchanged: unchanged(T).

### HTS-V-15 — category null from a non-creator counts as a text change
- **Rules:** `update_platform_ticket` R3a [BUG-3270]
- **Kind:** bug
- **Expect:** xfail BUG-3270
- **Fails today on:** Then 1 (no error: the category is cleared)

**Given**
1. T = ticket `"HELP-2026-001"` (commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(category=None))`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. re-read T: `category == "hardware"`.
3. unchanged: unchanged(T).

### HTS-V-16 — the admin who created the ticket changes its text
- **Rules:** `update_platform_ticket` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by ADM.id` (commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(title="Toner low", category=None))`.

**Then**
1. returns: `result.title == "Toner low"`, `result.category is None`, `result.creator_name == "Sam"`.
2. committed: T has `title == "Toner low"`, `category is None`, `description == "It jams"`, `status == "pending"`.

### HTS-V-17 — a type key in the request is dropped: the stored type stays
- **Rules:** `update_platform_ticket` R3 (R2a)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `type "feedback"` (pending; commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate.model_validate({"status": "opened", "type": "support"}))`.

**Then**
1. returns: `result.type == FEEDBACK`, `result.status == OPENED`.
2. committed: T has `type == "feedback"`, `status == "opened"`.

### HTS-V-18 — a failing commit rolls back and nothing is saved
- **Rules:** `update_platform_ticket` R6, TC4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- failing commit: `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count >= 1`.
3. unchanged: unchanged(T).
4. re-read T: `status == "opened"`, `closed_by is None`.

### HTS-V-19 — a failing re-read after the commit leaves the change saved
- **Rules:** `update_platform_ticket` R6, TC5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"` (commit point after this line).

**When**
- failing refresh: `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. committed: T has `status == "closed"`, `closed_by == ADM.id`.

### HTS-V-20 — a text change on a ticket with an unknown stored status is saved, then the answer fails
- **Rules:** `update_platform_ticket` R6 (`create_ticket` R3a, TC5)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"`, `created_by ADM.id` (commit point after this line).

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(title="Toner low"))`.

**Then**
1. raises: `PydanticValidationError`.
2. committed: T has `title == "Toner low"`, `status == "open"`.

### HTS-V-21 — a sent title is stored trimmed on the platform path (pass-through)
- **Rules:** `update_platform_ticket` R4 [BUG-1574]
- **Kind:** bug
- **Expect:** xfail BUG-1574
- **Fails today on:** Then 2 (stored as typed: `"  Toner low  "`)

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by ADM.id` (commit point after this line).

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(title="  Toner low  "))`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `title == "Toner low"`.

### HTS-V-22 — closed_at is the true moment whatever the database's time zone (pass-through)
- **Rules:** `update_platform_ticket` R2 (`update_ticket` R6 [BUG-1577])
- **Kind:** bug
- **Expect:** xfail BUG-1577
- **Fails today on:** Then 2 (5 hours off under `America/New_York`)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`.
2. T = opened ticket `"HELP-2026-001"` (commit point after this line).
3. Real clock: no close clock in this card.

**When**
- `result = svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate(status=CLOSED))`.

**Then**
1. returns: `result.status == CLOSED`.
2. re-read T: `abs(closed_at - created_at) < timedelta(seconds=60)`.

### HTS-V-23 — a database error before the commit rolls back, reaches the caller, and discards other pending changes
- **Rules:** `update_platform_ticket` R6, TC3 (any exception, not only the manager's)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by ADM.id` (commit point after this line).
2. extra row X.

**When**
- `svc.update_platform_ticket(db, ticket_id=T.id, user=ADM, payload=HelpTicketUpdate.model_construct(title=None))` (the schema is skipped, so `null` reaches the NOT NULL column).

**Then**
1. raises: `IntegrityError`.
2. session: `X not in db`.
3. count: x_gone (no test-level rollback before this line).
4. nothing written.
5. session: `db.execute(text("SELECT 1")).scalar() == 1`.
6. unchanged: unchanged(T).

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

### HTS-P-02 — each entry carries the ticket's own fields (revised 2026-11-26)
- **Rules:** `list_platform_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = svc.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `[t.id for t in result if t.id == T1.id] == [T1.id]`.
2. returns: the entry E with `E.id == T1.id` has `E.ticket_number == "HELP-2026-001"`, `E.workspace_id == W2.id`, `E.title == "Printer jam"`, `E.status == PENDING`, `E.type == SUPPORT`, `E.created_by == CR.id`.

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

### HTS-P-09 — status opened keeps only opened tickets
- **Rules:** `list_platform_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"` (pending).
2. T2 = opened ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
3. T3 = closed ticket `"HELP-2026-002"`.

**When**
- `result = svc.list_platform_tickets(db, status=OPENED, search=TAG, limit=1000)`.

**Then**
1. returns: `own(result) == {T2.id}` (OWN = {T1.id, T2.id, T3.id}).

### HTS-P-10 — status pending keeps only pending tickets
- **Rules:** `list_platform_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = opened ticket `"HELP-2026-001"`.
2. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id` (pending).
3. T3 = closed ticket `"HELP-2026-002"`.

**When**
- `result = svc.list_platform_tickets(db, status=PENDING, search=TAG, limit=1000)`.

**Then**
1. returns: `own(result) == {T2.id}` (OWN = {T1.id, T2.id, T3.id}).

### HTS-P-11 — type feedback keeps only feedback tickets, answered with their type
- **Rules:** `list_platform_tickets` R1a, R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"` (support).
2. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `type "feedback"`.
3. T3 = ticket `"HELP-2026-002"` (support).

**When**
- `result = svc.list_platform_tickets(db, ticket_type=FEEDBACK, search=TAG, limit=1000)`.

**Then**
1. returns: `own(result) == {T2.id}` (OWN = {T1.id, T2.id, T3.id}).
2. returns: `[t.type for t in result if t.id == T2.id] == [FEEDBACK]`.

### HTS-P-12 — type, status and search must all match
- **Rules:** `list_platform_tickets` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M = opened ticket `"HELP-2026-001"`, but `type "feedback"`.
2. H1 = opened ticket `"HELP-2026-002"` (support).
3. H2 = ticket `"HELP-2026-003"`, but `type "feedback"` (pending).
4. `W3 = make_workspace(db, name="Omega")` (a name without TAG).
5. H3 = opened ticket `"HELP-2026-001"`, but `workspace_id W3.id`, `type "feedback"` (matches status and type, not the search).

**When**
- `result = svc.list_platform_tickets(db, status=OPENED, ticket_type=FEEDBACK, search=TAG, limit=1000)`.

**Then**
1. returns: `own(result) == {M.id}` (OWN = {M.id, H1.id, H2.id, H3.id}).

### HTS-P-13 — a plain string for ticket_type raises AttributeError when called directly
- **Rules:** `list_platform_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.

**When**
- `svc.list_platform_tickets(db, ticket_type="feedback", search=TAG, limit=1000)`.

**Then**
1. raises: `AttributeError`.

### HTS-P-14 — a listed ticket with a stored status the enum does not know cannot be answered
- **Rules:** `list_platform_tickets` R1 (`create_ticket` R3a)
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`, but `status "open"`.

**When**
- `svc.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. raises: `PydanticValidationError`.

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

### HTS-Q-05 — a closed feedback ticket is returned with its status and type
- **Rules:** `get_platform_ticket` R1 (whatever status or type)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `type "feedback"`.

**When**
- `result = svc.get_platform_ticket(db, ticket_id=T.id)`.

**Then**
1. returns: `result.id == T.id`, `result.status == CLOSED`, `result.type == FEEDBACK`.
2. returns: `result.closed_by == MGR.id`, `result.workspace_name == f"Delta {TAG}"`.

### HTS-Q-06 — a ticket with a stored status the enum does not know cannot be answered
- **Rules:** `get_platform_ticket` R1 (`create_ticket` R3a)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"`.

**When**
- `svc.get_platform_ticket(db, ticket_id=T.id)`.

**Then**
1. raises: `PydanticValidationError`.


## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Endpoint translation `{"detail": …}` (workspace) | `/help/tickets` endpoints | `HelpTicketNotFoundError` → 404, `HelpTicketForbiddenError` → 403 (incl. BUG-1863's text change), `HelpTicketStatusChangeForbiddenError` → 403, `HelpTicketInvalidTransitionError` → 400 |
| Endpoint translation (platform) and `get_platform_admin` guard | `/platform/help/tickets` endpoints | 403 `Platform admin access required` for a non-admin; PATCH: 404, 400, and 403 for `HelpTicketForbiddenError` once BUG-3270 is fixed (no mapping today) |
| `limit` / `skip` bounds (HR-7); query enums `status` / `type` | endpoints | 422 for `limit=0`, `limit=201`, `skip=-1`; `status=open` or `type=bug` refused by request validation (BUG-461) |
| `IntegrityError` handler for `null` title today (P1) | global handler | replaced by 422 after BUG-1575 |
| `create_with_user` R3 [BUG-1440] (concurrent numbers) | integration test | two connections |
| FU-1: `can_access_ticket` in `AttachmentManager` after BUG-1863 | `AttachmentManager` spec | who may attach to a support ticket |
| Role lookup for BUG-3251 (active membership, BUG-1885); BUG-2103 / BUG-3250 (workspace owner sees every ticket) | `help_ticket_manager.spec.md`, endpoints | the service only passes what the endpoint computed |

## Retired IDs
None. (U-09, U-10, U-22 keep their ids: each still tests the same state and payload; their expected outcome changed with the workflow.)

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Facts for the test designer | **Closed (Revision 3):** the spec now names `app.models.enums` for `HelpTicketStatusEnum`, `HelpTicketTypeEnum`. | — |
| 2 | `create_ticket` R3 | **Closed (Revision 2):** the spec (revision 2026-11-04) marks the "re-read finds nothing" fallback of `create_ticket` R3 / `update_ticket` R7 not unit-testable | No card, by the spec's decision. |
| 3 | `update_ticket` R5-1 | **Closed (Revision 4) by spec G1:** the workspace's `owner_user_id` has the status right (as manager R5g); the fix adds keyword `role`. Was: the service spec names only role `owner` / `ground-team-manager` as status rights; `help_ticket_manager.spec.md` R5g also grants the workspace's `owner_user_id` (BUG-2103), which the service would have to pass. Not stated here. | Not blocking: U-43 follows the manager spec (coordinator's alignment, 2026-11-26); the owner is also the ticket's creator, so the see-right (BUG-2103, unfixed) does not decide the result. The describer should add the rule (or say the service does not pass it). |
| 4 | `update_ticket` Inputs (`user`) | **Closed (Revision 4) by spec G2:** the see-right and the status flag both use `getattr(user, "is_platform_admin", False)`; cards HTS-U-60, HTS-U-61. Was: "A profile without `is_platform_admin` counts as not an admin" — the spec does not say whether the see-right check (`get_ticket` R1, reached first) tolerates a profile without the attribute. | Resolved: HTS-U-60, HTS-U-61. |
| 5 | `update_ticket` R5 / manager R5h | **Closed (Revision 4) by spec G3** (covered by G1: cards assert the type only). Was: the R5 refusal's message changes with BUG-3251 (`You may not change the status of this help ticket.` in the manager spec; not in this spec). | Not blocking: R5 cards assert the type only, per spec Facts; the message is the manager's to test. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `create_ticket` | R1 | HTS-C-01, HTS-C-11; BUG-1441 pass-through HTS-C-05 |
| `create_ticket` | R1a | HTS-C-01 (support default), HTS-C-11 (feedback) |
| `create_ticket` | R2 [BUG-1574] | HTS-C-06, HTS-C-07, HTS-C-08, HTS-C-09; kept HTS-C-10 |
| `create_ticket` | R3 | HTS-C-01, HTS-G-01, HTS-G-19 (fallback branch: not unit-testable per spec, gap 2 closed) |
| `create_ticket` | R3a | not reachable through create (spec); per method: HTS-L-17, HTS-G-17, HTS-G-18, HTS-U-53, HTS-V-20, HTS-P-14, HTS-Q-06 |
| `create_ticket` | R4 (TC3, TC4, TC5) | HTS-C-02, HTS-C-03, HTS-C-04 |
| `create_ticket` | Errors (unknown user) | HTS-C-02 |
| `list_tickets` | R1 | HTS-L-01 … HTS-L-11, HTS-L-18, HTS-L-21; BUG-1442 pass-through HTS-L-16 |
| `list_tickets` | R1a | HTS-L-19, HTS-L-20, HTS-L-21 |
| `list_tickets` | R2 [BUG-1578] | HTS-L-12 |
| `list_tickets` | R3 | HTS-L-13, HTS-L-19 (type), HTS-L-17 (R3a) |
| `list_tickets` | R4 (TC6) | HTS-L-14 |
| `list_tickets` | Errors (DataError; plain string) | HTS-L-15; HTS-L-22, HTS-L-23 |
| `get_ticket` | R1 | HTS-G-01, HTS-G-02, HTS-G-03, HTS-G-04, HTS-G-19 |
| `get_ticket` | R2 | HTS-G-05, HTS-G-06, HTS-G-07, HTS-G-16 |
| `get_ticket` | R3 | HTS-G-08, HTS-G-09, HTS-G-10, HTS-G-11, HTS-G-12 |
| `get_ticket` | R4 | HTS-G-13, HTS-G-14, HTS-G-15, HTS-G-17, HTS-G-18 |
| `update_ticket` | R1 | HTS-U-12, HTS-U-13, HTS-U-14, HTS-U-15 |
| `update_ticket` | R2 | HTS-U-03, HTS-U-01 |
| `update_ticket` | R2a | HTS-U-56 |
| `update_ticket` | R3 | HTS-U-01, HTS-U-02, HTS-U-08, HTS-U-32, HTS-U-46 |
| `update_ticket` | R3a [BUG-1863] | HTS-U-16 … HTS-U-21, HTS-U-23 … HTS-U-25, HTS-U-58 |
| `update_ticket` | R3a (D3, holds today) | HTS-U-22, HTS-U-57, HTS-U-59 |
| `update_ticket` | R4 [BUG-1574] | HTS-U-26, HTS-U-27, HTS-U-28, HTS-U-29 |
| `update_ticket` | R4a [BUG-1575] | HTS-U-30, HTS-U-31; category null HTS-U-32 |
| `update_ticket` | R5 (admin may; others refused; null = no change) | HTS-U-06, HTS-U-35, HTS-U-36, HTS-U-37, HTS-U-07, HTS-U-08 |
| `update_ticket` | R5-1 [BUG-3251] | HTS-U-04, HTS-U-05, HTS-U-38, HTS-U-39, HTS-U-40, HTS-U-41, HTS-U-42, HTS-U-43 |
| `update_ticket` | R5a | HTS-U-06 (opened → closed), HTS-U-44 (pending → opened), HTS-U-45 (closed → opened), HTS-U-46 (text with it) |
| `update_ticket` | R5b | HTS-U-09, HTS-U-10, HTS-U-47, HTS-U-48, HTS-U-49, HTS-U-50, HTS-U-51 |
| `update_ticket` | R5c | HTS-U-52, HTS-U-53 |
| `update_ticket` | R5d | HTS-U-54, HTS-U-55 |
| `update_ticket` | R6 (HR-9, BUG-1576 resolved) | HTS-U-10 |
| `update_ticket` | R6 [BUG-1577] | HTS-U-11 |
| `update_ticket` | R7 (TC1, TC2, TC4, TC5) | HTS-U-01, HTS-U-06, HTS-U-33, HTS-U-34, HTS-U-53, HTS-U-62 |
| `update_ticket` | TC3 (rollback spy, `X not in db`) | HTS-U-35, HTS-U-48; non-manager error HTS-U-62; x_gone also HTS-U-12, HTS-U-14, HTS-U-25 |
| `update_ticket` | Inputs `user` (spec G2: no `is_platform_admin` = not an admin) | HTS-U-60, HTS-U-61 |
| `update_ticket` | Errors row 1 (not found) | HTS-U-12, HTS-U-13 |
| `update_ticket` | Errors row 2 (not allowed to see) | HTS-U-14, HTS-U-15 |
| `update_ticket` | Errors row 3 (status, no right) | HTS-U-35, HTS-U-36, HTS-U-37 |
| `update_ticket` | Errors row 4 (today, BUG-3251) | the buggy path, not carded on its own; intended HTS-U-04, HTS-U-05, HTS-U-38 … HTS-U-43; mixed payloads HTS-U-22, HTS-U-57 |
| `update_ticket` | Errors row 5 (transition) | HTS-U-09, HTS-U-10, HTS-U-47 … HTS-U-51 |
| `update_ticket` | Errors row 6 (stored status unknown) | HTS-U-52 |
| `update_ticket` | Errors row 7 (text by non-creator) | HTS-U-16 … HTS-U-21, HTS-U-23 … HTS-U-25, HTS-U-58 |
| `update_ticket` | Errors row 8 (today's `IntegrityError`) | not carded: the buggy path; intended behaviour HTS-U-30, HTS-U-31 |
| `update_platform_ticket` | R1 | HTS-V-01, HTS-V-08, HTS-V-09 |
| `update_platform_ticket` | R2 | HTS-V-01 … HTS-V-07; R5d via HTS-U-54, HTS-U-55 (same manager path); BUG-1577 pass-through HTS-V-22 |
| `update_platform_ticket` | R3 | HTS-V-10, HTS-V-16, HTS-V-17 |
| `update_platform_ticket` | R3a [BUG-3270] | HTS-V-11, HTS-V-12, HTS-V-14, HTS-V-15 |
| `update_platform_ticket` | R3a (D3, holds today) | HTS-V-13 |
| `update_platform_ticket` | R4 [BUG-1574, BUG-1575] | HTS-V-21; BUG-1575 is schema-only (same `HelpTicketUpdate`): HTS-U-30, HTS-U-31 |
| `update_platform_ticket` | R5 (HR-16) | HTS-V-01 |
| `update_platform_ticket` | R6 (TC1–TC5) | TC1/TC2 HTS-V-01; TC3 HTS-V-05, HTS-V-08, HTS-V-12, non-manager error HTS-V-23; TC4 HTS-V-18; TC5 HTS-V-19, HTS-V-20 |
| `update_platform_ticket` | Errors rows 1–5 | 1: HTS-V-08, HTS-V-09 · 2: HTS-V-05, HTS-V-06 · 3: HTS-V-07 · 4: HTS-V-11, HTS-V-12, HTS-V-14, HTS-V-15 · 5 (today's `IntegrityError`): not carded, intended HTS-U-30, HTS-U-31 |
| `list_platform_tickets` | R1 | HTS-P-01 … HTS-P-04, HTS-P-08 (default limit), HTS-P-09, HTS-P-10, HTS-P-14; BUG-1443 pass-through HTS-P-05 |
| `list_platform_tickets` | R1a | HTS-P-11, HTS-P-12 |
| `list_platform_tickets` | R2 | HTS-P-06 |
| `list_platform_tickets` | Errors (DataError; plain string) | HTS-P-07; HTS-P-13 |
| `get_platform_ticket` | R1 | HTS-Q-01, HTS-Q-05, HTS-Q-06 |
| `get_platform_ticket` | R2 | HTS-Q-02, HTS-Q-03, HTS-Q-04 |
