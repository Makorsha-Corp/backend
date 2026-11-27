# Test cases — `app/managers/help_ticket_manager.py`

> **Spec:** `tests/unit/managers/help_ticket_manager.spec.md` (source commit 41d5ac1)
> **Status:** READY
> **Revision:** 2 — status workflow `pending → opened → closed`, ticket `type`, owner answer OQ-66 (BUG-3251), BUG-2103 / BUG-3250 carried in, BUG-1576 closed
> **Counts:** 194 cases · 165 expected-to-pass · 29 expected-to-fail (bugs) · 13 deferred

> **Revision (2026-11-26).** The spec was revised for merge 41d5ac1 (statuses `pending` · `opened` · `closed`, new tickets `pending`; `type` `support` · `feedback`; `update_ticket` status rights, transition table and stamps) and for the owner's OQ-66 answer (BUG-3251). **Conventions rewritten:** `OPEN` removed (`HelpTicketStatusEnum("open")` now raises `ValueError`), PENDING / OPENED / CLOSED and SUPPORT / FEEDBACK added, a direct ticket is `pending` / `support`, new row **opened ticket**, new step **owner of W by X**, standing workspaces have no owner, new messages and imports (old gap 1, the enum import path, is answered by the spec). **Revised in place** (same id, "(revised 2026-11-26)" in the title): HTM-AC-18, L-07, L-08, L-09, P-02, P-04, C-01, C-02, U-01, U-06 … U-17, U-23, U-24, U-26, U-31, U-32, R-01, I-01. **Added:** HTM-AC-20 … AC-25, G-22, L-20 … L-30, P-12 … P-14, C-07, U-33 … U-63, R-04 … R-06. **Retired:** none — every old card still tests the same scenario, some with the outcome the new rules give it (e.g. U-07, the creator closing their own ticket, is now refused; U-16, closing a closed ticket, is now a passing refusal since BUG-1576 is closed). The verify report (`help_ticket_manager.verify.md`, cases revision 1) had no findings to address.

> **Revision (2026-11-26, gap fill).** The describer closed gaps 1–3 (spec `## Gap log` G1–G3): gap 1 → `can_access_ticket` R3a, unreachable, no card; gap 2 → new `to_response` R2a → **added HTM-R-07, R-08** (appended only; no existing card renumbered or changed); gap 3 → `role: str | None = None`, keyword-only, which the cards already assume (U-53 … U-60 and every passing `update_ticket` card stand as written).

> **Revision (2026-11-26, verifier round).** Verify finding (case-missing, `update_ticket` R5b): every close card started from empty stamps, so `ticket.closed_by or user_id` survived. **Added HTM-U-64** (appended only): an opened ticket carrying `closed_at PAST` / `closed_by MGR.id` is closed by a platform admin; the stamps become `ADM.id` / `CLOSE_AT`.

## Reviewer summary
- **Per callable:** `can_view_all_tickets` 14 · `can_access_ticket` 25 (3 bug) · `get_by_id_and_workspace` 22 (1 bug) · `list_tickets` 30 (5 bug) · `list_platform_tickets` 14 · `get_platform_ticket` 5 · `create_ticket` 7 · `update_ticket` 64 (20 bug) · `to_response` 8 · `_to_platform_item` 5.
- **Depth:** full for who may see, edit text and move status (`can_access_ticket`, `get_by_id_and_workspace`, `list_tickets` R1 / R2 / R2a, all of `update_ticket`). Lighter (step 1a) for the platform reads, `create_ticket` and the mappers: support messages, no stock, money or order state.
- **Status workflow (pass today, platform admin):** every allowed move (U-06, U-08, U-33) and every refused pair, one per card (U-15, U-16, U-35 … U-38), the stamps (U-34 keeps directly-set stamps on `pending → opened`), legacy stored status (U-40 … U-42), plain-string status (U-13, U-14), status as held in the session (U-43), bad values (U-11, U-12, U-44). Each refusal checks the session before any re-read, as BUG-1863's cards do.
- **Who may move status (R5, pass today):** creator, non-creator, a profile with `is_platform_admin` true but the flag not passed, same-status request, bad value, text + status (U-07, U-45 … U-50).
- **BUG-3251 (strict):** U-51 (new message, no `role` needed: fails on the message) and U-53 … U-60 written against the fix's new `role` keyword (spec Notes): today each call raises `TypeError`, the expected failure. Grants: role owner, role ground-team-manager, `owner_user_id`; refusals with the role keyword: ground-team creator, owner of W2, owner of W0.
- **BUG-1863 (strict):** U-18 … U-22, U-25 … U-28, U-52 (U-26 now on the platform path, `is_platform_admin=True`). U-23 / U-24 now pass under R4a (the status refusal fires first today, nothing written).
- **Other xfail (all strict):** BUG-2103 4 (AC-20, AC-21, AC-22, G-22), BUG-3250 3 (L-27, L-28, L-30), BUG-1578 2, BUG-1577 1. Kept passing beside them: AC-23 / L-29 (owner of *another* workspace gets nothing), L-16.
- **Notable design choices:** today-passing `update_ticket` cards never pass `role`; the spec fixes its default to `None` = no role (gap 3, closed). AC-18 ("no query") loads `T.workspace` before the When so it stays true after the BUG-2103 fix reads it. `closed_at` exact via the patched manager clock; only U-17 uses the real clock.
- **Needs a decision:** None. Gaps 1–3 closed by the describer (2026-11-26).

## Conventions for this module

**IDs.** `HTM` = `app/managers/help_ticket_manager.py`. `VA` can_view_all_tickets · `AC` can_access_ticket · `G` get_by_id_and_workspace · `L` list_tickets · `P` list_platform_tickets · `Q` get_platform_ticket · `C` create_ticket · `U` update_ticket · `R` to_response · `I` _to_platform_item.

**Actors and fixed values.**
- `HM` = `help_ticket_manager` (`from app.managers.help_ticket_manager import HelpTicketManager, help_ticket_manager, HelpTicketNotFoundError, HelpTicketForbiddenError, HelpTicketStatusChangeForbiddenError, HelpTicketInvalidTransitionError, TICKET_VIEW_ALL_ROLES, ALLOWED_STATUS_TRANSITIONS`). `db` = the test's real session (`autoflush=False`), first argument; every other argument by keyword, except `can_view_all_tickets(role)`, which is positional. `result` = what the When returns.
- `HelpTicket` (`app.models.help_ticket`). `HelpTicketCreate`, `HelpTicketUpdate`, `HelpTicketResponse`, `PlatformHelpTicketListItem` (`app.schemas.help_ticket`). `HelpTicketStatusEnum`, `HelpTicketTypeEnum`, `RoleEnum` (`app.models.enums`). `PydanticValidationError` = `pydantic.ValidationError`. `IntegrityError`, `DataError` (`sqlalchemy.exc`). `select`, `func`, `text` (`sqlalchemy`). `patch` (`unittest.mock`). `SimpleNamespace` (`types`). `datetime`, `timezone`, `timedelta` (`datetime`).
- OWNER_R = `RoleEnum("owner")`, GTM_R = `RoleEnum("ground-team-manager")`, GT_R = `RoleEnum("ground-team")`, FIN_R = `RoleEnum("finance")`. PENDING = `HelpTicketStatusEnum.PENDING`, OPENED = `HelpTicketStatusEnum.OPENED`, CLOSED = `HelpTicketStatusEnum.CLOSED`. SUPPORT = `HelpTicketTypeEnum.SUPPORT`, FEEDBACK = `HelpTicketTypeEnum.FEEDBACK`.
- MISSING = `999999999`. TAG = `uuid.uuid4().hex[:8]`, once per test. PAST = `datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)`. CLOSE_AT = `datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)`.
- FORBID = `"You do not have access to this help ticket."`. NOTFOUND = `"Help ticket not found."`. STATUS_FORBID = `"You may not change the status of this help ticket."` (intended; today's text is `"Only platform admins may change ticket status."`).

**Standing rows** (every test, in this order, no Given line): W0 = `make_workspace(db, name=f"Alpha {TAG}")`, W1 = `make_workspace(db, name=f"Gamma {TAG}")`, W2 = `make_workspace(db, name=f"Delta {TAG}")`, so W0.id < W1.id < W2.id; then each has `owner_user_id = None` set and flushed (no workspace has an owner unless a Given makes one). Then profiles by `make_profile(db, name=…)`: MGR `"Karim"`, CR `"Rahim"`, OWN `"Owen"`, ADM `"Sam"` with `is_platform_admin=True`, FIN `"Fatima"`. So MGR.id < CR.id < OWN.id < ADM.id < FIN.id. No membership rows: the role is an argument. No ticket exists unless the Given builds it.

**Given rows.** Inserted directly (never through `HM`), each `db.add` + `db.flush()` in the order written, so ticket ids rise in that order. A Given line written as code is a step to run exactly.
- **ticket** = `HelpTicket(workspace_id=W1.id, ticket_number=N, title="Printer jam", description="It jams", category="hardware", created_by=CR.id)`; `status` and `type` left to their defaults `"pending"` and `"support"`. The card gives `ticket_number`; after "but" every other column that differs (e.g. `type "feedback"`, `status "open"`).
- **opened ticket** = a ticket, but `status "opened"`.
- **closed ticket** = a ticket, but `status "closed"`, `closed_at PAST`, `closed_by MGR.id`.
- **owner of W by X** = `W.owner_user_id = X.id`, then `db.flush()`.
- **pending P** (last Given line where listed) = `P = HelpTicket(workspace_id=W2.id, ticket_number=f"HELP-P-{TAG}", title="Pending", description="Pending", created_by=FIN.id)`, `db.add(P)`, **no flush**.
- **snapshot** = taken after the last Given line, before the When: the values `unchanged` and `nothing written` compare to.

**Externals.**
- **clock** (every `C` card): around the When, patch `app.dao.help_ticket.datetime` (`create=True`) with a subclass of `datetime` whose `now()` returns `datetime(2026, 6, 1, 12, 0)`, and patch `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow` to return `datetime(2026, 6, 1, 12, 0)`.
- **close clock** (every `U` card unless it says "real clock"): around the When, patch `app.managers.help_ticket_manager.utcnow` to return CLOSE_AT.

**Named checks.**
- **re-read X** = `db.expire_all()`, then `db.get(HelpTicket, X.id)`; database values. Never before a `session:` or `pending:` line.
- **unchanged(T)** = after re-read, `title`, `description`, `category`, `status`, `type`, `closed_at`, `closed_by`, `created_by`, `updated_at` of T equal their snapshot values.
- **nothing written** = the numbers of `help_tickets` rows with `workspace_id` W0, W1 and W2 equal their snapshot values.
- **idset(r)** = `{t.id for t in r}`. **own(r)** = `{t.id for t in r if t.id in OWN}`, OWN = the ids of the tickets the Given made.
- `raises: <Type>` = plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint; further lines on `exc.value` after the block. `raises: <Type> in a savepoint` = `with pytest.raises(<Type>) as exc:` then `with db.begin_nested():` then the call.
- `session:` lines read `db` or the named objects directly, with no `expire_all` / `refresh` before them. `pending:` lines check P the same way.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (and around the `raises` block, when there is one).
- **rolled back** = inside spies, `sp = db.begin_nested()` directly before the call; the `in savepoint:` lines run before `sp.rollback()`, the `after rollback:` lines after it.
- **sql_log** = a list filled by a `before_cursor_execute` listener on `db.connection()`, started directly before the When, removed after it.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-n")`. Write the call and checks exactly as shown, including a `role=` keyword `update_ticket` does not take yet (BUG-3251 cards: the `TypeError` it raises today is the expected failure).

**Race simulations.** None.

## `HelpTicketManager.can_view_all_tickets`

### HTM-VA-01 — "owner" sees all
- **Rules:** `can_view_all_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("owner")`.

**Then**
1. returns: `result is True`.

### HTM-VA-02 — "ground-team-manager" sees all
- **Rules:** `can_view_all_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("ground-team-manager")`.

**Then**
1. returns: `result is True`.

### HTM-VA-03 — the RoleEnum owner member sees all
- **Rules:** `can_view_all_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets(OWNER_R)`.

**Then**
1. returns: `result is True`.

### HTM-VA-04 — the RoleEnum ground-team-manager member sees all
- **Rules:** `can_view_all_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets(GTM_R)`.

**Then**
1. returns: `result is True`.

### HTM-VA-05 — "finance" does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("finance")`.

**Then**
1. returns: `result is False`.

### HTM-VA-06 — "ground-team" does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets(GT_R)`.

**Then**
1. returns: `result is False`.

### HTM-VA-07 — None does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets(None)`.

**Then**
1. returns: `result is False`.

### HTM-VA-08 — the empty string does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("")`.

**Then**
1. returns: `result is False`.

### HTM-VA-09 — "Owner" with a capital does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("Owner")`.

**Then**
1. returns: `result is False`.

### HTM-VA-10 — " owner" with a leading space does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets(" owner")`.

**Then**
1. returns: `result is False`.

### HTM-VA-11 — "manager", a part of the role, does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("manager")`.

**Then**
1. returns: `result is False`.

### HTM-VA-12 — "ground_team_manager" with underscores does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("ground_team_manager")`.

**Then**
1. returns: `result is False`.

### HTM-VA-13 — "own", the start of a role, does not
- **Rules:** `can_view_all_tickets` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = HelpTicketManager.can_view_all_tickets("own")`.

**Then**
1. returns: `result is False`.

### HTM-VA-14 — the view-all set holds exactly the two roles
- **Rules:** `can_view_all_tickets` R1 (Facts: `TICKET_VIEW_ALL_ROLES`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = set(TICKET_VIEW_ALL_ROLES)`.

**Then**
1. returns: `result == {"owner", "ground-team-manager"}`.

## `HelpTicketManager.can_access_ticket`

### HTM-AC-01 — a platform admin without a role may open a member's ticket
- **Rules:** `can_access_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=ADM, role=None)`.

**Then**
1. returns: `result is True`.

### HTM-AC-02 — a platform admin with a plain role may open a ticket whose creator is gone
- **Rules:** `can_access_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=ADM, role=GT_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-03 — an owner (higher id than the creator) may open a member's ticket
- **Rules:** `can_access_ticket` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-04 — a ground-team-manager (lower id than the creator) may open a member's ticket
- **Rules:** `can_access_ticket` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=MGR, role=GTM_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-05 — the role as a plain string "owner" counts
- **Rules:** `can_access_ticket` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role="owner")`.

**Then**
1. returns: `result is True`.

### HTM-AC-06 — an owner may open a ticket whose creator is gone
- **Rules:** `can_access_ticket` R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-07 — the creator with no role may open their ticket
- **Rules:** `can_access_ticket` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=CR, role=None)`.

**Then**
1. returns: `result is True`.

### HTM-AC-08 — the creator as a ground-team member may open their ticket
- **Rules:** `can_access_ticket` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=CR, role=GT_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-09 — a ground-team member with a lower id than the creator may not
- **Rules:** `can_access_ticket` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=MGR, role=GT_R)`.

