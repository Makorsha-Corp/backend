# Test cases — `app/dao/help_ticket.py`

> **Spec:** `tests/unit/dao/help_ticket.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1, P2 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `help_ticket.verify.md` (case-missing Findings 1 … 6; recipes R-1 … R-6): R-1 → HLP-LW-23 … LW-25; R-2 → HLP-LP-25; R-3 → HLP-GN-11, LW-26; R-4 → HLP-GN-10 and GP-06 gain an unflushed edit (two Given lines and two `pending:` Then lines each, placed before the `statement:` and `nothing written:` lines, which move from 4, 5 to 6, 7; GN-10's and GP-06's later Given lines move down by two); R-5 → HLP-GB-06; R-6 → HLP-LW-27, LP-26. No ID retired.
> **Counts:** 92 cases · 82 expected-to-pass · 10 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `generate_ticket_number` 11 · `create_with_user` 8 (1 bug) · `get_by_id` 6 · `get_by_id_and_workspace` 8 · `list_by_workspace` 27 (3 bug) · `list_platform` 26 (6 bug) · `get_platform_by_id` 6.
- **Depth:** lighter target (skill step 1a). Support tickets: numbering, one insert, by-id reads and two filtered lists; no stock, money or order state.
- **Expected-to-fail:** BUG-1441 1, strict: HLP-CW-03. BUG-1442 6: HLP-LW-17, LW-27, HLP-LP-20, LP-26 non-strict; HLP-LW-18, HLP-LP-21 strict (the SQL recorder). BUG-1443 3, strict: HLP-LP-11 (`_`), LP-12 (`%`), LP-13 (`\`).
- **Not carded:** `create_with_user` R3 [BUG-1440] (two concurrent creates) — the spec says it is not unit-testable; Deferred. R4 holds the single-connection outcome (HLP-CW-04).
- **Commit spies:** `create_with_user` 1 (HLP-CW-08).
- **Notable design choices:**
  - `list_platform` and the two unscoped lookups read every workspace of a shared database. Each test makes its own tag TAG and names its workspaces with it; platform cards search for TAG (or a value holding TAG) and compare only the test's own tickets. Two cards (`search` `None` and `""`) cannot narrow and use `limit=1000` (Spec gap 3).
  - The wildcard cards put TAG next to the wildcard, so the decoy only matches through the wildcard.
  - Numbering cards use a fixed `year`; the clock is patched only for `create_with_user`.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `HLP` = `app/dao/help_ticket.py`. `GN` generate_ticket_number · `CW` create_with_user · `GB` get_by_id · `GW` get_by_id_and_workspace · `LW` list_by_workspace · `LP` list_platform · `GP` get_platform_by_id.

**Actors and fixed values.**
- `dao` = the singleton `help_ticket_dao` (`from app.dao.help_ticket import help_ticket_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `HelpTicket` = `app.models.help_ticket.HelpTicket`. `HelpTicketCreate` = `app.schemas.help_ticket.HelpTicketCreate`. `IntegrityError`, `DataError` = `sqlalchemy.exc` classes. `text` = `sqlalchemy.text`. `sa_inspect` = `sqlalchemy.inspect`. `datetime` = the `datetime` module's class.
- MISSING = `999999999`: an id that no row of any table has.
- TAG = `uuid.uuid4().hex[:8]`, made once at the start of each test.

**Externals.** Only in `CW` cards: **clock(L, U)** = for the When, patch `app.dao.help_ticket.datetime` with a subclass of `datetime` whose `now()` returns L, and patch both `app.dao.help_ticket.utcnow` (with `create=True`) and `app.utils.time.utcnow` to return U. A `CW` card without a clock line runs under clock(`datetime(2026, 6, 1, 12, 0)`, `datetime(2026, 6, 1, 12, 0)`).

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1 = `make_workspace(name=f"Gamma {TAG}")`, W2 = `make_workspace(name=f"Delta {TAG}")`; U1 = `make_profile(name="Rahim")`, U2 = `make_profile(name="Karim")`.
- **ticket** = `HelpTicket(workspace_id=W1.id, ticket_number=N, title="Printer jam", description="It jams", created_by=U1.id)`; `status` is left to its default `"open"`. The card always gives `ticket_number`; after "but" it lists every other column that differs. No ticket of W1 or W2 exists unless the Given lists it.
- **newer(X, h)** = `db.execute(text("UPDATE help_tickets SET created_at = now() + make_interval(hours => :h) WHERE id = :i"), {"h": h, "i": X.id})`, then `db.expire_all()` (a negative h makes it older).
- **bumpT(X)** = `db.execute(text("UPDATE help_tickets SET title = title WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`; **tids(result)** = `[r[0].id for r in result]` (platform tuples). The order is part of the check.
- **OWN** = the set of ids of the tickets the card's Given made. **own(result)** = `[r[0].id for r in result if r[0].id in OWN]`, in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. **NOW_DB** = `db.scalar(text("SELECT now()"))`.
- **w1_count** = `db.scalar(text("SELECT count(*) FROM help_tickets WHERE workspace_id = :w"), {"w": W1.id})`.
- **nothing written** = the numbers of `help_tickets` rows of W1 and of W2 equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` lines.
- `raises: E` (`IntegrityError` or `DataError`) = wrap the call: `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, one `assert` per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `selects` = every `SELECT` recorded; `sql` = the text of the one `SELECT` from `help_tickets`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `DAOHelpTicket.generate_ticket_number`