**Then**
1. returns: `result is False`.

### HTM-AC-10 — a finance member with a higher id than the creator may not
- **Rules:** `can_access_ticket` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role=FIN_R)`.

**Then**
1. returns: `result is False`.

### HTM-AC-11 — no role and not an admin may not
- **Rules:** `can_access_ticket` R1, R2, R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=OWN, role=None)`.

**Then**
1. returns: `result is False`.

### HTM-AC-12 — a ticket whose creator is gone is closed to a plain member
- **Rules:** `can_access_ticket` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role=FIN_R)`.

**Then**
1. returns: `result is False`.

### HTM-AC-13 — a user object without is_platform_admin counts as not an admin
- **Rules:** `can_access_ticket` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=SimpleNamespace(id=FIN.id), role=None)`.

**Then**
1. returns: `result is False`.

### HTM-AC-14 — a user object without is_platform_admin is still let in as the creator
- **Rules:** `can_access_ticket` R1, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=SimpleNamespace(id=CR.id), role=None)`.

**Then**
1. returns: `result is True`.

### HTM-AC-15 — is_platform_admin False with a view-all role still counts by role
- **Rules:** `can_access_ticket` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=SimpleNamespace(id=FIN.id, is_platform_admin=False), role=GTM_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-16 — "Owner" with a capital is not a view-all role
- **Rules:** `can_access_ticket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role="Owner")`.

**Then**
1. returns: `result is False`.

### HTM-AC-17 — the creator of a different ticket may not open this one
- **Rules:** `can_access_ticket` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `created_by FIN.id`.
2. T = ticket `"HELP-2026-002"`.
3. TB = ticket `"HELP-2026-003"`, but `created_by FIN.id`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role=GT_R)`.

**Then**
1. returns: `result is False`.

### HTM-AC-18 — the check runs no query (revised 2026-11-26)
- **Rules:** `can_access_ticket` Persistence (pure)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. `T.workspace` read once, so it is loaded before the When; sql_log runs around the When.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=CR, role=GT_R)`.

**Then**
1. returns: `result is True`.
2. statement: `sql_log == []`.

### HTM-AC-19 — the ticket's workspace is not looked at
- **Rules:** `can_access_ticket` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=TZ, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-20 — the workspace owner with a plain role may open a member's ticket
- **Rules:** `can_access_ticket` R5 [BUG-2103]
- **Kind:** bug
- **Expect:** xfail BUG-2103
- **Fails today on:** Then 1 (`owner_user_id` is never read: `False`)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. owner of W1 by FIN.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role=FIN_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-21 — the workspace owner without a role may open a member's ticket
- **Rules:** `can_access_ticket` R5 [BUG-2103]
- **Kind:** bug
- **Expect:** xfail BUG-2103
- **Fails today on:** Then 1 (`owner_user_id` is never read: `False`)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. owner of W1 by OWN.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=OWN, role=None)`.

**Then**
1. returns: `result is True`.

### HTM-AC-22 — the workspace owner may open a ticket whose creator is gone
- **Rules:** `can_access_ticket` R3, R5 [BUG-2103]
- **Kind:** bug
- **Expect:** xfail BUG-2103
- **Fails today on:** Then 1 (`owner_user_id` is never read: `False`)

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.
2. owner of W1 by FIN.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role=GT_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-23 — the owner of the earlier and the later workspace may not open W1's ticket
- **Rules:** `can_access_ticket` R5 (grant held on a different workspace), R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. owner of W0 by FIN.
2. owner of W2 by FIN.
3. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role=FIN_R)`.

**Then**
1. returns: `result is False`.

### HTM-AC-24 — status and type play no part: the creator opens a closed feedback ticket
- **Rules:** `can_access_ticket` R6, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`, but `type "feedback"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=CR, role=GT_R)`.

**Then**
1. returns: `result is True`.

### HTM-AC-25 — status and type play no part: an opened feedback ticket stays closed to a non-creator
- **Rules:** `can_access_ticket` R6, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`, but `type "feedback"`.

**When**
- `result = HelpTicketManager.can_access_ticket(ticket=T, user=FIN, role=FIN_R)`.

**Then**
1. returns: `result is False`.

## `HelpTicketManager.get_by_id_and_workspace`

### HTM-G-01 — the creator gets their ticket, not a neighbour, with its creator
- **Rules:** `get_by_id_and_workspace` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `title "Other"`.
2. T = ticket `"HELP-2026-002"`.
3. TB = ticket `"HELP-2026-003"`, but `title "Third"`.

**When**
- `result = HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=CR, role=GT_R)`.

**Then**
1. returns: `result is T`.
2. returns: `result.title == "Printer jam"`, `result.ticket_number == "HELP-2026-002"`.
3. returns: `result.creator.name == "Rahim"`.

### HTM-G-02 — an owner (higher id than the creator) gets a member's ticket
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result is T`.

### HTM-G-03 — a ground-team-manager (lower id than the creator) gets a member's ticket
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=MGR, role=GTM_R)`.

**Then**
1. returns: `result is T`.

### HTM-G-04 — a platform admin without a role gets a member's ticket
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=ADM, role=None)`.

**Then**
1. returns: `result is T`.

### HTM-G-05 — an owner gets a ticket whose creator is gone, creator None
- **Rules:** `get_by_id_and_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `result is T`.
2. returns: `result.creator is None`.

### HTM-G-06 — a ground-team member with a lower id than the creator is refused
- **Rules:** `get_by_id_and_workspace` R2, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=MGR, role=GT_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `type(exc.value) is HelpTicketForbiddenError`.
3. raises: `str(exc.value) == FORBID`.
4. raises: `isinstance(exc.value, PermissionError)`.

### HTM-G-07 — a finance member with a higher id than the creator is refused
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTM-G-08 — no role and not an admin is refused
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=OWN, role=None)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTM-G-09 — a ticket whose creator is gone is refused to a plain member
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTM-G-10 — a user without is_platform_admin and not the creator is refused
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=SimpleNamespace(id=OWN.id), role=GT_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTM-G-11 — an unknown id is not found
- **Rules:** `get_by_id_and_workspace` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=MISSING, workspace_id=W1.id, user=OWN, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `type(exc.value) is HelpTicketNotFoundError`.
3. raises: `str(exc.value) == NOTFOUND`.
4. raises: `isinstance(exc.value, LookupError)`.

### HTM-G-12 — id 0 is not found
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=0, workspace_id=W1.id, user=OWN, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTM-G-13 — the later workspace's ticket asked in W1 is not found, even by its creator
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=TZ.id, workspace_id=W1.id, user=CR, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTM-G-14 — the earlier workspace's ticket asked in W1 is not found, even by its creator
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=TZ.id, workspace_id=W1.id, user=CR, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTM-G-15 — W1's ticket asked in the later workspace is not found
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W2.id, user=OWN, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTM-G-16 — W1's ticket asked in the earlier workspace is not found
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W0.id, user=OWN, role=OWNER_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTM-G-17 — another workspace's ticket gives "not found" before any access check
- **Rules:** `get_by_id_and_workspace` R1 (order of checks)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=TZ.id, workspace_id=W1.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `type(exc.value) is HelpTicketNotFoundError`.
3. raises: `str(exc.value) == NOTFOUND`.

### HTM-G-18 — an admin asking for another workspace's ticket is not found
- **Rules:** `get_by_id_and_workspace` R1 (HR-16: the workspace methods are scoped)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. TZ = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=TZ.id, workspace_id=W1.id, user=ADM, role=None)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTM-G-19 — the creator of other tickets, here and elsewhere, is refused this one
- **Rules:** `get_by_id_and_workspace` R2 (creator grant held on a different record)
- **Kind:** error
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-002"`, but `workspace_id W0.id`, `created_by FIN.id`.
2. TA = ticket `"HELP-2026-001"`, but `created_by FIN.id`.
3. T = ticket `"HELP-2026-002"`.
4. TB = ticket `"HELP-2026-003"`, but `created_by FIN.id`.
5. TZ = ticket `"HELP-2026-002"`, but `workspace_id W2.id`, `created_by FIN.id`.

**When**
- `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=FIN, role=GT_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.

### HTM-G-20 — a successful get writes nothing and keeps the caller's pending row
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- spies: `result = HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=CR, role=GT_R)`.

**Then**
1. returns: `result is T`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `db.is_modified(T) is False`.
5. session: `not db.dirty`, `not db.deleted`.
6. pending: `len(db.new) == 1`, `P in db.new`.

### HTM-G-21 — a refused get neither rolls back nor drops the caller's pending row
- **Rules:** `get_by_id_and_workspace` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- spies: `HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=FIN, role=FIN_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.dirty`, `not db.deleted`.
5. pending: `len(db.new) == 1`, `P in db.new`.

### HTM-G-22 — the workspace owner with a plain role gets a member's ticket
- **Rules:** `get_by_id_and_workspace` R2, R3 (through `can_access_ticket` R5 [BUG-2103])
- **Kind:** bug
- **Expect:** xfail BUG-2103
- **Fails today on:** Then 1 (the call raises HelpTicketForbiddenError: `owner_user_id` is never read)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. owner of W1 by FIN.

**When**
- `result = HM.get_by_id_and_workspace(db, ticket_id=T.id, workspace_id=W1.id, user=FIN, role=GT_R)`.

**Then**
1. returns: `result is T`.

## `HelpTicketManager.list_tickets`

### HTM-L-01 — an owner sees every ticket of W1, none of W0 or W2
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
2. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
3. TC = ticket `"HELP-2026-002"`.
4. TO = ticket `"HELP-2026-003"`, but `created_by OWN.id`.
5. TN = ticket `"HELP-2026-004"`, but `created_by None`.
6. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `all(isinstance(t, HelpTicket) for t in result)`.
3. returns: `idset(result) == {TM.id, TC.id, TO.id, TN.id}`.

### HTM-L-02 — a ground-team-manager sees every ticket of W1
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TF = ticket `"HELP-2026-003"`, but `created_by FIN.id`.
4. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `created_by MGR.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=MGR, role=GTM_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id, TC.id, TF.id}`.

### HTM-L-03 — a ground-team member sees only their own, not lower or higher creators'
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TF = ticket `"HELP-2026-003"`, but `created_by FIN.id`.
4. TN = ticket `"HELP-2026-004"`, but `created_by None`.
5. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
6. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=CR, role=GT_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TC.id}`.

### HTM-L-04 — a finance member sees only their own
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TC = ticket `"HELP-2026-001"`.
2. TF = ticket `"HELP-2026-002"`, but `created_by FIN.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=FIN, role=FIN_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TF.id}`.

### HTM-L-05 — no role and not an admin sees only their own
- **Rules:** `list_tickets` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TC = ticket `"HELP-2026-001"`.
2. TO = ticket `"HELP-2026-002"`, but `created_by OWN.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TO.id}`.

### HTM-L-06 — the own-tickets filter is applied before paging
- **Rules:** `list_tickets` R1 (HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TF = ticket `"HELP-2026-002"`, but `created_by FIN.id`.
3. TC = ticket `"HELP-2026-003"`.
4. TO = ticket `"HELP-2026-004"`, but `created_by OWN.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=CR, role=GT_R, limit=1)`.

**Then**
1. returns: `idset(result) == {TC.id}`.

### HTM-L-07 — status closed keeps only closed tickets (revised 2026-11-26)
- **Rules:** `list_tickets` R1 (status)
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TO = opened ticket `"HELP-2026-002"`.
3. TB = closed ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=CLOSED, limit=1000)`.

**Then**
1. returns: `idset(result) == {TB.id}`.

### HTM-L-08 — status opened keeps only opened tickets (revised 2026-11-26)
- **Rules:** `list_tickets` R1 (status)
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TO = opened ticket `"HELP-2026-002"`.
3. TB = closed ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=OPENED, limit=1000)`.

**Then**
1. returns: `idset(result) == {TO.id}`.

### HTM-L-09 — status None keeps all three statuses (revised 2026-11-26)
- **Rules:** `list_tickets` R1 (status)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TO = opened ticket `"HELP-2026-002"`.
3. TB = closed ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id, TO.id, TB.id}`.

### HTM-L-10 — the default limit is 100
- **Rules:** `list_tickets` R1 (paging default)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets, the k-th (k = 1 … 101) = ticket `f"HELP-2026-{k:03d}"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R)`.

**Then**
1. returns: `len(result) == 100`.

### HTM-L-11 — skip reaches the query
- **Rules:** `list_tickets` R1 (paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TB = ticket `"HELP-2026-002"`.
3. TC = ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `idset(result) < {TA.id, TB.id, TC.id}`.

### HTM-L-12 — limit reaches the query
- **Rules:** `list_tickets` R1 (paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`.
2. TB = ticket `"HELP-2026-002"`.
3. TC = ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=2)`.

**Then**
1. returns: `len(result) == 2`.

### HTM-L-13 — each ticket comes with its creator
- **Rules:** `list_tickets` Returns (creator loaded)
- **Kind:** happy
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TN = ticket `"HELP-2026-003"`, but `created_by None`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `{t.id: (t.creator.name if t.creator else None) for t in result} == {TM.id: "Karim", TC.id: "Rahim", TN.id: None}`.

### HTM-L-14 — a platform admin without a role sees every ticket of the workspace
- **Rules:** `list_tickets` R2 [BUG-1578]
- **Kind:** bug
- **Expect:** xfail BUG-1578
- **Fails today on:** Then 1 (only the admin's own tickets: `[]`)

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=ADM, role=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id, TC.id}`.

### HTM-L-15 — a platform admin with a plain role sees every ticket of the workspace
- **Rules:** `list_tickets` R2 [BUG-1578]
- **Kind:** bug
- **Expect:** xfail BUG-1578
- **Fails today on:** Then 1 (only the admin's own ticket TA)

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TA = ticket `"HELP-2026-002"`, but `created_by ADM.id`.
3. TF = ticket `"HELP-2026-003"`, but `created_by FIN.id`.
4. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=ADM, role=GT_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id, TA.id, TF.id}`.

### HTM-L-16 — a platform admin's own tickets of the workspace are listed, another workspace's are not
- **Rules:** `list_tickets` R1, R2 (holds before and after BUG-1578)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`, `created_by ADM.id`.
2. TA = ticket `"HELP-2026-001"`, but `created_by ADM.id`.
3. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `created_by ADM.id`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=ADM, role=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### HTM-L-17 — a negative skip raises DataError
- **Rules:** `list_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. TC = ticket `"HELP-2026-001"`.

**When**
- `HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, skip=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### HTM-L-18 — a negative limit raises DataError
- **Rules:** `list_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. TC = ticket `"HELP-2026-001"`.

**When**
- `HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### HTM-L-19 — a list writes nothing and keeps the caller's pending row
- **Rules:** `list_tickets` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. TC = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- spies: `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TC.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.dirty`, `not db.deleted`.
5. pending: `len(db.new) == 1`, `P in db.new`.

### HTM-L-20 — status pending keeps only pending tickets
- **Rules:** `list_tickets` R1 (status)
- **Kind:** happy
- **Expect:** pass

**Given**
1. TO = opened ticket `"HELP-2026-001"`.
2. TA = ticket `"HELP-2026-002"`.
3. TB = closed ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=PENDING, limit=1000)`.

**Then**
1. returns: `idset(result) == {TA.id}`.

### HTM-L-21 — type feedback keeps only W1's feedback tickets
- **Rules:** `list_tickets` R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. TS = ticket `"HELP-2026-001"`.
2. TF = ticket `"HELP-2026-002"`, but `type "feedback"`.
3. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `type "feedback"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, ticket_type=FEEDBACK, limit=1000)`.

**Then**
1. returns: `idset(result) == {TF.id}`.

### HTM-L-22 — type support keeps only support tickets
- **Rules:** `list_tickets` R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. TF = ticket `"HELP-2026-001"`, but `type "feedback"`.
2. TS = ticket `"HELP-2026-002"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, ticket_type=SUPPORT, limit=1000)`.

**Then**
1. returns: `idset(result) == {TS.id}`.

### HTM-L-23 — type None keeps both types
- **Rules:** `list_tickets` R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TF = ticket `"HELP-2026-001"`, but `type "feedback"`.
2. TS = ticket `"HELP-2026-002"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, ticket_type=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TF.id, TS.id}`.

### HTM-L-24 — type and status must both hold
- **Rules:** `list_tickets` R1, R1a (combined)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = opened ticket `"HELP-2026-001"`, but `type "feedback"`.
2. T2 = ticket `"HELP-2026-002"`, but `type "feedback"`.
3. T3 = opened ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, status=OPENED, ticket_type=FEEDBACK, limit=1000)`.

**Then**
1. returns: `idset(result) == {T1.id}`.

### HTM-L-25 — type and the own-tickets filter must both hold
- **Rules:** `list_tickets` R1, R1a (combined)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`, `type "feedback"`.
2. TC = ticket `"HELP-2026-002"`, but `type "feedback"`.
3. TS = ticket `"HELP-2026-003"`.
4. TF = ticket `"HELP-2026-004"`, but `created_by FIN.id`, `type "feedback"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=CR, role=GT_R, ticket_type=FEEDBACK, limit=1000)`.

**Then**
1. returns: `idset(result) == {TC.id}`.

### HTM-L-26 — the type filter is applied before paging
- **Rules:** `list_tickets` R1a (in SQL before paging, HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TS1 = ticket `"HELP-2026-001"`.
2. TS2 = ticket `"HELP-2026-002"`.
3. TS3 = ticket `"HELP-2026-003"`.
4. TF = ticket `"HELP-2026-004"`, but `type "feedback"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=OWNER_R, ticket_type=FEEDBACK, limit=1)`.

**Then**
1. returns: `idset(result) == {TF.id}`.

### HTM-L-27 — the workspace owner with a plain role sees every ticket of the workspace
- **Rules:** `list_tickets` R2a [BUG-3250]
- **Kind:** bug
- **Expect:** xfail BUG-3250
- **Fails today on:** Then 1 (only the owner's own ticket TF)

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. TF = ticket `"HELP-2026-003"`, but `created_by FIN.id`.
4. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `created_by MGR.id`.
5. owner of W1 by FIN.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=FIN, role=FIN_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id, TC.id, TF.id}`.

### HTM-L-28 — the workspace owner without a role sees every ticket of the workspace
- **Rules:** `list_tickets` R2a [BUG-3250]
- **Kind:** bug
- **Expect:** xfail BUG-3250
- **Fails today on:** Then 1 (the owner created none: `[]`)