### HLP-GN-01 — no ticket yet gives HELP-2026-001
- **Rules:** `generate_ticket_number` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no ticket.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `isinstance(result, str)`.
2. returns: `result == "HELP-2026-001"`.

### HLP-GN-02 — two tickets give HELP-2026-003
- **Rules:** `generate_ticket_number` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-003"`.

### HLP-GN-03 — 999 tickets give HELP-2026-1000
- **Rules:** `generate_ticket_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 999 tickets E1 … E999, built with `add_all` and flushed: Ek = ticket, `ticket_number` = `f"HELP-2026-{k:03d}"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-1000"`.

### HLP-GN-04 — another workspace's tickets do not count
- **Rules:** `generate_ticket_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.
2. Z2 = ticket, `ticket_number "HELP-2026-002"`, but `workspace_id W2.id`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-001"`.

### HLP-GN-05 — another year's tickets do not count
- **Rules:** `generate_ticket_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2025-001"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-001"`.

### HLP-GN-06 — year 1 is used as given, and "HELP-10-" does not count for it
- **Rules:** `generate_ticket_number` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-10-001"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=1)`.

**Then**
1. returns: `result == "HELP-1-001"`.

### HLP-GN-07 — a number changed to 009 still counts as one
- **Rules:** `generate_ticket_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-009"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-003"`.

### HLP-GN-08 — a non-numeric suffix counts
- **Rules:** `generate_ticket_number` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-ABC"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-002"`.

### HLP-GN-09 — only numbers that start with the prefix count
- **Rules:** `generate_ticket_number` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "XHELP-2026-001"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-001"`.

### HLP-GN-10 — writes nothing: a pending ticket stays pending and is not counted, an unflushed edit stays unflushed
- **Rules:** `generate_ticket_number` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. B = ticket, `ticket_number "HELP-2025-001"`.
2. `B.title = "Edited"` (not flushed).
3. `P = HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-001", title="Printer jam", description="It jams", created_by=U1.id)`
4. `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W1.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-001"`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### HLP-GN-11 — asked for W2, the earlier W1 ticket does not count
- **Rules:** `generate_ticket_number` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.generate_ticket_number(db, workspace_id=W2.id, year=2026)`.

**Then**
1. returns: `result == "HELP-2026-001"`.

## `DAOHelpTicket.create_with_user`

### HLP-CW-01 — a ticket is opened with the schema's fields, the next number and status open
- **Rules:** `create_with_user` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no ticket.

**When**
- `result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="Printer jam", description="It jams", category="hardware"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, HelpTicket)`.
2. returns: `result.id is not None`.
3. re-read result: `ticket_number == "HELP-2026-001"`, `status == "open"`, `workspace_id == W1.id`, `created_by == U1.id`.
4. re-read result: `title == "Printer jam"`, `description == "It jams"`, `category == "hardware"`.
5. re-read result: `closed_at is None`, `closed_by is None`.
6. re-read result: `created_at == NOW_DB`, `updated_at == NOW_DB`.
7. count: `w1_count == 1`.

### HLP-CW-02 — the second ticket gets the next number
- **Rules:** `create_with_user` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `ticket_number == "HELP-2026-002"`, `created_by == U2.id`.

### HLP-CW-03 — the year comes from UTC, not the server's local clock
- **Rules:** `create_with_user` R2 [BUG-1441]
- **Kind:** bug
- **Expect:** xfail BUG-1441
- **Fails today on:** Then 2 (the local year is used: `HELP-2027-001`)

**Given**
1. W1 has no ticket.
2. clock(`datetime(2027, 1, 1, 5, 0)`, `datetime(2026, 12, 31, 23, 0)`).

**When**
- `result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="Printer jam", description="It jams"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `ticket_number == "HELP-2026-001"`.

### HLP-CW-04 — a computed number already taken fails at the flush and saves nothing
- **Rules:** `create_with_user` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. C = ticket, `ticket_number "HELP-2026-004"`.

**When**
- `dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"), workspace_id=W1.id, user_id=U1.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. raises: `"uq_help_tickets_workspace_number" in str(exc.value.orig)`.
3. count: `w1_count == 3`.

### HLP-CW-05 — an unknown user raises IntegrityError 23503
- **Rules:** `create_with_user` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no ticket.

**When**
- `dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"), workspace_id=W1.id, user_id=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### HLP-CW-06 — an unknown workspace raises IntegrityError 23503
- **Rules:** `create_with_user` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no ticket.