**Given**
1. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
2. TC = ticket `"HELP-2026-002"`.
3. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
4. owner of W1 by OWN.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=OWN, role=None, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id, TC.id}`.

### HTM-L-29 — the owner of the earlier and the later workspace sees only their own tickets of W1
- **Rules:** `list_tickets` R1, R2a (grant held on a different workspace; holds before and after BUG-3250)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. owner of W0 by FIN.
2. owner of W2 by FIN.
3. TM = ticket `"HELP-2026-001"`, but `created_by MGR.id`.
4. TF = ticket `"HELP-2026-002"`, but `created_by FIN.id`.
5. TC = ticket `"HELP-2026-003"`.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=FIN, role=FIN_R, limit=1000)`.

**Then**
1. returns: `idset(result) == {TF.id}`.

### HTM-L-30 — the workspace owner's full list still obeys status and type
- **Rules:** `list_tickets` R2a [BUG-3250], R1, R1a
- **Kind:** bug
- **Expect:** xfail BUG-3250
- **Fails today on:** Then 1 (the owner created no opened feedback ticket: `[]`)

**Given**
1. TM = opened ticket `"HELP-2026-001"`, but `created_by MGR.id`, `type "feedback"`.
2. TF = ticket `"HELP-2026-002"`, but `created_by FIN.id`, `type "feedback"`.
3. TC = opened ticket `"HELP-2026-003"`.
4. owner of W1 by FIN.

**When**
- `result = HM.list_tickets(db, workspace_id=W1.id, user=FIN, role=FIN_R, status=OPENED, ticket_type=FEEDBACK, limit=1000)`.

**Then**
1. returns: `idset(result) == {TM.id}`.

## `HelpTicketManager.list_platform_tickets`

### HTM-P-01 — tickets of every workspace, each as an item with its workspace's and creator's name
- **Rules:** `list_platform_tickets` R1, R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`, `created_by FIN.id`.
2. T1 = ticket `"HELP-2026-001"`.
3. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `created_by MGR.id`.

**When**
- `result = HM.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `all(isinstance(t, PlatformHelpTicketListItem) for t in result)`.
3. returns: `own(result) == {T0.id, T1.id, T2.id}` (OWN = {T0.id, T1.id, T2.id}).
4. returns: `{t.id: (t.workspace_name, t.creator_name) for t in result if t.id in OWN} == {T0.id: (f"Alpha {TAG}", "Fatima"), T1.id: (f"Gamma {TAG}", "Rahim"), T2.id: (f"Delta {TAG}", "Karim")}`.

### HTM-P-02 — an item carries the ticket's own fields, type included (revised 2026-11-26)
- **Rules:** `list_platform_tickets` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = closed ticket `"HELP-2026-004"`, but `workspace_id W2.id`, `type "feedback"`.

**When**
- `result = HM.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `[t.id for t in result if t.id == T1.id] == [T1.id]`.
2. returns: the entry E with `E.id == T1.id` has `E.ticket_number == "HELP-2026-004"`, `E.workspace_id == W2.id`, `E.title == "Printer jam"`, `E.description == "It jams"`, `E.category == "hardware"`.
3. returns: E has `E.status == CLOSED`, `E.closed_at == PAST`, `E.closed_by == MGR.id`, `E.created_by == CR.id`.
4. returns: E has `E.type == FEEDBACK`.

### HTM-P-03 — a ticket without a creator has creator_name None
- **Rules:** `list_platform_tickets` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HM.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `{t.id: t.creator_name for t in result if t.id == T1.id} == {T1.id: None}`.

### HTM-P-04 — status closed keeps only closed tickets (revised 2026-11-26)
- **Rules:** `list_platform_tickets` R1 (status)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T0 = opened ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
2. T1 = ticket `"HELP-2026-001"`.
3. T2 = closed ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = HM.list_platform_tickets(db, status=CLOSED, search=TAG, limit=1000)`.

**Then**
1. returns: `own(result) == {T2.id}` (OWN = {T0.id, T1.id, T2.id}).

### HTM-P-05 — the search reaches the query
- **Rules:** `list_platform_tickets` R1 (search)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
2. T1 = ticket `"HELP-2026-001"`.
3. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = HM.list_platform_tickets(db, search=f"Delta {TAG}", limit=1000)`.

**Then**
1. returns: `own(result) == {T2.id}` (OWN = {T0.id, T1.id, T2.id}).

### HTM-P-06 — no matching row gives an empty list
- **Rules:** `list_platform_tickets` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.

**When**
- `result = HM.list_platform_tickets(db, search=f"nomatch-{TAG}", limit=1000)`.

**Then**
1. returns: `result == []`.

### HTM-P-07 — the default limit is 100
- **Rules:** `list_platform_tickets` R1 (paging default)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets, the k-th (k = 1 … 101) = ticket `f"HELP-2026-{k:03d}"`, but `title f"T{k} {TAG}"`.

**When**
- `result = HM.list_platform_tickets(db, search=TAG)`.

**Then**
1. returns: `len(result) == 100`.

### HTM-P-08 — skip reaches the query
- **Rules:** `list_platform_tickets` R1 (paging)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
2. T1 = ticket `"HELP-2026-001"`.
3. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = HM.list_platform_tickets(db, search=TAG, skip=1, limit=1000)`.

**Then**
1. returns: `len(result) == 2`.

### HTM-P-09 — a negative limit raises DataError
- **Rules:** `list_platform_tickets` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.

**When**
- `HM.list_platform_tickets(db, limit=-1)`.

**Then**
1. raises: `DataError` in a savepoint.

### HTM-P-10 — items keep the database's order
- **Rules:** `list_platform_tickets` R2 (in the DAO's order)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.
2. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
3. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
4. `db.execute(text("UPDATE help_tickets SET created_at = now() + interval '3 hours' WHERE id = :i"), {"i": T1.id})`.
5. `db.execute(text("UPDATE help_tickets SET created_at = now() + interval '2 hours' WHERE id = :i"), {"i": T0.id})`.
6. `db.execute(text("UPDATE help_tickets SET created_at = now() + interval '1 hour' WHERE id = :i"), {"i": T2.id})`, then `db.expire_all()`.

**When**
- `result = HM.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `[t.id for t in result] == [T1.id, T0.id, T2.id]`.

### HTM-P-11 — the platform list writes nothing and keeps the caller's pending row
- **Rules:** `list_platform_tickets` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- spies: `result = HM.list_platform_tickets(db, search=TAG, limit=1000)`.

**Then**
1. returns: `idset(result) == {T1.id}`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `not db.dirty`, `not db.deleted`.
5. pending: `len(db.new) == 1`, `P in db.new`.

### HTM-P-12 — type feedback keeps feedback tickets of every workspace
- **Rules:** `list_platform_tickets` R1a
- **Kind:** happy
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`, `type "feedback"`.
2. T1 = ticket `"HELP-2026-001"`.
3. T2 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `type "feedback"`.

**When**
- `result = HM.list_platform_tickets(db, ticket_type=FEEDBACK, search=TAG, limit=1000)`.

**Then**
1. returns: `own(result) == {T0.id, T2.id}` (OWN = {T0.id, T1.id, T2.id}).

### HTM-P-13 — type, status and search must all hold
- **Rules:** `list_platform_tickets` R1, R1a (combined)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T0 = opened ticket `"HELP-2026-001"`, but `workspace_id W0.id`, `type "feedback"`.
2. T1 = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `type "feedback"`.
3. T2 = opened ticket `"HELP-2026-002"`, but `workspace_id W2.id`.
4. T3 = opened ticket `"HELP-2026-003"`, but `workspace_id W2.id`, `type "feedback"`.

**When**
- `result = HM.list_platform_tickets(db, status=OPENED, ticket_type=FEEDBACK, search=f"Delta {TAG}", limit=1000)`.

**Then**
1. returns: `own(result) == {T3.id}` (OWN = {T0.id, T1.id, T2.id, T3.id}).

### HTM-P-14 — the type filter is applied before paging
- **Rules:** `list_platform_tickets` R1a (in SQL before paging, HR-5)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = ticket `"HELP-2026-001"`.
2. T2 = ticket `"HELP-2026-002"`.
3. T3 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
4. TF = ticket `"HELP-2026-001"`, but `workspace_id W2.id`, `type "feedback"`.

**When**
- `result = HM.list_platform_tickets(db, ticket_type=FEEDBACK, search=TAG, limit=1)`.

**Then**
1. returns: `[t.id for t in result] == [TF.id]`.

## `HelpTicketManager.get_platform_ticket`

### HTM-Q-01 — a ticket of another workspace is returned as an item, not a neighbour
- **Rules:** `get_platform_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `title "Other"`.
2. T = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
3. TB = ticket `"HELP-2026-001"`, but `workspace_id W0.id`, `title "Third"`.

**When**
- `result = HM.get_platform_ticket(db, ticket_id=T.id)`.

**Then**
1. returns: `isinstance(result, PlatformHelpTicketListItem)`.
2. returns: `result.id == T.id`, `result.workspace_id == W2.id`, `result.title == "Printer jam"`.
3. returns: `result.workspace_name == f"Delta {TAG}"`, `result.creator_name == "Rahim"`.

### HTM-Q-02 — a ticket of the earliest workspace is returned
- **Rules:** `get_platform_ticket` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `workspace_id W0.id`, `created_by None`.
2. TB = ticket `"HELP-2026-001"`, but `title "Third"`.

**When**
- `result = HM.get_platform_ticket(db, ticket_id=T.id)`.

**Then**
1. returns: `result.id == T.id`, `result.workspace_name == f"Alpha {TAG}"`.
2. returns: `result.creator_name is None`.

### HTM-Q-03 — an unknown id is not found
- **Rules:** `get_platform_ticket` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_platform_ticket(db, ticket_id=MISSING)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `type(exc.value) is HelpTicketNotFoundError`.
3. raises: `str(exc.value) == NOTFOUND`.

### HTM-Q-04 — id 0 is not found
- **Rules:** `get_platform_ticket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.get_platform_ticket(db, ticket_id=0)`.

**Then**
1. raises: `HelpTicketNotFoundError`.
2. raises: `str(exc.value) == NOTFOUND`.

### HTM-Q-05 — the platform get writes nothing and keeps the caller's pending row
- **Rules:** `get_platform_ticket` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- spies: `result = HM.get_platform_ticket(db, ticket_id=T.id)`.

**Then**
1. returns: `result.id == T.id`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. pending: `len(db.new) == 1`, `P in db.new`.

## `HelpTicketManager.create_ticket`

### HTM-C-01 — one pending support ticket is created, numbered and flushed (revised 2026-11-26)
- **Rules:** `create_ticket` R1, R1a, R1b (type not sent)
- **Kind:** happy
- **Expect:** pass

**Given**
1. No ticket in W1.

**When**
- `result = HM.create_ticket(db, workspace_id=W1.id, user_id=CR.id, payload=HelpTicketCreate(title="Printer jam", description="It jams", category="hardware"))`.

**Then**
1. returns: `isinstance(result, HelpTicket)`, `result.id is not None`.
2. re-read the row `result.id`: `ticket_number == "HELP-2026-001"`, `workspace_id == W1.id`, `created_by == CR.id`.
3. re-read the row `result.id`: `status == "pending"`, `type == "support"`.
4. re-read the row `result.id`: `title == "Printer jam"`, `description == "It jams"`, `category == "hardware"`.
5. re-read the row `result.id`: `closed_at is None`, `closed_by is None`.
6. count: W1 has exactly 1 `help_tickets` row.

### HTM-C-02 — the payload is stored as given, untrimmed; a dump without type gives support (revised 2026-11-26)
- **Rules:** `create_ticket` R1 (no check or trimming of its own), R1a, R1b (no `type` key)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No ticket in W1.

**When**
- `result = HM.create_ticket(db, workspace_id=W1.id, user_id=FIN.id, payload=HelpTicketCreate.model_construct(title="  Printer  JAM ", description=" It  jams ", category=None))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `title == "  Printer  JAM "`, `description == " It  jams "`, `category is None`, `created_by == FIN.id`.
3. re-read the row `result.id`: `type == "support"`, `status == "pending"`.

### HTM-C-03 — the number counts only W1's tickets
- **Rules:** `create_ticket` R1 (DAO `create_with_user` R1)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T0 = ticket `"HELP-2026-001"`, but `workspace_id W0.id`.
2. T0b = ticket `"HELP-2026-002"`, but `workspace_id W0.id`.
3. TA = ticket `"HELP-2026-001"`.
4. TZ = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
5. TZb = ticket `"HELP-2026-002"`, but `workspace_id W2.id`.

**When**
- `result = HM.create_ticket(db, workspace_id=W1.id, user_id=CR.id, payload=HelpTicketCreate(title="Toner low", description="Grey prints"))`.

**Then**
1. returns: `result.ticket_number == "HELP-2026-002"`.
2. re-read the row `result.id`: `ticket_number == "HELP-2026-002"`, `workspace_id == W1.id`.

### HTM-C-04 — an unknown user raises IntegrityError and nothing is saved
- **Rules:** `create_ticket` Errors (DAO R5)
- **Kind:** error
- **Expect:** pass

**Given**
1. No ticket in W1.

**When**
- `HM.create_ticket(db, workspace_id=W1.id, user_id=MISSING, payload=HelpTicketCreate(title="Printer jam", description="It jams"))`.

**Then**
1. raises: `IntegrityError` in a savepoint.
2. nothing written.

### HTM-C-05 — a number already taken raises IntegrityError and nothing is saved
- **Rules:** `create_ticket` Errors (DAO R4)
- **Kind:** error
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-002"`.

**When**
- `HM.create_ticket(db, workspace_id=W1.id, user_id=CR.id, payload=HelpTicketCreate(title="Toner low", description="Grey prints"))`.

**Then**
1. raises: `IntegrityError` in a savepoint.
2. nothing written.
3. unchanged: unchanged(TA).

### HTM-C-06 — create flushes but never commits or rolls back
- **Rules:** `create_ticket` R1 (flushed, not committed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No ticket in W1.

**When**
- rolled back: `result = HM.create_ticket(db, workspace_id=W1.id, user_id=CR.id, payload=HelpTicketCreate(title="Printer jam", description="It jams"))`.

**Then**
1. in savepoint: `result.id is not None`.
2. in savepoint: `db.scalar(select(func.count()).select_from(HelpTicket).where(HelpTicket.workspace_id == W1.id)) == 1`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. after rollback: `db.scalar(select(func.count()).select_from(HelpTicket).where(HelpTicket.workspace_id == W1.id)) == 0`.

### HTM-C-07 — type feedback is stored; the ticket is still pending
- **Rules:** `create_ticket` R1a, R1b
- **Kind:** happy
- **Expect:** pass

**Given**
1. No ticket in W1.

**When**
- `result = HM.create_ticket(db, workspace_id=W1.id, user_id=CR.id, payload=HelpTicketCreate(title="Nice app", description="Love the reports", type=FEEDBACK))`.

**Then**
1. returns: `result.id is not None`.
2. re-read the row `result.id`: `type == "feedback"`, `status == "pending"`, `title == "Nice app"`.

## `HelpTicketManager.update_ticket`

### HTM-U-01 — the creator changes title, description and category; neighbours untouched (revised 2026-11-26)
- **Rules:** `update_ticket` R2, R3, R11; Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. TA = ticket `"HELP-2026-001"`, but `title "Other"`.
2. T = ticket `"HELP-2026-002"`.
3. TB = ticket `"HELP-2026-003"`, but `title "Third"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Toner low", description="Grey prints", category="supplies"), user_id=CR.id)`.

**Then**
1. returns: `result is T`.
2. re-read T: `title == "Toner low"`, `description == "Grey prints"`, `category == "supplies"`.
3. re-read T: `status == "pending"`, `type == "support"`, `closed_at is None`, `closed_by is None`, `created_by == CR.id`.
4. re-read TA: `title == "Other"`.
5. re-read TB: `title == "Third"`.

### HTM-U-02 — a creator with the lowest id edits their own ticket's text
- **Rules:** `update_ticket` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by MGR.id`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Toner low"), user_id=MGR.id)`.

**Then**
1. returns: `result is T`.
2. re-read T: `title == "Toner low"`, `description == "It jams"`, `category == "hardware"`.

### HTM-U-03 — category null from the creator clears the category
- **Rules:** `update_ticket` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(category=None), user_id=CR.id)`.

**Then**
1. returns: `result is T`.
2. re-read T: `category is None`, `title == "Printer jam"`, `description == "It jams"`.

### HTM-U-04 — an empty payload from a non-creator changes nothing and is no refusal
- **Rules:** `update_ticket` R1, R4 (nothing sent → no refusal), R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `updated_at PAST`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(), user_id=MGR.id)`.

**Then**
1. returns: `result is T`.
2. session: `db.is_modified(T) is False`.
3. unchanged: unchanged(T).
4. re-read T: `updated_at == PAST`.

### HTM-U-05 — only the sent field changes; a text change moves updated_at
- **Rules:** `update_ticket` R1, R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `updated_at PAST`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(description="Grey prints"), user_id=CR.id)`.

**Then**
1. returns: `result is T`.
2. re-read T: `description == "Grey prints"`, `title == "Printer jam"`, `category == "hardware"`.
3. re-read T: `updated_at != PAST`.

### HTM-U-06 — a platform admin closes an opened ticket: closed_at and closed_by stamped (revised 2026-11-26)
- **Rules:** `update_ticket` R5a, R5b, R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. returns: `result.closed_at == CLOSE_AT`.
3. re-read T: `status == "closed"`, `closed_by == ADM.id`, `closed_at == CLOSE_AT`.
4. re-read T: `title == "Printer jam"`, `description == "It jams"`, `category == "hardware"`.
5. re-read T: `type == "support"`, `created_by == CR.id`.

### HTM-U-07 — the creator, not a platform admin, may not close their own ticket (revised 2026-11-26)
- **Rules:** `update_ticket` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=CR.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError`.
3. raises: `isinstance(exc.value, PermissionError)`.
4. session: `db.is_modified(T) is False`.
5. session: `T.status == "opened"`, `T.closed_at is None`, `T.closed_by is None`.
6. session: `not db.dirty`, `not db.deleted`.
7. pending: `len(db.new) == 1`, `P in db.new`.
8. unchanged: unchanged(T).
9. nothing written.

### HTM-U-08 — a platform admin reopens a closed ticket: closed_at and closed_by are cleared (revised 2026-11-26)
- **Rules:** `update_ticket` R5a, R5c
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "opened"`, `closed_at is None`, `closed_by is None`.
3. re-read T: `title == "Printer jam"`, `type == "support"`.

### HTM-U-09 — status null from a non-admin leaves status, closed_at and closed_by and is no refusal (revised 2026-11-26)
- **Rules:** `update_ticket` R6 (no admin check)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=None), user_id=OWN.id)`.

**Then**
1. returns: `result is T`.
2. unchanged: unchanged(T).
3. re-read T: `status == "closed"`, `closed_at == PAST`, `closed_by == MGR.id`.

### HTM-U-10 — the creator edits a closed ticket's text; it stays closed (revised 2026-11-26)
- **Rules:** `update_ticket` R3 (D-10), R6, R11
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(category="network"), user_id=CR.id)`.

**Then**
1. returns: `result is T`.
2. re-read T: `category == "network"`, `status == "closed"`, `closed_at == PAST`, `closed_by == MGR.id`.
3. re-read T: `type == "support"`.

### HTM-U-11 — "archived" from a platform admin raises a plain ValueError, nothing written (revised 2026-11-26)
- **Rules:** `update_ticket` R6, Errors row 5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="archived"), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `ValueError`.
2. raises: `not isinstance(exc.value, HelpTicketInvalidTransitionError)`.
3. session: `db.is_modified(T) is False`.
4. session: `T.status == "pending"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-12 — "Closed" with a capital from a platform admin raises a plain ValueError (revised 2026-11-26)
- **Rules:** `update_ticket` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="Closed"), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `ValueError`.
2. raises: `not isinstance(exc.value, HelpTicketInvalidTransitionError)`.
3. session: `db.is_modified(T) is False`.
4. session: `T.status == "opened"`, `T.closed_at is None`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-13 — a plain string "closed" (not the enum) from a platform admin closes an opened ticket (revised 2026-11-26)
- **Rules:** `update_ticket` R5f, R5b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="closed"), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "closed"`, `closed_by == ADM.id`, `closed_at == CLOSE_AT`.

### HTM-U-14 — a plain string "opened" (not the enum) from a platform admin reopens a closed ticket (revised 2026-11-26)
- **Rules:** `update_ticket` R5f, R5c
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="opened"), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTM-U-15 — opening an opened ticket is refused and changes nothing (revised 2026-11-26)
- **Rules:** `update_ticket` R5a, R7, Errors row 3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from opened to opened."`.
3. session: `db.is_modified(T) is False`.
4. session: `not db.dirty`, `not db.deleted`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-16 — closing an already closed ticket is refused and keeps who closed it and when (revised 2026-11-26)
- **Rules:** `update_ticket` R7 (HR-9; BUG-1576 closed), R5a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from closed to closed."`.
3. session: `db.is_modified(T) is False`.
4. session: `T.closed_by == MGR.id`, `T.closed_at == PAST`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. re-read T: `closed_by == MGR.id`.
7. re-read T: `closed_at == PAST`.
8. re-read T: `status == "closed"`.

### HTM-U-17 — closed_at is the true moment whatever the database's time zone (revised 2026-11-26)
- **Rules:** `update_ticket` R5b [BUG-1577]
- **Kind:** bug
- **Expect:** xfail BUG-1577
- **Fails today on:** Then 2 (5 hours off under `America/New_York`)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`.
2. T = opened ticket `"HELP-2026-001"`.
3. Real clock: no close clock in this card.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `abs(closed_at - created_at) < timedelta(seconds=60)`.

### HTM-U-18 — a ground-team-manager (lower id) may not change a member's title; refused before any write
- **Rules:** `update_ticket` R4 [BUG-1863], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced and flushed)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Work order missing"), user_id=MGR.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `type(exc.value) is HelpTicketForbiddenError`.
3. raises: `str(exc.value) == FORBID`.
4. session: `db.is_modified(T) is False`.
5. session: `T.title == "Printer jam"`, `T.description == "It jams"`, `T.category == "hardware"`.
6. session: `not db.dirty`, `not db.deleted`.
7. pending: `len(db.new) == 1`, `P in db.new`.
8. unchanged: unchanged(T).
9. nothing written.

### HTM-U-19 — a finance member (higher id) may not change a member's description
- **Rules:** `update_ticket` R4 [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the description is replaced)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(description="Nothing happened"), user_id=FIN.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.description == "It jams"`.
5. session: `not db.dirty`, `not db.deleted`.
6. pending: `len(db.new) == 1`, `P in db.new`.
7. unchanged: unchanged(T).