**When**
- `dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"), workspace_id=MISSING, user_id=U1.id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### HLP-CW-07 — values are stored as the schema gives them, untrimmed
- **Rules:** `create_with_user` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no ticket.

**When**
- `result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="  Jam  ", description=" It jams "), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `title == "  Jam  "`, `description == " It jams "`.

### HLP-CW-08 — flushed, not committed: a rollback removes the ticket
- **Rules:** `create_with_user` R1, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no ticket.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create_with_user(db, obj_in=HelpTicketCreate(title="Leak", description="Drips"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `w1_count == 1`.
3. count: after the savepoint rollback, `w1_count == 0`.
4. mock called: the `db.commit` spy was never called.

## `DAOHelpTicket.get_by_id`

### HLP-GB-01 — returns the ticket with its creator, in one query
- **Rules:** `get_by_id` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. `db.expire_all()`
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id(db, ticket_id=A.id)`.

**Then**
1. returns: `isinstance(result, HelpTicket)`.
2. returns: `result.id == A.id`.
3. returns: `"creator" not in sa_inspect(result).unloaded`.
4. statement: `len(selects) == 1`.
5. returns: `result.creator.id == U1.id`.

### HLP-GB-02 — a ticket of another workspace is returned
- **Rules:** `get_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id(db, ticket_id=Z.id)`.

**Then**
1. returns: `result.id == Z.id`.

### HLP-GB-03 — an unknown id returns None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_by_id(db, ticket_id=MISSING)`.

**Then**
1. returns: `result is None`.

### HLP-GB-04 — id 0 returns None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_by_id(db, ticket_id=0)`.

**Then**
1. returns: `result is None`.

### HLP-GB-05 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. `B.title = "Edited"` (not flushed).
4. `P = HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-003", title="Printer jam", description="It jams", created_by=U1.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id(db, ticket_id=A.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### HLP-GB-06 — a ticket without a creator is returned, with creator None
- **Rules:** `get_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `created_by None`.

**When**
- `result = dao.get_by_id(db, ticket_id=A.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.creator is None`.

## `DAOHelpTicket.get_by_id_and_workspace`

### HLP-GW-01 — returns the ticket with its creator, in one statement with a LEFT OUTER JOIN
- **Rules:** `get_by_id_and_workspace` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. `db.expire_all()`
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `"creator" not in sa_inspect(result).unloaded`.
3. statement: `len(selects) == 1`.
4. statement: `"LEFT OUTER JOIN" in sql.upper()`.
5. statement: `"profiles" in sql`.

### HLP-GW-02 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.
2. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### HLP-GW-03 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### HLP-GW-04 — the id under another workspace returns None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### HLP-GW-05 — an unknown id returns None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### HLP-GW-06 — id 0 returns None
- **Rules:** `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### HLP-GW-07 — a ticket without a creator is returned with creator None
- **Rules:** `get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `created_by None`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.creator is None`.

### HLP-GW-08 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed
- **Rules:** `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. `B.title = "Edited"` (not flushed).
4. `P = HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-003", title="Printer jam", description="It jams", created_by=U1.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

## `DAOHelpTicket.list_by_workspace`

### HLP-LW-01 — returns a list of the workspace's tickets
- **Rules:** `list_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(ids(result)) == {A.id, B.id}`.
3. returns: `isinstance(result[0], HelpTicket)`.

### HLP-LW-02 — a newer ticket of another workspace is not returned
- **Rules:** `list_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.
3. newer(Z, 1).

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### HLP-LW-03 — status "closed" keeps the closed tickets only
- **Rules:** `list_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. C = ticket, `ticket_number "HELP-2026-002"`, but `status "closed"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status="closed")`.

**Then**
1. returns: `ids(result) == [C.id]`.

### HLP-LW-04 — status "" keeps none
- **Rules:** `list_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status="")`.

**Then**
1. returns: `result == []`.

### HLP-LW-05 — status "OPEN" in capitals keeps none
- **Rules:** `list_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status="OPEN")`.

**Then**
1. returns: `result == []`.

### HLP-LW-06 — created_by keeps that creator's tickets only
- **Rules:** `list_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`, but `created_by U2.id`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, created_by=U2.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### HLP-LW-07 — created_by=0 is a filter and keeps none
- **Rules:** `list_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, created_by=0)`.

**Then**
1. returns: `result == []`.

### HLP-LW-08 — status and created_by combine with AND
- **Rules:** `list_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`, but `status "closed"`.
3. C = ticket, `ticket_number "HELP-2026-003"`, but `created_by U2.id`.
4. D = ticket, `ticket_number "HELP-2026-004"`, but `status "closed"`, `created_by U2.id`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status="closed", created_by=U2.id)`.

**Then**
1. returns: `ids(result) == [D.id]`.