### HTM-U-20 — an owner (higher id) may not change a member's category
- **Rules:** `update_ticket` R4 [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the category is replaced)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(category="other"), user_id=OWN.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.category == "hardware"`.
5. session: `not db.dirty`, `not db.deleted`.
6. pending: `len(db.new) == 1`, `P in db.new`.
7. unchanged: unchanged(T).

### HTM-U-21 — sending category null counts as a text change and is refused
- **Rules:** `update_ticket` R4 [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the category is cleared)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(category=None), user_id=MGR.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.category == "hardware"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-22 — sending the unchanged title still counts as a text change
- **Rules:** `update_ticket` R4 [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the same title is written)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Printer jam"), user_id=FIN.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-23 — a non-creator without the status right sends a title and a status: refused, nothing written (revised 2026-11-26)
- **Rules:** `update_ticket` R4a, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Work order missing", status=OPENED), user_id=MGR.id)`.

**Then**
1. raises: `PermissionError`.
2. session: `db.is_modified(T) is False`.
3. session: `T.status == "pending"`, `T.closed_at is None`, `T.closed_by is None`.
4. session: `T.title == "Printer jam"`.
5. session: `not db.dirty`, `not db.deleted`.
6. pending: `len(db.new) == 1`, `P in db.new`.
7. re-read T: `status == "pending"`, `title == "Printer jam"`.
8. unchanged: unchanged(T).

### HTM-U-24 — a non-creator without the status right sends a description and a reopen: refused, the ticket stays closed (revised 2026-11-26)
- **Rules:** `update_ticket` R4a, R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(description="Nothing happened", status=OPENED), user_id=OWN.id)`.

**Then**
1. raises: `PermissionError`.
2. session: `db.is_modified(T) is False`.
3. session: `T.status == "closed"`, `T.closed_at == PAST`, `T.closed_by == MGR.id`.
4. session: `T.description == "It jams"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. re-read T: `status == "closed"`, `closed_at == PAST`, `closed_by == MGR.id`.
7. unchanged: unchanged(T).

### HTM-U-25 — a ticket whose creator is gone has its text changed by nobody
- **Rules:** `update_ticket` R4 [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced)

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Work order missing"), user_id=OWN.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.title == "Printer jam"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).
7. nothing written.

### HTM-U-26 — a platform admin on the platform path may not change a member's description (revised 2026-11-26)
- **Rules:** `update_ticket` R4 [BUG-1863] (whatever `is_platform_admin` is)
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the description is replaced)

**Given**
1. T = ticket `"HELP-2026-001"`, but `workspace_id W2.id`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(description="Nothing happened"), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.description == "It jams"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-27 — the creator of other tickets, here and elsewhere, may not edit this one
- **Rules:** `update_ticket` R4 [BUG-1863] (creator grant held on a different record)
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced)

**Given**
1. T0 = ticket `"HELP-2026-002"`, but `workspace_id W0.id`, `created_by FIN.id`.
2. TA = ticket `"HELP-2026-001"`, but `created_by FIN.id`.
3. T = ticket `"HELP-2026-002"`.
4. TB = ticket `"HELP-2026-003"`, but `created_by FIN.id`.
5. TZ = ticket `"HELP-2026-002"`, but `workspace_id W2.id`, `created_by FIN.id`.
6. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Work order missing"), user_id=FIN.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.title == "Printer jam"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).
7. nothing written.

### HTM-U-28 — a refused text change neither commits nor rolls back
- **Rules:** `update_ticket` R4 [BUG-1863] (refusal before any write; the caller owns the transaction)
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- spies: `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Work order missing"), user_id=MGR.id)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `db.is_modified(T) is False`.
5. pending: `len(db.new) == 1`, `P in db.new`.

### HTM-U-29 — title null reaches the column: IntegrityError on flush, no rollback by the manager
- **Rules:** `update_ticket` R9, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- spies: `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"title"}, title=None), user_id=CR.id)`.

**Then**
1. raises: `IntegrityError` in a savepoint.
2. mock called: `rb.call_count == 0`.
3. mock called: `cm.call_count == 0`.
4. re-read T: `title == "Printer jam"`.

### HTM-U-30 — description null reaches the column: IntegrityError on flush
- **Rules:** `update_ticket` R9
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"description"}, description=None), user_id=CR.id)`.

**Then**
1. raises: `IntegrityError` in a savepoint.
2. re-read T: `description == "It jams"`.

### HTM-U-31 — update flushes but never commits or rolls back (revised 2026-11-26)
- **Rules:** `update_ticket` Returns (flushed, not committed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`, but `created_by ADM.id`.

**When**
- rolled back: `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Toner low", status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. in savepoint: `result is T`.
2. in savepoint: `db.execute(text("SELECT title, status FROM help_tickets WHERE id = :i"), {"i": T.id}).one() == ("Toner low", "closed")`.
3. mock called: `cm.call_count == 0`.
4. mock called: `rb.call_count == 0`.
5. after rollback: `db.execute(text("SELECT title, status FROM help_tickets WHERE id = :i"), {"i": T.id}).one() == ("Printer jam", "opened")`.

### HTM-U-32 — a creator who is a platform admin changes text and closes in one payload; both apply (revised 2026-11-26)
- **Rules:** `update_ticket` R3, R5a, R5b
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`, but `created_by ADM.id`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Toner low", status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `title == "Toner low"`, `status == "closed"`, `closed_by == ADM.id`, `closed_at == CLOSE_AT`.

### HTM-U-33 — a platform admin opens a pending ticket; the stamps stay empty
- **Rules:** `update_ticket` R5a, R5d
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "opened"`, `closed_at is None`, `closed_by is None`.
3. re-read T: `title == "Printer jam"`, `type == "support"`.

### HTM-U-34 — opening a pending ticket keeps stamps that were set directly
- **Rules:** `update_ticket` R5d
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `closed_at PAST`, `closed_by MGR.id`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "opened"`, `closed_at == PAST`, `closed_by == MGR.id`.

### HTM-U-35 — pending to closed is refused: a ticket is opened before it is closed
- **Rules:** `update_ticket` R5a, Errors row 3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `type(exc.value) is HelpTicketInvalidTransitionError`.
3. raises: `str(exc.value) == "Cannot transition from pending to closed."`.
4. raises: `isinstance(exc.value, ValueError)`.
5. session: `db.is_modified(T) is False`.
6. session: `T.status == "pending"`, `T.closed_at is None`, `T.closed_by is None`.
7. session: `not db.dirty`, `not db.deleted`.
8. pending: `len(db.new) == 1`, `P in db.new`.
9. unchanged: unchanged(T).
10. nothing written.

### HTM-U-36 — opened to pending is refused
- **Rules:** `update_ticket` R5a
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=PENDING), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from opened to pending."`.
3. session: `db.is_modified(T) is False`.
4. session: `T.status == "opened"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-37 — closed to pending is refused; the stamps stay
- **Rules:** `update_ticket` R5a
- **Kind:** error
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=PENDING), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from closed to pending."`.
3. session: `db.is_modified(T) is False`.
4. session: `T.status == "closed"`, `T.closed_at == PAST`, `T.closed_by == MGR.id`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-38 — pending to pending is refused
- **Rules:** `update_ticket` R5a, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=PENDING), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from pending to pending."`.
3. session: `db.is_modified(T) is False`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-39 — a refused move also drops the creator's text in the same payload
- **Rules:** `update_ticket` R5a (text not applied)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by ADM.id`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Toner low", status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from pending to closed."`.
3. session: `db.is_modified(T) is False`.
4. session: `T.title == "Printer jam"`, `T.status == "pending"`.
5. session: `not db.dirty`, `not db.deleted`.
6. pending: `len(db.new) == 1`, `P in db.new`.
7. unchanged: unchanged(T).

### HTM-U-40 — a stored legacy status "open" cannot be moved
- **Rules:** `update_ticket` R5e, Errors row 4
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from invalid status 'open'."`.
3. session: `db.is_modified(T) is False`.
4. session: `T.status == "open"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-41 — a stored empty status cannot be moved
- **Rules:** `update_ticket` R5e
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status ""`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from invalid status ''."`.
3. session: `db.is_modified(T) is False`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-42 — on a stored "open" ticket a caller without the status right gets the status refusal first
- **Rules:** `update_ticket` R5e (last sentence), R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=CR.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError`.
3. session: `db.is_modified(T) is False`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-43 — the move is checked against the status held in the session
- **Rules:** `update_ticket` R5f (status as held in the session)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. `T.status = "opened"` in memory, no flush (the stored row still says `"pending"`).

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "closed"`, `closed_by == ADM.id`, `closed_at == CLOSE_AT`.

### HTM-U-44 — the legacy value "open" requested by a platform admin raises a plain ValueError
- **Rules:** `update_ticket` R6
- **Kind:** error
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="open"), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `ValueError`.
2. raises: `not isinstance(exc.value, HelpTicketInvalidTransitionError)`.
3. session: `db.is_modified(T) is False`.
4. session: `T.status == "closed"`, `T.closed_at == PAST`, `T.closed_by == MGR.id`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-45 — a bad status value from a caller without the status right gets the status refusal first
- **Rules:** `update_ticket` R6 (last sentence), R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate.model_construct(_fields_set={"status"}, status="bogus"), user_id=MGR.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError`.
3. session: `db.is_modified(T) is False`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-46 — a non-creator without the status right may not open a pending ticket
- **Rules:** `update_ticket` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=MGR.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. session: `db.is_modified(T) is False`.
3. session: `T.status == "pending"`.
4. session: `not db.dirty`, `not db.deleted`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).
7. nothing written.

### HTM-U-47 — a same-status request without the status right gets the status refusal, not the transition error
- **Rules:** `update_ticket` R5 (before the value is checked)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=FIN.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `type(exc.value) is HelpTicketStatusChangeForbiddenError`.
3. session: `db.is_modified(T) is False`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-48 — a platform admin's profile without is_platform_admin passed is refused: the flag is trusted as passed
- **Rules:** `update_ticket` R5 (Inputs: `is_platform_admin` trusted as passed)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=ADM.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. session: `db.is_modified(T) is False`.
3. session: `T.status == "pending"`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-49 — the creator without the status right sends text and a status: refused whole, the text not applied
- **Rules:** `update_ticket` R5 (text not applied, even the creator's)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Toner low", status=OPENED), user_id=CR.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. session: `db.is_modified(T) is False`.
3. session: `T.title == "Printer jam"`, `T.status == "pending"`.
4. session: `not db.dirty`, `not db.deleted`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. re-read T: `title == "Printer jam"`, `status == "pending"`.
7. unchanged: unchanged(T).

### HTM-U-50 — a refused status change neither commits nor rolls back
- **Rules:** `update_ticket` R5 (refusal before any write; the caller owns the transaction)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`.
2. pending P.