### HLP-LW-09 — with the defaults 101 tickets give 100
- **Rules:** `list_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets E1 … E101, built with `add_all` and flushed: Ek = ticket, `ticket_number` = `f"HELP-2026-{k:03d}"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### HLP-LW-10 — limit=1000 gives all 101
- **Rules:** `list_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets E1 … E101, built with `add_all` and flushed: Ek = ticket, `ticket_number` = `f"HELP-2026-{k:03d}"`.
2. `all_ids` = the set of the ids of E1 … E101.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == all_ids`.

### HLP-LW-11 — limit=0 returns an empty list
- **Rules:** `list_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### HLP-LW-12 — skip past the end returns an empty list
- **Rules:** `list_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `result == []`.

### HLP-LW-13 — a negative limit raises DataError
- **Rules:** `list_by_workspace` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `dao.list_by_workspace(db, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### HLP-LW-14 — a negative skip raises DataError
- **Rules:** `list_by_workspace` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `dao.list_by_workspace(db, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### HLP-LW-15 — newest first, whatever the ids
- **Rules:** `list_by_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. C = ticket, `ticket_number "HELP-2026-003"`.
4. newer(B, 2).
5. newer(C, 1).

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### HLP-LW-16 — on a tie both tickets sit between the newer and the older one
- **Rules:** `list_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. C = ticket, `ticket_number "HELP-2026-003"`.
4. D = ticket, `ticket_number "HELP-2026-004"`.
5. newer(C, 1).
6. newer(D, -1).

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `set(ids(result)[1:3]) == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### HLP-LW-17 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `list_by_workspace` R5 [BUG-1442]
- **Kind:** bug
- **Expect:** xfail BUG-1442 (non-strict)
- **Fails today on:** Then 2 (no tie-break; the result rests on physical row order)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. C = ticket, `ticket_number "HELP-2026-003"`.
4. D = ticket, `ticket_number "HELP-2026-004"`.
5. newer(D, 1).
6. seqscan.
7. bumpT(A).

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### HLP-LW-18 — the query orders by created_at, then id, both descending
- **Rules:** `list_by_workspace` R5 [BUG-1442]
- **Kind:** bug
- **Expect:** xfail BUG-1442
- **Fails today on:** Then 3 (the query orders by `created_at` alone)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"created_at" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("created_at") < order_part.index(".id")`.
5. statement: `order_part.upper().count("DESC") == 2`.

### HLP-LW-19 — the status filter comes before the page: a newer closed ticket takes no place
- **Rules:** `list_by_workspace` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = ticket, `ticket_number "HELP-2026-001"`, but `status "closed"`.
2. A = ticket, `ticket_number "HELP-2026-002"`.
3. B = ticket, `ticket_number "HELP-2026-003"`.
4. newer(X, 3).
5. newer(A, 2).
6. newer(B, 1).

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status="open", skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### HLP-LW-20 — the creator filter comes before the page: a newer ticket of another creator takes no place
- **Rules:** `list_by_workspace` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = ticket, `ticket_number "HELP-2026-001"`, but `created_by U2.id`.
2. A = ticket, `ticket_number "HELP-2026-002"`.
3. B = ticket, `ticket_number "HELP-2026-003"`.
4. newer(X, 3).
5. newer(A, 2).
6. newer(B, 1).

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, created_by=U1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### HLP-LW-21 — each ticket's creator is loaded in the same query
- **Rules:** `list_by_workspace` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. `db.expire_all()`
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. returns: `"creator" not in sa_inspect(result[0]).unloaded`.
3. statement: `len(selects) == 1`.
4. statement: `"profiles" in sql`.

### HLP-LW-22 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed
- **Rules:** `list_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.
3. `B.title = "Edited"` (not flushed).
4. `P = HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-003", title="Printer jam", description="It jams", created_by=U1.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### HLP-LW-23 — _ in the status is no wildcard
- **Rules:** `list_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `status "closed"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status="clos_d")`.

**Then**
1. returns: `result == []`.

### HLP-LW-24 — a leading space in the status keeps none
- **Rules:** `list_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `status "closed"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status=" closed")`.

**Then**
1. returns: `result == []`.

### HLP-LW-25 — a stored status with a leading space is not kept
- **Rules:** `list_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `status " closed"`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id, status="closed")`.

**Then**
1. returns: `result == []`.

### HLP-LW-26 — asked for W2, only the W2 ticket is returned, though the W1 ticket is earlier
- **Rules:** `list_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = dao.list_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

### HLP-LW-27 — on a tie the id decides, not the title
- **Rules:** `list_by_workspace` R5 [BUG-1442]
- **Kind:** bug
- **Expect:** xfail BUG-1442 (non-strict)
- **Fails today on:** Then 1 (no tie-break; the result rests on physical row order)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `title "Alpha"`.
2. B = ticket, `ticket_number "HELP-2026-002"`, but `title "Bravo"`.
3. C = ticket, `ticket_number "HELP-2026-003"`, but `title "Charlie"`.
4. D = ticket, `ticket_number "HELP-2026-004"`, but `title "Delta"`.
5. newer(D, 1).
6. seqscan.
7. bumpT(A).

**When**
- `result = dao.list_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

## `DAOHelpTicket.list_platform`

### HLP-LP-01 — every workspace's tickets come back as (ticket, workspace name, creator name)
- **Rules:** `list_platform` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`, `created_by U2.id`.

**When**
- `result = dao.list_platform(db, search=TAG)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(own(result)) == {A.id, Z.id}`.
3. returns: `[tuple(r[1:]) for r in result if r[0].id == A.id] == [(f"Gamma {TAG}", "Rahim")]`.
4. returns: `[tuple(r[1:]) for r in result if r[0].id == Z.id] == [(f"Delta {TAG}", "Karim")]`.

### HLP-LP-02 — a ticket without a creator has creator name None
- **Rules:** `list_platform` Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `created_by None`.

**When**
- `result = dao.list_platform(db, search=TAG)`.

**Then**
1. returns: `own(result) == [A.id]`.
2. returns: `result[0][2] is None`.

### HLP-LP-03 — status keeps exactly that status
- **Rules:** `list_platform` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. C = ticket, `ticket_number "HELP-2026-002"`, but `status "closed"`.

**When**
- `result = dao.list_platform(db, status="closed", search=TAG)`.

**Then**
1. returns: `own(result) == [C.id]`.

### HLP-LP-04 — search None applies no filter
- **Rules:** `list_platform` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`, `title "Leak"`.

**When**
- `result = dao.list_platform(db, search=None, limit=1000)`.

**Then**
1. returns: `set(own(result)) == {A.id, Z.id}`.

### HLP-LP-05 — search "" applies no filter
- **Rules:** `list_platform` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`, `title "Leak"`.

**When**
- `result = dao.list_platform(db, search="", limit=1000)`.

**Then**
1. returns: `set(own(result)) == {A.id, Z.id}`.

### HLP-LP-06 — the middle of a workspace name, in capitals, finds that workspace's tickets
- **Rules:** `list_platform` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.

**When**
- `result = dao.list_platform(db, search=f"MMA {TAG.upper()}")`.

**Then**
1. returns: `own(result) == [A.id]`.

### HLP-LP-07 — the middle of a title, padded with spaces and in capitals, finds it
- **Rules:** `list_platform` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `title f"Printer jam {TAG}"`.
2. Z = ticket, `ticket_number "HELP-2026-002"`, but `title f"Leak {TAG}"`.

**When**
- `result = dao.list_platform(db, search=f"  NTER JAM {TAG.upper()}  ")`.

**Then**
1. returns: `own(result) == [A.id]`.

### HLP-LP-08 — a lowercase part of a ticket number finds it
- **Rules:** `list_platform` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number f"HELP-2026-{TAG.upper()}"`.
2. Z = ticket, `ticket_number "HELP-2026-002"`.

**When**
- `result = dao.list_platform(db, search=f"elp-2026-{TAG.lower()}")`.

**Then**
1. returns: `own(result) == [A.id]`.

### HLP-LP-09 — the middle of a description finds it
- **Rules:** `list_platform` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `description f"It jams {TAG} daily"`.
2. Z = ticket, `ticket_number "HELP-2026-002"`, but `description "Drips"`.

**When**
- `result = dao.list_platform(db, search=f"JAMS {TAG.upper()} DA")`.

**Then**
1. returns: `own(result) == [A.id]`.