**When**
- spies: `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=MGR.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `db.is_modified(T) is False`.
5. pending: `len(db.new) == 1`, `P in db.new`.

### HTM-U-51 — the status refusal says who may not, not "only platform admins"
- **Rules:** `update_ticket` R5h [BUG-3251], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 2 (today's message is "Only platform admins may change ticket status.")

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=CR.id)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. raises: `str(exc.value) == STATUS_FORBID`.

### HTM-U-52 — a platform admin who is not the creator sends text and a status: R4's refusal, the status not applied
- **Rules:** `update_ticket` R4a (second half), R4 [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-1863
- **Fails today on:** Then 1 (no error: the title is replaced and the ticket opened)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Work order missing", status=OPENED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.title == "Printer jam"`, `T.status == "pending"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-53 — a ground-team-manager who is not the creator sends text and a status: R4's refusal
- **Rules:** `update_ticket` R4a (second half), R5g [BUG-3251], R4 [BUG-1863]
- **Kind:** bug
- **Expect:** xfail BUG-3251 (passes only once BUG-1863 is fixed too)
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Work order missing", status=OPENED), user_id=MGR.id, role=GTM_R)`.

**Then**
1. raises: `HelpTicketForbiddenError`.
2. raises: `str(exc.value) == FORBID`.
3. session: `db.is_modified(T) is False`.
4. session: `T.title == "Printer jam"`, `T.status == "pending"`.
5. pending: `len(db.new) == 1`, `P in db.new`.
6. unchanged: unchanged(T).

### HTM-U-54 — a caller with role owner closes an opened ticket like a platform admin
- **Rules:** `update_ticket` R5g [BUG-3251], R5b
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. T = opened ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=OWN.id, role=OWNER_R)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "closed"`, `closed_by == OWN.id`, `closed_at == CLOSE_AT`.

### HTM-U-55 — a caller with role ground-team-manager opens a pending ticket
- **Rules:** `update_ticket` R5g [BUG-3251], R5d
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=MGR.id, role=GTM_R)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTM-U-56 — the workspace owner with a plain role reopens a closed ticket
- **Rules:** `update_ticket` R5g [BUG-3251] (workspace `owner_user_id`), R5c
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. T = closed ticket `"HELP-2026-001"`.
2. owner of W1 by FIN.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=FIN.id, role=FIN_R)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "opened"`, `closed_at is None`, `closed_by is None`.