### HLP-LP-10 — a search of only spaces matches every ticket
- **Rules:** `list_platform` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`, `title "Leak"`.

**When**
- `result = dao.list_platform(db, search="   ", limit=1000)`.

**Then**
1. returns: `set(own(result)) == {A.id, Z.id}`.

### HLP-LP-11 — _ in the search matches only a real _
- **Rules:** `list_platform` R6 [BUG-1443]
- **Kind:** bug
- **Expect:** xfail BUG-1443
- **Fails today on:** Then 2 (`_` is a wildcard: "axb" matches too)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `title f"a_b {TAG}"`.
2. Z = ticket, `ticket_number "HELP-2026-002"`, but `title f"axb {TAG}"`.

**When**
- `result = dao.list_platform(db, search=f"a_b {TAG}")`.

**Then**
1. returns: `A.id in own(result)`.
2. returns: `own(result) == [A.id]`.

### HLP-LP-12 — % in the search matches only a real %
- **Rules:** `list_platform` R6 [BUG-1443]
- **Kind:** bug
- **Expect:** xfail BUG-1443
- **Fails today on:** Then 2 (`%` is a wildcard: "50 x" matches too)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `title f"50% {TAG}"`.
2. Z = ticket, `ticket_number "HELP-2026-002"`, but `title f"50 x {TAG}"`.

**When**
- `result = dao.list_platform(db, search=f"50% {TAG}")`.

**Then**
1. returns: `A.id in own(result)`.
2. returns: `own(result) == [A.id]`.

### HLP-LP-13 — a backslash in the search matches only a real backslash
- **Rules:** `list_platform` R6 [BUG-1443]
- **Kind:** bug
- **Expect:** xfail BUG-1443
- **Fails today on:** Then 1 (the backslash escapes the next letter: "ab" matches, "a\b" does not)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `title f"a\\b {TAG}"` (one real backslash).
2. Z = ticket, `ticket_number "HELP-2026-002"`, but `title f"ab {TAG}"`.

**When**
- `result = dao.list_platform(db, search=f"a\\b {TAG}")`.

**Then**
1. returns: `own(result) == [A.id]`.

### HLP-LP-14 — with the defaults 101 matching tickets give 100
- **Rules:** `list_platform` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets E1 … E101, built with `add_all` and flushed: Ek = ticket, `ticket_number` = `f"HELP-2026-{k:03d}"`.

**When**
- `result = dao.list_platform(db, search=TAG)`.

**Then**
1. returns: `len(result) == 100`.

### HLP-LP-15 — limit=1000 gives all 101
- **Rules:** `list_platform` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 tickets E1 … E101, built with `add_all` and flushed: Ek = ticket, `ticket_number` = `f"HELP-2026-{k:03d}"`.

**When**
- `result = dao.list_platform(db, search=TAG, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### HLP-LP-16 — limit=0 returns an empty list
- **Rules:** `list_platform` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.list_platform(db, search=TAG, limit=0)`.

**Then**
1. returns: `result == []`.

### HLP-LP-17 — a negative limit raises DataError
- **Rules:** `list_platform` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `dao.list_platform(db, search=TAG, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### HLP-LP-18 — a negative skip raises DataError
- **Rules:** `list_platform` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `dao.list_platform(db, search=TAG, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### HLP-LP-19 — newest first, whatever the ids
- **Rules:** `list_platform` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. C = ticket, `ticket_number "HELP-2026-003"`.
4. newer(B, 2).
5. newer(C, 1).

**When**
- `result = dao.list_platform(db, search=TAG)`.

**Then**
1. returns: `tids(result) == [B.id, C.id, A.id]`.

### HLP-LP-20 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `list_platform` R5 [BUG-1442]
- **Kind:** bug
- **Expect:** xfail BUG-1442 (non-strict)
- **Fails today on:** Then 2 (no tie-break; the result rests on physical row order)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. C = ticket, `ticket_number "HELP-2026-003"`.
4. D = ticket, `ticket_number "HELP-2026-004"`.
5. newer(D, 1).
6. seqscan.
7. bumpT(A).

**When**
- `result = dao.list_platform(db, search=TAG)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `tids(result) == [D.id, C.id, B.id, A.id]`.

### HLP-LP-21 — the query orders by created_at, then id, both descending
- **Rules:** `list_platform` R5 [BUG-1442]
- **Kind:** bug
- **Expect:** xfail BUG-1442
- **Fails today on:** Then 3 (the query orders by `created_at` alone)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_platform(db, search=TAG)`.

**Then**
1. returns: `tids(result) == [A.id]`.
2. statement: `"created_at" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("created_at") < order_part.index(".id")`.
5. statement: `order_part.upper().count("DESC") == 2`.

### HLP-LP-22 — the status filter comes before the page: a newer closed ticket takes no place
- **Rules:** `list_platform` R2, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = ticket, `ticket_number "HELP-2026-001"`, but `status "closed"`.
2. A = ticket, `ticket_number "HELP-2026-002"`.
3. B = ticket, `ticket_number "HELP-2026-003"`.
4. newer(X, 3).
5. newer(A, 2).
6. newer(B, 1).

**When**
- `result = dao.list_platform(db, status="open", search=TAG, skip=1, limit=1)`.

**Then**
1. returns: `tids(result) == [B.id]`.

### HLP-LP-23 — the search comes before the page: a newer ticket of another workspace takes no place
- **Rules:** `list_platform` R3, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`.
2. A = ticket, `ticket_number "HELP-2026-002"`.
3. B = ticket, `ticket_number "HELP-2026-003"`.
4. newer(X, 3).
5. newer(A, 2).
6. newer(B, 1).

**When**
- `result = dao.list_platform(db, search=f"Gamma {TAG}", skip=1, limit=1)`.

**Then**
1. returns: `tids(result) == [B.id]`.

### HLP-LP-24 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed
- **Rules:** `list_platform` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-002"`.
3. `B.title = "Edited"` (not flushed).
4. `P = HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-003", title="Printer jam", description="It jams", created_by=U1.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_platform(db, search=f"Gamma {TAG}")`.

**Then**
1. returns: `set(tids(result)) == {A.id, B.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### HLP-LP-25 — status "" is a filter and keeps none
- **Rules:** `list_platform` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.list_platform(db, status="", search=TAG)`.

**Then**
1. returns: `own(result) == []`.

### HLP-LP-26 — on a tie the id decides, not the title
- **Rules:** `list_platform` R5 [BUG-1442]
- **Kind:** bug
- **Expect:** xfail BUG-1442 (non-strict)
- **Fails today on:** Then 1 (no tie-break; the result rests on physical row order)

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `title "Alpha"`.
2. B = ticket, `ticket_number "HELP-2026-002"`, but `title "Bravo"`.
3. C = ticket, `ticket_number "HELP-2026-003"`, but `title "Charlie"`.
4. D = ticket, `ticket_number "HELP-2026-004"`, but `title "Delta"`.
5. newer(D, 1).
6. seqscan.
7. bumpT(A).

**When**
- `result = dao.list_platform(db, search=TAG)`.

**Then**
1. returns: `tids(result) == [D.id, C.id, B.id, A.id]`.

## `DAOHelpTicket.get_platform_by_id`

### HLP-GP-01 — returns (ticket, workspace name, creator name)
- **Rules:** `get_platform_by_id` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_platform_by_id(db, ticket_id=A.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0].id == A.id`.
3. returns: `result[1] == f"Gamma {TAG}"`.
4. returns: `result[2] == "Rahim"`.

### HLP-GP-02 — a ticket of another workspace is returned
- **Rules:** `get_platform_by_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = ticket, `ticket_number "HELP-2026-001"`, but `workspace_id W2.id`, `created_by U2.id`.

**When**
- `result = dao.get_platform_by_id(db, ticket_id=Z.id)`.

**Then**
1. returns: `result[0].id == Z.id`.
2. returns: `result[1] == f"Delta {TAG}"`.
3. returns: `result[2] == "Karim"`.

### HLP-GP-03 — a ticket without a creator has creator name None
- **Rules:** `get_platform_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`, but `created_by None`.

**When**
- `result = dao.get_platform_by_id(db, ticket_id=A.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. returns: `result[2] is None`.

### HLP-GP-04 — an unknown id returns None
- **Rules:** `get_platform_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_platform_by_id(db, ticket_id=MISSING)`.

**Then**
1. returns: `result is None`.

### HLP-GP-05 — id 0 returns None
- **Rules:** `get_platform_by_id` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.

**When**
- `result = dao.get_platform_by_id(db, ticket_id=0)`.

**Then**
1. returns: `result is None`.

### HLP-GP-06 — writes nothing: a pending ticket stays pending, an unflushed edit stays unflushed
- **Rules:** `get_platform_by_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = ticket, `ticket_number "HELP-2026-001"`.
2. B = ticket, `ticket_number "HELP-2026-003"`.
3. `B.title = "Edited"` (not flushed).
4. `P = HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-002", title="Printer jam", description="It jams", created_by=U1.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_platform_by_id(db, ticket_id=A.id)`.

**Then**
1. returns: `result[0].id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_with_user` R3 [BUG-1440] — two concurrent creates both succeed with distinct numbers | Integration test with two connections (`HelpTicketManager.create_ticket`) | The spec: not unit-testable. The single-connection outcome is R4 (HLP-CW-04). |
| Spec FU-1 (a) — HR-1: `title`, `description`, `category` accept `"   "` and are not trimmed | `app/schemas/help_ticket.py` (`HelpTicketCreate`, `HelpTicketUpdate`) | Schema rule; the DAO stores what it gets (HLP-CW-07). |
| Spec FU-1 (b) — closing an already closed ticket rewrites `closed_at` / `closed_by` | `HelpTicketManager.update_ticket` | Inherited `update`. |
| Spec FU-1 (c) — who may call the unscoped platform reads | `app/api/v1/endpoints/platform_help.py` | Endpoint check. |
| HR-7 — `GET /help-tickets/` and the platform list require `skip >= 0`, `1 <= limit <= 200` | the two list endpoints | The DAO's negatives are HLP-LW-13, LW-14, LP-17, LP-18. |
| FU of BUG-1441 — `app.dao.help_ticket` does not import `utcnow` today | the fix | HLP-CW-03 patches it with `create=True`. |
| Inherited `BaseDAO` methods (`update` ← `update_ticket`, others no caller) | `tests/unit/dao/base.cases.md` | Not overridden. |
| Module singleton `help_ticket_dao` | none (no logic) | Entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `list_platform` Returns, `get_platform_by_id` R1 | Which profile column is the "creator name". | Cards assume the name given to `make_profile(name=…)` ("Rahim", "Karim"). |
| 2 | `list_platform` R6 | The `Today` note names `_` and `%` only; what an unescaped `\` does today is not stated. | HLP-LP-13 puts a letter after the backslash, so today it matches "ab" and not "a\b": the card fails today on Then 1. |
| 3 | Notes ("compare only the test's own ticket ids") | Committed tickets of other runs may exist; a list with no search could push the test's tickets past a page. | HLP-LP-04, LP-05, LP-10 use `limit=1000`; every other platform card searches for TAG. |
| 4 | `create_with_user` R1 | `updated_at` equal to `created_at` is not stated as a database default fact for the insert. | HLP-CW-01 checks both against `now()`, from the model facts table. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `generate_ticket_number` | Returns | HLP-GN-01 |
| `generate_ticket_number` | R1 | HLP-GN-01, HLP-GN-02, HLP-GN-03, HLP-GN-09 |
| `generate_ticket_number` | R2 | HLP-GN-04, HLP-GN-05, HLP-GN-06, HLP-GN-11 |
| `generate_ticket_number` | R3 | HLP-GN-07, HLP-GN-08 |
| `generate_ticket_number` | Side effects | HLP-GN-10 |
| `create_with_user` | Returns | HLP-CW-01 |
| `create_with_user` | R1 | HLP-CW-01, HLP-CW-02, HLP-CW-08 |
| `create_with_user` | R2 [BUG-1441] | HLP-CW-03 |
| `create_with_user` | R3 [BUG-1440] | Deferred |
| `create_with_user` | R4 | HLP-CW-04 |
| `create_with_user` | R5 | HLP-CW-05, HLP-CW-06, HLP-CW-07 |
| `create_with_user` | Errors | HLP-CW-04, HLP-CW-05, HLP-CW-06 |
| `create_with_user` | Side effects | HLP-CW-01, HLP-CW-08 |
| `get_by_id` | Returns | HLP-GB-01 |
| `get_by_id` | R1 | HLP-GB-01, HLP-GB-02, HLP-GB-03, HLP-GB-04, HLP-GB-06 |
| `get_by_id` | Side effects | HLP-GB-05 |
| `get_by_id_and_workspace` | Returns | HLP-GW-01 |
| `get_by_id_and_workspace` | R1 | HLP-GW-01, HLP-GW-02, HLP-GW-03, HLP-GW-04, HLP-GW-05, HLP-GW-06 |
| `get_by_id_and_workspace` | R2 | HLP-GW-01, HLP-GW-07 |
| `get_by_id_and_workspace` | Side effects | HLP-GW-08 |
| `list_by_workspace` | Returns | HLP-LW-01 |
| `list_by_workspace` | R1 | HLP-LW-01, HLP-LW-02, HLP-LW-26 |
| `list_by_workspace` | R2 | HLP-LW-03, HLP-LW-04, HLP-LW-05, HLP-LW-19, HLP-LW-23, HLP-LW-24, HLP-LW-25 |
| `list_by_workspace` | R3 | HLP-LW-06, HLP-LW-07, HLP-LW-08, HLP-LW-20 |
| `list_by_workspace` | R4 | HLP-LW-09, HLP-LW-10, HLP-LW-11, HLP-LW-12, HLP-LW-13, HLP-LW-14 |
| `list_by_workspace` | R5 | HLP-LW-15, HLP-LW-16, HLP-LW-19, HLP-LW-20 |
| `list_by_workspace` | R5 [BUG-1442] | HLP-LW-17, HLP-LW-18, HLP-LW-27 |
| `list_by_workspace` | R6 | HLP-LW-21 |
| `list_by_workspace` | Errors | HLP-LW-13, HLP-LW-14 |
| `list_by_workspace` | Side effects | HLP-LW-22 |
| `list_platform` | Returns | HLP-LP-01, HLP-LP-02 |
| `list_platform` | R1 | HLP-LP-01 |
| `list_platform` | R2 | HLP-LP-03, HLP-LP-22, HLP-LP-25 |
| `list_platform` | R3 | HLP-LP-04, HLP-LP-05, HLP-LP-06, HLP-LP-07, HLP-LP-08, HLP-LP-09, HLP-LP-23 |
| `list_platform` | R4 | HLP-LP-10 |
| `list_platform` | R5 | HLP-LP-14, HLP-LP-15, HLP-LP-16, HLP-LP-17, HLP-LP-18, HLP-LP-19, HLP-LP-22, HLP-LP-23 |
| `list_platform` | R5 [BUG-1442] | HLP-LP-20, HLP-LP-21, HLP-LP-26 |
| `list_platform` | R6 [BUG-1443] | HLP-LP-11, HLP-LP-12, HLP-LP-13 |
| `list_platform` | Errors | HLP-LP-17, HLP-LP-18 |
| `list_platform` | Side effects | HLP-LP-24 |
| `get_platform_by_id` | Returns | HLP-GP-01 |
| `get_platform_by_id` | R1 | HLP-GP-01, HLP-GP-02, HLP-GP-03, HLP-GP-04, HLP-GP-05 |
| `get_platform_by_id` | Side effects | HLP-GP-06 |