### HTM-U-57 — a ground-team-manager is held to the transition table: pending to closed is refused
- **Rules:** `update_ticket` R5g [BUG-3251], R5a
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. T = ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=MGR.id, role=GTM_R)`.

**Then**
1. raises: `HelpTicketInvalidTransitionError`.
2. raises: `str(exc.value) == "Cannot transition from pending to closed."`.
3. session: `db.is_modified(T) is False`.
4. pending: `len(db.new) == 1`, `P in db.new`.
5. unchanged: unchanged(T).

### HTM-U-58 — the creator with role ground-team is refused a status change
- **Rules:** `update_ticket` R5 (with the fix's `role`), R5g [BUG-3251]
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. T = opened ticket `"HELP-2026-001"`.
2. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=CR.id, role=GT_R)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. session: `db.is_modified(T) is False`.
3. pending: `len(db.new) == 1`, `P in db.new`.
4. unchanged: unchanged(T).

### HTM-U-59 — the owner of the later workspace, finance here, is refused a status change on W1's ticket
- **Rules:** `update_ticket` R5, R5g [BUG-3251] (owner grant held on a different workspace)
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. owner of W2 by FIN.
2. T = ticket `"HELP-2026-001"`.
3. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=OPENED), user_id=FIN.id, role=FIN_R)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. session: `db.is_modified(T) is False`.
3. pending: `len(db.new) == 1`, `P in db.new`.
4. unchanged: unchanged(T).

### HTM-U-60 — the owner of the earlier workspace, ground-team here, is refused a status change on W1's ticket
- **Rules:** `update_ticket` R5, R5g [BUG-3251] (owner grant held on a different workspace)
- **Kind:** bug
- **Expect:** xfail BUG-3251
- **Fails today on:** Then 1 (the call raises TypeError: `update_ticket` takes no `role` yet)

**Given**
1. owner of W0 by MGR.
2. T = opened ticket `"HELP-2026-001"`.
3. pending P.

**When**
- `HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=MGR.id, role=GT_R)`.

**Then**
1. raises: `HelpTicketStatusChangeForbiddenError`.
2. session: `db.is_modified(T) is False`.
3. pending: `len(db.new) == 1`, `P in db.new`.
4. unchanged: unchanged(T).

### HTM-U-61 — a feedback ticket stays feedback through a text change and a status move
- **Rules:** `update_ticket` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by ADM.id`, `type "feedback"`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(title="Nice reports", status=OPENED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `title == "Nice reports"`, `status == "opened"`.
3. re-read T: `type == "feedback"`.

### HTM-U-62 — the update schema has no type field and drops a sent type
- **Rules:** `update_ticket` R11 (D-6; target `schema`)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- build `result = HelpTicketUpdate(title="Nice reports", type="support")` (target `schema`; the manager is not called).

**Then**
1. returns: `result.model_dump(exclude_unset=True) == {"title": "Nice reports"}`.
2. returns: `"type" not in HelpTicketUpdate.model_fields`.

### HTM-U-63 — the transition table holds exactly the three moves
- **Rules:** `update_ticket` R5a (Facts: `ALLOWED_STATUS_TRANSITIONS`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Standing rows only.

**When**
- `result = ALLOWED_STATUS_TRANSITIONS`.

**Then**
1. returns: `result == {PENDING: {OPENED}, OPENED: {CLOSED}, CLOSED: {OPENED}}`.

### HTM-U-64 — closing overwrites stamps an opened ticket already carries
- **Rules:** `update_ticket` R5b (`closed_by = user_id`, `closed_at = utcnow()`, always written)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = opened ticket `"HELP-2026-001"`, but `closed_at PAST`, `closed_by MGR.id`.

**When**
- `result = HM.update_ticket(db, ticket=T, payload=HelpTicketUpdate(status=CLOSED), user_id=ADM.id, is_platform_admin=True)`.

**Then**
1. returns: `result is T`.
2. re-read T: `status == "closed"`.
3. re-read T: `closed_by == ADM.id`.
4. re-read T: `closed_at == CLOSE_AT`.

## `HelpTicketManager.to_response`

### HTM-R-01 — every field of the row, type included, and the creator's name (revised 2026-11-26)
- **Rules:** `to_response` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-007"`, but `type "feedback"`.

**When**
- `result = HelpTicketManager.to_response(ticket=T)`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`.
2. returns: `result.id == T.id`, `result.workspace_id == W1.id`, `result.ticket_number == "HELP-2026-007"`.
3. returns: `result.title == "Printer jam"`, `result.description == "It jams"`, `result.category == "hardware"`.
4. returns: `result.status == CLOSED`, `result.closed_at == PAST`, `result.closed_by == MGR.id`.
5. returns: `result.type == FEEDBACK`, `isinstance(result.type, HelpTicketTypeEnum)`.
6. returns: `result.created_by == CR.id`, `result.creator_name == "Rahim"`.
7. returns: `result.created_at == db.scalar(select(HelpTicket.created_at).where(HelpTicket.id == T.id))`.
8. returns: `result.updated_at == db.scalar(select(HelpTicket.updated_at).where(HelpTicket.id == T.id))`.

### HTM-R-02 — no creator gives creator_name None
- **Rules:** `to_response` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HelpTicketManager.to_response(ticket=T)`.

**Then**
1. returns: `result.id == T.id`, `result.created_by is None`.
2. returns: `result.creator_name is None`.

### HTM-R-03 — an unflushed row is not a valid response
- **Rules:** `to_response` Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. `U = HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-009", title="Loose", description="Never flushed", created_by=CR.id)`, not added to `db`.

**When**
- `HelpTicketManager.to_response(ticket=U)`.

**Then**
1. raises: `PydanticValidationError`.

### HTM-R-04 — a pending support ticket maps to the enum values
- **Rules:** `to_response` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager.to_response(ticket=T)`.

**Then**
1. returns: `result.status == PENDING`, `isinstance(result.status, HelpTicketStatusEnum)`.
2. returns: `result.type == SUPPORT`.

### HTM-R-05 — a stored legacy status "open" is not a valid response
- **Rules:** `to_response` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `status "open"`.

**When**
- `HelpTicketManager.to_response(ticket=T)`.

**Then**
1. raises: `PydanticValidationError`.

### HTM-R-06 — a stored type outside the enum is not a valid response
- **Rules:** `to_response` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `type "question"`.

**When**
- `HelpTicketManager.to_response(ticket=T)`.

**Then**
1. raises: `PydanticValidationError`.

### HTM-R-07 — an object with no creator attribute gives creator_name None, no error
- **Rules:** `to_response` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.
2. `S = SimpleNamespace(**{c: getattr(T, c) for c in ("id", "workspace_id", "ticket_number", "title", "description", "category", "status", "type", "created_by", "created_at", "updated_at", "closed_at", "closed_by")})` (no `creator` attribute).

**When**
- `result = HelpTicketManager.to_response(ticket=S)`.

**Then**
1. returns: `isinstance(result, HelpTicketResponse)`, `result.id == T.id`.
2. returns: `result.created_by == CR.id`, `result.creator_name is None`.

### HTM-R-08 — a creator named "" gives creator_name "", not None
- **Rules:** `to_response` R2a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. E = `make_profile(db, name="")`.
2. T = ticket `"HELP-2026-001"`, but `created_by E.id`.

**When**
- `result = HelpTicketManager.to_response(ticket=T)`.

**Then**
1. returns: `result.created_by == E.id`.
2. returns: `result.creator_name == ""`.

## `HelpTicketManager._to_platform_item`

### HTM-I-01 — every response field, the given workspace name and the given creator name (revised 2026-11-26)
- **Rules:** `_to_platform_item` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = closed ticket `"HELP-2026-007"`, but `workspace_id W2.id`, `type "feedback"`.

**When**
- `result = HelpTicketManager._to_platform_item(ticket=T, workspace_name="Elsewhere", creator_name="Zed")`.

**Then**
1. returns: `isinstance(result, PlatformHelpTicketListItem)`.
2. returns: `result.workspace_name == "Elsewhere"`, `result.creator_name == "Zed"`.
3. returns: `result.id == T.id`, `result.workspace_id == W2.id`, `result.ticket_number == "HELP-2026-007"`.
4. returns: `result.title == "Printer jam"`, `result.status == CLOSED`, `result.closed_by == MGR.id`, `result.created_by == CR.id`.
5. returns: `result.type == FEEDBACK`.

### HTM-I-02 — creator_name None falls back to the loaded creator's name
- **Rules:** `_to_platform_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager._to_platform_item(ticket=T, workspace_name="Elsewhere", creator_name=None)`.

**Then**
1. returns: `result.creator_name == "Rahim"`.

### HTM-I-03 — creator_name "" falls back to the loaded creator's name
- **Rules:** `_to_platform_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`.

**When**
- `result = HelpTicketManager._to_platform_item(ticket=T, workspace_name="Elsewhere", creator_name="")`.

**Then**
1. returns: `result.creator_name == "Rahim"`.

### HTM-I-04 — no given name and no creator gives None
- **Rules:** `_to_platform_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HelpTicketManager._to_platform_item(ticket=T, workspace_name="Elsewhere", creator_name=None)`.

**Then**
1. returns: `result.creator_name is None`.
2. returns: `result.workspace_name == "Elsewhere"`.

### HTM-I-05 — a given name wins over a ticket without a creator
- **Rules:** `_to_platform_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = ticket `"HELP-2026-001"`, but `created_by None`.

**When**
- `result = HelpTicketManager._to_platform_item(ticket=T, workspace_name="Elsewhere", creator_name="Zed")`.

**Then**
1. returns: `result.creator_name == "Zed"`.

## Retired IDs
None. Every card of revision 1 still tests the same scenario (2026-11-26). Where a rule changed, the card keeps its id and now carries the new outcome: U-07 (the creator closing their own ticket) is refused under R5; U-15 / U-16 (same-status moves) are refused under R5a / R7; U-16 is no longer xfail because BUG-1576 is closed; U-23 / U-24 (text + status from a non-creator) pass under R4a. Retired convention name: `OPEN` (`HelpTicketStatusEnum("open")` raises today).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `can_access_ticket` R4 / BUG-1885 (only an `active` membership's role counts) | endpoint role lookup `_workspace_role` | a suspended owner gets 403 / 404, not the owner's view; also for status changes (R5g) |
| Role held in **another** workspace (owner / manager of W2 calling for W1) | endpoint role lookup | the role passed is the caller's role in the path's workspace only |
| 404 / 403 translation of `HelpTicketNotFoundError` / `HelpTicketForbiddenError` | `/help-tickets/` endpoints | incl. BUG-1863's text refusal → 403 |
| 403 / 400 translation of `HelpTicketStatusChangeForbiddenError` / `HelpTicketInvalidTransitionError` | `/help-tickets/` and `/platform/help/tickets/{id}` PATCH | 403 and 400 with the manager's message; R6's plain `ValueError` is unreachable through the schema |
| The service passing `is_platform_admin` (workspace PATCH: the caller's flag; platform PATCH: `True`) | `HelpTicketService.update_ticket`, `update_platform_ticket` (FU-3) | the flag reaches the manager as stated |
| 🐞 BUG-3251: the service handing the manager the caller's role and the workspace owner (FU-6) | `HelpTicketService.update_ticket` | owner / ground-team-manager / `owner_user_id` may move status; plain member 403 |
| `update_platform_ticket` finds the ticket in any workspace, 404 when missing | `HelpTicketService.update_platform_ticket` (FU-3) | HR-16 exception, platform admins only |
| `get_platform_admin` guard (`list_platform_tickets` R3) | `/platform/help/tickets` endpoints | non-admin → 403 |
| HR-7 `limit` / `skip` bounds | endpoints | 422 for `limit=0`, `limit=201`, `skip=-1` |
| BUG-1574 / BUG-1575 (trimming, `null` text refused by the schema) | `HelpTicketCreate` / `HelpTicketUpdate`; already HTS-C-06 … C-09, HTS-U-26 … U-31 | — |
| BUG-1441 year / BUG-1440 concurrent numbers (`create_ticket` R1 pass-through) | DAO cases; HTS-C-05; integration test | — |
| BUG-1442 order / BUG-1443 search wildcards (pass-through in `list_tickets` R1, `list_platform_tickets` R1); `ticket_type` filter's exact match | DAO `help_ticket.cases.md` (FU-4); HTS-L-16, HTS-P-05 | — |
| BUG-1950 (attachments follow the ticket's visibility; FU-1) | `AttachmentManager` / attachment service spec | list / sign / confirm on a ticket `can_access_ticket` refuses → 404, nothing written |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `can_access_ticket` R3 | **Closed 2026-11-26** (spec R3a: unreachable, no card). (from revision 1) R3 says a ticket with `created_by None` is open to R1, R2 and R5 only, but the branch map gives the test as `created_by == user.id`. For a user object whose `id` is `None` (not admin, plain role) those two disagree (`None == None`). Is that input possible, and is the intended answer `False`? | No card: a real profile always has an id, and a card would encode a guess. |
| 2 | `to_response` R2 / branch line 207 | **Closed 2026-11-26** (spec R2a → HTM-R-07, R-08). (from revision 1) The spec states only "creator `None` → `creator_name` None"; the code reads `getattr(ticket, "creator", None)`, so an object without a `creator` attribute is also handled, but no rule says so. Also unstated: a creator whose `name` is `""` (falsy). | No card for either; R2 is covered for real rows (R-01, R-02). |
| 3 | `update_ticket` Inputs, R5g, Notes (BUG-3251) | **Closed 2026-11-26** (spec: keyword-only `role`, type `str` or `None`, default `None`; no flag; cards unchanged). The fix's new input is given as "e.g. a new keyword `role`, … or a `can_change_status` flag", and its default is not stated. The cards follow the Notes (`role=` keyword) and assume that leaving `role` out means "no role" (every today-passing `update_ticket` card calls without it). Two decisions are needed: (a) `role` keyword vs a flag; (b) `role` defaults to `None`. | Not blocking today. If the fix picks a flag, U-53 … U-60 must be rewritten; if `role` becomes required, every passing `update_ticket` card would break with `TypeError`. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `can_view_all_tickets` | R1 | HTM-VA-01 … HTM-VA-14 |
| `can_access_ticket` | R1 | HTM-AC-01, AC-02, AC-11, AC-13, AC-14, AC-15 |
| `can_access_ticket` | R2 | HTM-AC-03, AC-04, AC-05, AC-06, AC-15, AC-16 |
| `can_access_ticket` | R3 | HTM-AC-06, AC-07, AC-08, AC-09, AC-10, AC-11, AC-12, AC-14, AC-17, AC-22, AC-23 |
| `can_access_ticket` | R3a | none: unreachable per spec (gap 1, closed) |
| `can_access_ticket` | R4 | HTM-AC-19; BUG-1885 and role-in-another-workspace deferred |
| `can_access_ticket` | R5 [BUG-2103] | HTM-AC-20, AC-21, AC-22; kept passing AC-23 (owner of another workspace); `owner_user_id None` grants nobody: every standing workspace (AC-09 … AC-12) |
| `can_access_ticket` | R6 | HTM-AC-24, AC-25 |
| `can_access_ticket` | Persistence (pure) | HTM-AC-18 |
| `get_by_id_and_workspace` | R1 / Errors row 1 | HTM-G-11 … HTM-G-18 |
| `get_by_id_and_workspace` | R2 / Errors row 2 | HTM-G-06 … HTM-G-10, HTM-G-19, HTM-G-21, HTM-G-22 (BUG-2103) |
| `get_by_id_and_workspace` | R3 | HTM-G-01 … HTM-G-05 |
| `get_by_id_and_workspace` | Side effects | HTM-G-20, HTM-G-21 |
| `list_tickets` | R1 | HTM-L-01 … HTM-L-13, HTM-L-16, HTM-L-20, HTM-L-24, HTM-L-25, HTM-L-29 |
| `list_tickets` | R1a | HTM-L-21 … HTM-L-26 |
| `list_tickets` | R2 [BUG-1578] | HTM-L-14, HTM-L-15; kept HTM-L-16 |
| `list_tickets` | R2a [BUG-3250] | HTM-L-27, L-28, L-30; kept HTM-L-29 |
| `list_tickets` | Errors (DataError) | HTM-L-17, HTM-L-18 |
| `list_tickets` | Side effects | HTM-L-19 |
| `list_platform_tickets` | R1 | HTM-P-01, P-04, P-05, P-07, P-08, P-13 |
| `list_platform_tickets` | R1a | HTM-P-12, P-13, P-14 |
| `list_platform_tickets` | R2 | HTM-P-01, P-02, P-03, P-06, P-10 |
| `list_platform_tickets` | R3 | HTM-P-01 (no user argument); guard deferred |
| `list_platform_tickets` | Errors (DataError) | HTM-P-09 |
| `list_platform_tickets` | Side effects | HTM-P-11 |
| `get_platform_ticket` | R1 | HTM-Q-01, HTM-Q-02 |
| `get_platform_ticket` | R2 | HTM-Q-03, HTM-Q-04 |
| `get_platform_ticket` | Side effects | HTM-Q-05 |
| `create_ticket` | R1 | HTM-C-01, C-02, C-03, C-06; BUG-1440 / BUG-1441 deferred |
| `create_ticket` | R1a | HTM-C-01, C-02, C-07 |
| `create_ticket` | R1b | HTM-C-01 (not sent), C-02 (no `type` key), C-07 (feedback) |
| `create_ticket` | Errors (IntegrityError R4, R5) | HTM-C-05, HTM-C-04 |
| `update_ticket` | R1 | HTM-U-04, U-05 |
| `update_ticket` | R2 | HTM-U-01, U-03 |
| `update_ticket` | R3 | HTM-U-01, U-02, U-10, U-32 |
| `update_ticket` | R4 [BUG-1863] / Errors row 1 | HTM-U-18 … U-22, U-25 … U-28, U-52; kept U-04 (nothing sent) |
| `update_ticket` | R4a | HTM-U-23, U-24 (pass); U-52 (BUG-1863), U-53 (BUG-3251) |
| `update_ticket` | R5 / Errors row 2 | HTM-U-07, U-23, U-24, U-42, U-45 … U-50; with the fix's `role`: U-58, U-59, U-60 (BUG-3251) |
| `update_ticket` | R5g [BUG-3251] | HTM-U-53 … HTM-U-60 |
| `update_ticket` | R5h [BUG-3251] | HTM-U-51 |
| `update_ticket` | R5a / Errors row 3 | HTM-U-06, U-08, U-15, U-16, U-33, U-35 … U-39, U-57, U-63 |
| `update_ticket` | R5b (and BUG-1577) | HTM-U-06, U-13, U-32, U-43, U-54, U-64 (stamps already set); BUG-1577 HTM-U-17 |
| `update_ticket` | R5c | HTM-U-08, U-14, U-56 |
| `update_ticket` | R5d | HTM-U-33, U-34, U-55 |
| `update_ticket` | R5e / Errors row 4 | HTM-U-40, U-41, U-42 |
| `update_ticket` | R5f | HTM-U-13, U-14, U-43 |
| `update_ticket` | R6 / Errors row 5 | HTM-U-09, U-10, U-11, U-12, U-44, U-45 |
| `update_ticket` | R7 | HTM-U-15, U-16, U-38 |
| `update_ticket` | R8 | removed in the spec (moved into R5b) |
| `update_ticket` | R9 / Errors row 6 | HTM-U-29, HTM-U-30 |
| `update_ticket` | R10 | HTM-U-04, HTM-U-05 |
| `update_ticket` | R11 | HTM-U-01, U-06, U-10, U-61, U-62 (schema) |
| `update_ticket` | Returns (flushed, not committed) | HTM-U-31 |
| `to_response` | R1 | HTM-R-01, HTM-R-04 |
| `to_response` | R2 | HTM-R-01, HTM-R-02 |
| `to_response` | R2a | HTM-R-07, HTM-R-08 |
| `to_response` | R3 | HTM-R-05, HTM-R-06 |
| `to_response` | Errors | HTM-R-03, R-05, R-06 |
| `_to_platform_item` | R1 | HTM-I-01, I-04 |
| `_to_platform_item` | R2 | HTM-I-01 … HTM-I-05 |
