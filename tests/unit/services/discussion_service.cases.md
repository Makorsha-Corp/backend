# Test cases — `app/services/discussion_service.py`

> **Spec:** `tests/unit/services/discussion_service.spec.md` (source commit e48a092)
> **Status:** READY — the spec is APPROVED; OQ-5 (and Q2 under it) answered by the owner 2026-11-04 (BUG-1867, BUG-1868, BUG-1879).
> **Revision:** 2 (2026-11-04) — spec Gap log G1: a private project is `visibility = "invited_only"`. Changed: DSS-L-15, DSS-C-28 (Given `visibility "invited_only"`, was `"private"`); no other card used it. Still pending OQ-5. No card added or retired.
> **Revision:** 3 (2026-11-04) — from `discussion_service.verify.md`: R-DS-2 → new DSS-C-30 (pass split of C-11: a parent of another workspace writes nothing, no commit, no rollback); R-DS-3 → new DSS-C-31 (pass split of C-14: a parent on another record type); R-DS-4 → new DSS-L-17 (`limit=51` of 52 roots gives 51); R-DS-5 → new DSS-C-32 (two distinct active members both notified). Conventions: `mid` is read after any `loaded:` line (R-DS-1 itself is the executor's). No card changed or retired.
> **Revision:** 4 (2026-11-04) — the owner answered OQ-5 (spec revision note). Rewritten as refused callers, strict xfail: DSS-L-15 (`list` R5, BUG-1867), L-16 (R5a, BUG-1868), C-28 (`create` R11, BUG-1867), C-29 (R11a, BUG-1868) — intended 404 `Record not found`, nothing written. New `list` cards (all strict xfail: they pass `user_id`): L-18 … L-22 (private project: creator, workspace owner, role owner, role ground-team-manager, invited), L-23 (workspace project open), L-24 … L-27 (help ticket: creator, ground-team-manager, owner role, platform admin), L-28 … L-30 (R5b component), L-31 (R5c purchase order). New `create` cards: pass C-33 … C-37 (private project allowed callers), C-38 … C-41 (help ticket allowed callers), C-43, C-44 (R11b), C-45 (R11c), C-56 (R9a workspace project, both notified); xfail C-42 (R11b refused), C-46 … C-49 (step 1b: invitations to other projects, lower and higher id; role owner in W2; owner of W2; other tickets created, lower and higher id), C-50 (R2: visibility before parent), C-51 (suspended privileged member), C-52 … C-55 (R9a, BUG-1879). Conventions: `user_id=` on `list`; person / admin / owner / private project / component / invite builders; notes per recipient. The spec's `create` Errors table gained the visibility row as row 2, so older cards' "Errors row 2 … 5" are renumbered 3 … 6 (no card's content changed). No card retired.
> **Revision:** 5 (2026-11-04) — from `discussion_service.verify.md` round 3 and the spec's dated note (help-ticket Facts (2)): R-DS-6 → new DSS-C-57 (a platform admin cannot post on a private project, xfail BUG-1867) and its `list` twin DSS-L-32 (xfail BUG-1867); suspended members → new DSS-L-33 and C-58 (a suspended member with role owner is refused on a help ticket, xfail BUG-1868) and DSS-C-59 (a suspended creator posts on their ticket, pass). No card changed or retired.
> **Counts:** 97 cases · 41 expected-to-pass · 56 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `_extract_mentions` 5 (1 bug) · `list` 33 (25 bug) · `create` 59 (31 bug).
- **Depth:** lighter target (skill step 1a): comments and mention notifications; no stock, money or order state. One card per rule and Errors row, one per table shape for the record check (project with `is_deleted`, item with `is_active`, purchase order without soft delete, another workspace's id), one per paging rule, one commit spy per path of D1–D4.
- **OQ-5 answered (BUG-1867, BUG-1868, BUG-1879):** one refused caller per record kind (private project, its component, help ticket) on `list` and `create`, and one card per allowed kind (workspace owner, role owner, role ground-team-manager, creator, invited; for tickets creator, owner / ground-team-manager role, platform admin). `create` takes `user_id` today, so its allowed-caller cards pass now; every `list` card that passes `user_id` (allowed callers included, L-15 … L-31) is strict xfail until the fix adds the parameter. Step 1b: id filters with the other row on both sides (C-46, C-49), privileges in another workspace (C-47, C-48), a real suspended privileged member (C-51; on tickets L-33, C-58) and a suspended creator still allowed (C-59), a platform admin refused on a private project (L-32, C-57), no rollback on the refusal (C-28, C-29, C-42 keep the uncommitted extra message), mentions asserted per recipient (C-52 … C-56).
- **Expected-to-fail:** BUG-1694 7, BUG-1686 6, BUG-1687 4, BUG-1534 1, BUG-1536 1, pass-through BUG-1535 1, BUG-1438 1 (non-strict), BUG-1439 1 (non-strict), BUG-1490 1 (strict SQL recorder), BUG-1867 20, BUG-1868 9, BUG-1879 4.
- **Notable design choices:**
  - Every passing card posts on or lists a **real W1 record** (P1, a purchase order, a live item), so it keeps passing once BUG-1686's record check exists.
  - BUG-1694 split: DSS-C-16 … C-18 (pass) check what holds today and after the fix for each refusal branch — nothing written, no commit, **no rollback** (an uncommitted extra message must still be there, D2); they accept today's `TypeError` or the fixed class. The xfail cards C-09 … C-15 check the class, status and exact text.
  - DSS-C-14 (parent on another `entity_type`) stores the parent row with `entity_type "machine"` and `entity_id P1.id` directly, so the posted record P1 is real and only the type differs.
  - D3 is asserted directly: after an unknown author's `IntegrityError` and after a failing commit, the service's `rollback` is never called.
- **Needs a decision:** None.

## Conventions for this module

**IDs.** `DSS` = `app/services/discussion_service.py`. `X` _extract_mentions · `L` list · `C` create.

**Actors and fixed values.**
- `svc` = the singleton `discussion_service`; `_extract_mentions` the module function (`from app.services.discussion_service import DiscussionService, discussion_service, _extract_mentions`). `db` = the test's real session, always the first argument. `list` is called **positionally**: `svc.list(db, workspace_id, entity_type, entity_id)` plus `skip=`, `limit=` by keyword when a card gives them, and `user_id=` by keyword when a card gives it (that parameter does not exist today: every card passing it is strict xfail on BUG-1867 / BUG-1868; the other `list` cards keep today's call and gain `user_id=UA.id` with the fix, nothing else); `create` by keyword. `result` = what the When call returns; for `list`, **items** = `result[0]`, **total** = `result[1]`. **mid** = `result.id`, read right after a `create` When but **after** any `loaded:` line of the card (reading `result.id` reloads an expired object).
- `Discussion` (`app.models.discussion`), `Notification` (`app.models.notification`), `WorkspaceMember` (`app.models.workspace_member`), `Project` (`app.models.project`), `Factory` (`app.models.factory`), `Item` (`app.models.item`), `Status` (`app.models.status`), `PurchaseOrder` (`app.models.purchase_order`), `HelpTicket` (`app.models.help_ticket`), `ProjectComponent` (`app.models.project_component`), `ProjectMember` (`app.models.project_member`), `ET` = `DiscussionEntityType` (`app.models.enums`), `DiscussionCreate` (`app.schemas.discussion`). `NotFoundError`, `AppValidationError` = `NotFoundError`, `ValidationError` of `app.core.exceptions` (not pydantic's). `IntegrityError`, `DataError`, `DBAPIError`, `PendingRollbackError` (`sqlalchemy.exc`); `inspect`, `text`, `select` (`sqlalchemy`); `patch` (`unittest.mock`).
- MISSING = `999999999`. **bn(n)** = `"".join(chr(0x09E6 + int(c)) for c in str(n))`.

**Externals.** None is mocked.

**Standing rows.** In every test, no Given line needed, in this order: W1, W2 = `make_workspace(db)`. Profiles `make_profile(db, name=…)`: UA `"Ann"`, UB `"Bob"`, US `"Sue"`, UO `"Otto"`. Memberships `WorkspaceMember(workspace_id=…, user_id=…, role="member", status=…)`: UA, UB `"active"` in W1; US `"suspended"` in W1; UO `"active"` in W2. F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`; F9 = the same, but `workspace_id W2.id`, `name "Factory Nine"`, `abbreviation "F9"`. P1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project One", description="Main")`; P9 = the same, but `workspace_id W2.id`, `factory_id F9.id`, `name "Project Nine"`. No discussion or notification exists unless a Given line builds it.

**Given rows.** Built directly (never through `svc`), flushed one at a time in the order written, ids rising in that order. A Given line written as code is a step to run exactly.
- **msg** = `Discussion(workspace_id=W1.id, entity_type="project", entity_id=P1.id, user_id=UA.id, message="Hello")`; after "but" every column that differs. **reply on R** = msg, but `parent_id R.id`.
- **project** = `Project(workspace_id=W1.id, factory_id=F1.id, description="Main")`; the card gives `name` and any other column. **item** = `Item(workspace_id=W1.id, name="Bolt M8", name_normalized="bolt m8", unit="pcs", is_active=True)`. **stage** = `Status(workspace_id=W1.id, name="Draft", comment="A note")`. **purchase on S** = `PurchaseOrder(workspace_id=W1.id, po_number="PO-1", destination_type="storage", destination_id=1, subtotal=0, total_amount=0, current_status_id=S.id, created_by=UA.id)`. **ticket** = `HelpTicket(workspace_id=W1.id, ticket_number="HELP-2026-001", title="Printer jam", description="It jams", created_by=UA.id)`.
- **person N as R** = `make_profile(db, name=N)`, then `WorkspaceMember(workspace_id=W1.id, user_id=<that profile>.id, role=R, status="active")`. UA, UB (role `"member"`) are neither owner, ground-team-manager, creator nor invited unless a card says so. **admin PA** = `make_profile(db, name="Pat")`, then `PA.is_platform_admin = True` and `db.flush()`; PA has no membership anywhere. **W1 owner is U** = `W1.owner_user_id = U.id`, then `db.flush()`.
- **private project** = project, but `visibility "invited_only"`, `created_by UA.id`; the card gives `name`. **component of P** = `ProjectComponent(workspace_id=W1.id, project_id=P.id, name="Frame")`. **invite U to P** = `ProjectMember(workspace_id=W1.id, project_id=P.id, user_id=U.id)`.
- **older(X, h)** = `db.execute(text("UPDATE discussions SET created_at = now() - make_interval(hours => :h) WHERE id = :i"), {"h": h, "i": X.id})`, then `db.expire_all()`. **bumpD(X)** = `db.execute(text("UPDATE discussions SET message = message || '!' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`. **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.
- **commit point** = after the last Given line the test runs `db.commit()` (a savepoint release under the `db` fixture). A Given line marked "(after the commit point)" runs after it, is flushed, and stays uncommitted. **XM** in a card is always the extra message: msg, but `message "Extra"` (after the commit point).

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id. **ids(x)** = `sorted(r.id for r in x)`; **order(x)** = `[r.id for r in x]`; **reply_ids(r)** = `[x.id for x in r.replies]`.
- **notes(M)** = a fresh SELECT of `notifications` with `source_type == "discussion"` and `source_id == M` ("notes(M) with `recipient_user_id == U.id`" adds that filter); **recipients(M)** = `sorted(n.recipient_user_id for n in notes(M))`.
- **nothing written** = the numbers of `discussions` rows and of `notifications` rows (all workspaces) equal their values at the commit point (two counts, one line each).
- `count:` lines count with a fresh query, with the filter stated.
- `loaded:` lines run on the returned object first: each column named is not in `inspect(result).unloaded`.
- `committed:` lines: before the first one the test runs `db.rollback()` once; each line then re-reads or counts with a fresh query.
- `session:` lines check `db` itself: "aborted" = `db.execute(text("SELECT 1"))` raises `DBAPIError`; "inactive" = `db.execute(text("SELECT 1"))` raises `PendingRollbackError` (each wrapped in `pytest.raises`).
- `raises: <Type>` (or a tuple of types): plain `with pytest.raises(<Type>) as exc:` around the call, **no** savepoint. Further `raises:` lines assert on `exc.value` after the block.
- **spies** = `with patch.object(db, "commit", wraps=db.commit) as cm, patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When (inside any `raises:` wrap). **failing commit** = `with pytest.raises(RuntimeError) as exc:` around `with patch.object(db, "commit", side_effect=RuntimeError("boom")), patch.object(db, "rollback", wraps=db.rollback) as rb:` around the When.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `selects` = the text of every recorded `SELECT`. A `statement:` line is a check on these.

**xfail cards.** Write the call and checks as shown. Strict unless the Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Race simulations.** None in this module.

## `_extract_mentions`

### DSS-X-01 — every token gives its id, in order, duplicates kept
- **Rules:** `_extract_mentions` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No row is needed.

**When**
- `result = _extract_mentions("hi @[5] and @[12] @[5]")`.

**Then**
1. returns: `result == [5, 12, 5]`.

### DSS-X-02 — a message without a token gives an empty list
- **Rules:** `_extract_mentions` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row is needed.

**When**
- `result = _extract_mentions("hello @Bob [5]")`.

**Then**
1. returns: `result == []`.

### DSS-X-03 — malformed tokens give nothing
- **Rules:** `_extract_mentions` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row is needed.

**When**
- `result = _extract_mentions("@[] @[a1] @5 @[ 5] @[-5]")`.

**Then**
1. returns: `result == []`.

### DSS-X-04 — leading zeros are read as the number
- **Rules:** `_extract_mentions` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No row is needed.

**When**
- `result = _extract_mentions("ping @[007]")`.

**Then**
1. returns: `result == [7]`.

### DSS-X-05 — Bengali and Arabic-Indic digits make no token
- **Rules:** `_extract_mentions` R2 [BUG-1536]
- **Kind:** bug
- **Expect:** xfail BUG-1536
- **Fails today on:** Then 1 (both are read as 12)

**Given**
1. No row is needed.

**When**
- `result = _extract_mentions("hi @[১২] and @[١٢]")`.

**Then**
1. returns: `result == []`.

## `DiscussionService.list`

### DSS-L-01 — the record's top-level messages of the workspace, with the count, defaults skip 0 and limit 50
- **Rules:** `list` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. R1 = msg.
2. Q1 = reply on R1.
3. O1 = msg, but `entity_id MISSING`.
4. O2 = msg, but `entity_type "machine"`.
5. O3 = msg, but `workspace_id W2.id`.
6. R2 = msg, but `message "Second"`.

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id)`.

**Then**
1. returns: `isinstance(result, tuple)`.
2. returns: `ids(items) == [R1.id, R2.id]`.
3. returns: `total == 2`.

### DSS-L-02 — with the default limit, 51 roots give 50 and the full count
- **Rules:** `list` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 51 messages, by `add_all`: k = 0 … 50, msg, but `message f"m{k:02d}"`.

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id)`.

**Then**
1. returns: `len(items) == 50`.
2. returns: `total == 51`.

### DSS-L-03 — skip and limit are passed on: skip=1 with limit=1000
- **Rules:** `list` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R1 = msg.
2. R2 = msg, but `message "Second"`.

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id, skip=1, limit=1000)`.

**Then**
1. returns: `len(items) == 1`.
2. returns: `total == 2`.

### DSS-L-17 — limit is passed on unchanged: limit=51 of 52 roots gives 51
- **Rules:** `list` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 52 messages, by `add_all`: k = 0 … 51, msg, but `message f"m{k:02d}"`.

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id, limit=51)`.

**Then**
1. returns: `len(items) == 51`.
2. returns: `total == 52`.

### DSS-L-04 — a negative limit raises DataError and leaves the session aborted
- **Rules:** `list` R4, Errors; D4
- **Kind:** error
- **Expect:** pass

**Given**
1. R1 = msg.

**When**
- `svc.list(db, W1.id, ET("project"), P1.id, skip=0, limit=-1)`.

**Then**
1. raises: `DataError`.
2. session: aborted.

### DSS-L-05 — the list neither commits nor rolls back
- **Rules:** `list` R4; D4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. R1 = msg.
2. XM.
3. `R1.message = "Edited"` (after the commit point, not flushed).

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id)`, with **spies**.

**Then**
1. returns: `XM.id in [r.id for r in items]`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. session: `R1 in db.dirty`.
5. committed: `discussions` rows with `message == "Extra"`: exactly 0.

### DSS-L-06 — the thread of a purchase order (no soft delete) is listed
- **Rules:** `list` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = stage.
2. O = purchase on S.
3. M = msg, but `entity_type "purchase_order"`, `entity_id O.id`.

**When**
- `result = svc.list(db, W1.id, ET("purchase_order"), O.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-07 — the thread of a live item is listed
- **Rules:** `list` R1, R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. I = item.
2. M = msg, but `entity_type "item"`, `entity_id I.id`.

**When**
- `result = svc.list(db, W1.id, ET("item"), I.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-08 — an unknown record is not found
- **Rules:** `list` R2 [BUG-1686], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1686
- **Fails today on:** Then 1 (no error: the thread stored under that id is listed)

**Given**
1. M = msg, but `entity_id MISSING`.

**When**
- `svc.list(db, W1.id, ET("project"), MISSING)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-09 — another workspace's record is not found
- **Rules:** `list` R2 [BUG-1686], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1686
- **Fails today on:** Then 1 (no error: the thread stored under that id is listed)

**Given**
1. M = msg, but `entity_id P9.id`.

**When**
- `svc.list(db, W1.id, ET("project"), P9.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-10 — a soft-deleted project is not found
- **Rules:** `list` R3 [BUG-1687], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1687
- **Fails today on:** Then 1 (no error: its thread is listed)

**Given**
1. PD = project, `name "Old Project"`, `is_deleted True`.
2. M = msg, but `entity_id PD.id`.

**When**
- `svc.list(db, W1.id, ET("project"), PD.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-11 — an inactive item is not found
- **Rules:** `list` R3 [BUG-1687], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1687
- **Fails today on:** Then 1 (no error: its thread is listed)

**Given**
1. ID = item, but `is_active False`.
2. M = msg, but `entity_type "item"`, `entity_id ID.id`.

**When**
- `svc.list(db, W1.id, ET("item"), ID.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-12 — pass-through BUG-1438: roots oldest first, then by id, also after an update
- **Rules:** `list` R1 [BUG-1438]
- **Kind:** bug
- **Expect:** xfail BUG-1438 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (roots of one time come back in physical order; the updated R1 comes last)

**Given**
1. R1 = msg.
2. R2 = msg, but `message "Second"`.
3. R3 = msg, but `message "Third"`.
4. older(R3, 1).
5. seqscan.
6. bumpD(R1).

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id)`.

**Then**
1. returns: `ids(items) == [R1.id, R2.id, R3.id]`.
2. returns: `order(items) == [R3.id, R1.id, R2.id]`.

### DSS-L-13 — pass-through BUG-1439: replies come oldest first, then by id
- **Rules:** `list` R1 [BUG-1439]
- **Kind:** bug
- **Expect:** xfail BUG-1439 (non-strict)
- **Author:** claude
- **Fails today on:** Then 2 (replies have no order; the updated A comes last)

**Given**
1. R = msg.
2. A = reply on R.
3. B = reply on R, but `message "Two"`.
4. C = reply on R, but `message "Three"`.
5. seqscan.
6. bumpD(A).

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id)`.

**Then**
1. returns: `sorted(reply_ids(items[0])) == [A.id, B.id, C.id]`.
2. returns: `reply_ids(items[0]) == [A.id, B.id, C.id]`.

### DSS-L-14 — pass-through BUG-1490: the replies are loaded with the page
- **Rules:** `list` R1 [BUG-1490]
- **Kind:** bug
- **Expect:** xfail BUG-1490
- **Fails today on:** Then 2 (no replies query is sent during the call; they load lazily later)

**Given**
1. R = msg.
2. A = reply on R.
3. `db.expire_all()`.
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id)`.

**Then**
1. returns: `ids(items) == [R.id]`.
2. statement: `any("parent_id IN" in s for s in selects)`.

### DSS-L-15 — a plain member gets 404 for a private project's thread
- **Rules:** `list` R5 [BUG-1867], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. PP = private project, `name "Secret Project"`.
2. M = msg, but `entity_id PP.id`.

**When**
- `svc.list(db, W1.id, ET("project"), PP.id, user_id=UB.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-16 — a plain member gets 404 for a help ticket they did not create
- **Rules:** `list` R5a [BUG-1868], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. T = ticket.
2. M = msg, but `entity_type "support_ticket"`, `entity_id T.id`.

**When**
- `svc.list(db, W1.id, ET("support_ticket"), T.id, user_id=UB.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-18 — the creator of a private project gets its thread
- **Rules:** `list` R5 [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. PP = private project, `name "Secret Project"`.
2. M = msg, but `entity_id PP.id`.

**When**
- `result = svc.list(db, W1.id, ET("project"), PP.id, user_id=UA.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-19 — the workspace owner gets a private project's thread
- **Rules:** `list` R5 [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UW = person "Wes" as "member".
2. W1 owner is UW.
3. PP = private project, `name "Secret Project"`.
4. M = msg, but `entity_id PP.id`.

**When**
- `result = svc.list(db, W1.id, ET("project"), PP.id, user_id=UW.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-20 — a member with role owner gets a private project's thread
- **Rules:** `list` R5 [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UR = person "Ron" as "owner".
2. PP = private project, `name "Secret Project"`.
3. M = msg, but `entity_id PP.id`.

**When**
- `result = svc.list(db, W1.id, ET("project"), PP.id, user_id=UR.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-21 — a member with role ground-team-manager gets a private project's thread
- **Rules:** `list` R5 [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UM = person "Mia" as "ground-team-manager".
2. PP = private project, `name "Secret Project"`.
3. M = msg, but `entity_id PP.id`.

**When**
- `result = svc.list(db, W1.id, ET("project"), PP.id, user_id=UM.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-22 — a person invited to a private project gets its thread
- **Rules:** `list` R5 [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UP = person "Pia" as "member".
2. PP = private project, `name "Secret Project"`.
3. invite UP to PP.
4. M = msg, but `entity_id PP.id`.

**When**
- `result = svc.list(db, W1.id, ET("project"), PP.id, user_id=UP.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-23 — a workspace-visibility project's thread is open to every member
- **Rules:** `list` R5 [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. M = msg.

**When**
- `result = svc.list(db, W1.id, ET("project"), P1.id, user_id=UB.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-24 — the creator of a help ticket gets its thread
- **Rules:** `list` R5a [BUG-1868]
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. T = ticket, but `created_by UB.id`.
2. M = msg, but `entity_type "support_ticket"`, `entity_id T.id`.

**When**
- `result = svc.list(db, W1.id, ET("support_ticket"), T.id, user_id=UB.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-25 — a member with role ground-team-manager gets any help ticket's thread
- **Rules:** `list` R5a [BUG-1868]
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UM = person "Mia" as "ground-team-manager".
2. T = ticket.
3. M = msg, but `entity_type "support_ticket"`, `entity_id T.id`.

**When**
- `result = svc.list(db, W1.id, ET("support_ticket"), T.id, user_id=UM.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-26 — a member with role owner gets any help ticket's thread
- **Rules:** `list` R5a [BUG-1868]
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UR = person "Ron" as "owner".
2. T = ticket.
3. M = msg, but `entity_type "support_ticket"`, `entity_id T.id`.

**When**
- `result = svc.list(db, W1.id, ET("support_ticket"), T.id, user_id=UR.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-27 — a platform admin with no membership gets any help ticket's thread
- **Rules:** `list` R5a [BUG-1868]
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. admin PA.
2. T = ticket.
3. M = msg, but `entity_type "support_ticket"`, `entity_id T.id`.

**When**
- `result = svc.list(db, W1.id, ET("support_ticket"), T.id, user_id=PA.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-28 — a component of a private project: a plain member gets 404
- **Rules:** `list` R5b [BUG-1867], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. PP = private project, `name "Secret Project"`.
2. C = component of PP.
3. M = msg, but `entity_type "project_component"`, `entity_id C.id`.

**When**
- `svc.list(db, W1.id, ET("project_component"), C.id, user_id=UB.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-29 — a component of a private project: a person invited to the project gets its thread
- **Rules:** `list` R5b [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UP = person "Pia" as "member".
2. PP = private project, `name "Secret Project"`.
3. invite UP to PP.
4. C = component of PP.
5. M = msg, but `entity_type "project_component"`, `entity_id C.id`.

**When**
- `result = svc.list(db, W1.id, ET("project_component"), C.id, user_id=UP.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-30 — a component of a workspace-visibility project is open to every member
- **Rules:** `list` R5b [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. C = component of P1.
2. M = msg, but `entity_type "project_component"`, `entity_id C.id`.

**When**
- `result = svc.list(db, W1.id, ET("project_component"), C.id, user_id=UB.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-31 — another record type (purchase order) keeps membership as its only check
- **Rules:** `list` R5c [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. S = stage.
2. O = purchase on S.
3. M = msg, but `entity_type "purchase_order"`, `entity_id O.id`.

**When**
- `result = svc.list(db, W1.id, ET("purchase_order"), O.id, user_id=UB.id)`.

**Then**
1. returns: `ids(items) == [M.id]`.
2. returns: `total == 1`.

### DSS-L-32 — a platform admin gets 404 for a private project's thread
- **Rules:** `list` R5 [BUG-1867], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. admin PA.
2. PP = private project, `name "Secret Project"`.
3. M = msg, but `entity_id PP.id`.

**When**
- `svc.list(db, W1.id, ET("project"), PP.id, user_id=PA.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

### DSS-L-33 — a suspended member with role owner gets 404 for a help ticket they did not create
- **Rules:** `list` R5a [BUG-1868], Errors
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (the call raises TypeError: `list` has no `user_id` parameter yet)

**Given**
1. UQ = `make_profile(db, name="Quinn")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=UQ.id, role="owner", status="suspended")`.
3. T = ticket.
4. M = msg, but `entity_type "support_ticket"`, `entity_id T.id`.

**When**
- `svc.list(db, W1.id, ET("support_ticket"), T.id, user_id=UQ.id)`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.

## `DiscussionService.create`

### DSS-C-01 — a top-level message is stored, committed once and returned re-read; no token, no notification
- **Rules:** `create` R1, R10, Returns; D1
- **Kind:** happy
- **Expect:** pass

**Given**
1. W1 has no discussions.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Hello there"))`, with **spies**.

**Then**
1. loaded: `id`, `created_at`, `message`.
2. returns: `isinstance(result, Discussion)`, `result.parent_id is None`.
3. mock called: `cm.call_count == 1`.
4. mock called: `rb.call_count == 0`.
5. committed: re-read the row `mid`: `workspace_id == W1.id`, `entity_type == "project"`, `entity_id == P1.id`.
6. committed: re-read the row `mid`: `user_id == UA.id`, `message == "Hello there"`, `parent_id is None`.
7. committed: `notifications` rows of W1: exactly 0.

### DSS-C-02 — the message is stored as typed, spaces kept
- **Rules:** `create` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has no discussions.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="  Hello  "))`.

**Then**
1. returns: `result.message == "  Hello  "`.
2. committed: re-read the row `mid`: `message == "  Hello  "`.

### DSS-C-03 — a reply to a top-level message of the same record is stored with its parent
- **Rules:** `create` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. R = msg.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Agreed", parent_id=R.id))`.

**Then**
1. returns: `result.parent_id == R.id`.
2. committed: re-read the row `mid`: `parent_id == R.id`, `user_id == UB.id`, `entity_id == P1.id`.

### DSS-C-04 — a mentioned member gets one notification, committed with the message
- **Rules:** `create` R9; D1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no discussions.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"Thanks @[{UB.id}] for this"))`.

**Then**
1. returns: `result.message == f"Thanks @[{UB.id}] for this"`.
2. committed: `discussions` rows with `id == mid`: exactly 1.
3. committed: notes(mid) has exactly 1 row.
4. committed: that row: `workspace_id == W1.id`, `recipient_user_id == UB.id`, `actor_user_id == UA.id`, `notification_type == "mention"`.
5. committed: that row: `entity_type == "project"`, `entity_id == P1.id`, `source_type == "discussion"`, `source_id == mid`.
6. committed: that row: `preview == "Thanks @Bob for this"`, `is_read is False`.

### DSS-C-05 — each active member once; a suspended member and an unknown id are skipped, and the preview names them as today
- **Rules:** `create` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. W1 has no discussions.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"@[{UB.id}] @[{UB.id}] @[{US.id}] @[{MISSING}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `recipients(mid) == [UB.id]`.
3. committed: notes(mid)[0]: `preview == "@Bob @Bob @Sue @User 999999999"`.

### DSS-C-06 — a member of another workspace only gets no notification
- **Rules:** `create` R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. W1 has no discussions.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"see @[{UO.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: notes(mid) has exactly 0 rows.

### DSS-C-07 — pass-through BUG-1535: the author is not notified of their own mention
- **Rules:** `create` R9 [BUG-1535]
- **Kind:** bug
- **Expect:** xfail BUG-1535
- **Fails today on:** Then 2 (the author UA is notified too)

**Given**
1. W1 has no discussions.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"@[{UA.id}] and @[{UB.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `recipients(mid) == [UB.id]`.

### DSS-C-08 — the preview names only members of the caller's workspace
- **Rules:** `create` R9 [BUG-1534]
- **Kind:** bug
- **Expect:** xfail BUG-1534
- **Fails today on:** Then 3 (the preview reads `@Bob @Otto`)

**Given**
1. W1 has no discussions.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"@[{UB.id}] @[{UO.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `recipients(mid) == [UB.id]`.
3. committed: notes(mid)[0]: `preview == f"@Bob @User {UO.id}"`.

### DSS-C-09 — parent id 0 is not found
- **Rules:** `create` R5 [BUG-1694], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1694
- **Fails today on:** Then 1 (the call raises TypeError: `APIException` is built without `error_type` and `title`)

**Given**
1. R = msg.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Reply", parent_id=0))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Parent discussion not found"`.

### DSS-C-10 — an unknown parent id is not found
- **Rules:** `create` R5 [BUG-1694], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1694
- **Fails today on:** Then 1 (the call raises TypeError: `APIException` is built without `error_type` and `title`)

**Given**
1. R = msg.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Reply", parent_id=MISSING))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Parent discussion not found"`.

### DSS-C-11 — a parent of another workspace is not found
- **Rules:** `create` R5 [BUG-1694], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-1694
- **Fails today on:** Then 1 (the call raises TypeError: `APIException` is built without `error_type` and `title`)

**Given**
1. RZ = msg, but `workspace_id W2.id`.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Reply", parent_id=RZ.id))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Parent discussion not found"`.

### DSS-C-12 — a reply to a reply is refused: one level only
- **Rules:** `create` R6 [BUG-1694], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1694
- **Fails today on:** Then 1 (the call raises TypeError: `APIException` is built without `error_type` and `title`)

**Given**
1. R = msg.
2. Q = reply on R.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Deeper", parent_id=Q.id))`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.error_type == "validation_error"`.
4. raises: `exc.value.detail == "Replies can only be one level deep"`.

### DSS-C-13 — a reply on another record id is refused
- **Rules:** `create` R7 [BUG-1694], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-1694
- **Fails today on:** Then 1 (the call raises TypeError: `APIException` is built without `error_type` and `title`)

**Given**
1. P2 = project, `name "Project Two"`.
2. R = msg.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P2.id, message="Wrong place", parent_id=R.id))`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Reply must be on the same entity as the parent"`.

### DSS-C-14 — a reply on another record type with the same id is refused
- **Rules:** `create` R7 [BUG-1694], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-1694
- **Fails today on:** Then 1 (the call raises TypeError: `APIException` is built without `error_type` and `title`)

**Given**
1. R = msg, but `entity_type "machine"`.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Wrong type", parent_id=R.id))`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Reply must be on the same entity as the parent"`.

### DSS-C-15 — depth is checked before the record: a reply on another record's reply gets the depth message
- **Rules:** `create` R6, R7 [BUG-1694], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-1694
- **Fails today on:** Then 1 (the call raises TypeError: `APIException` is built without `error_type` and `title`)

**Given**
1. P2 = project, `name "Project Two"`.
2. R = msg, but `entity_id P2.id`.
3. Q = reply on R, but `entity_id P2.id`.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Deeper", parent_id=Q.id))`.

**Then**
1. raises: `AppValidationError`.
2. raises: `exc.value.detail == "Replies can only be one level deep"`.

### DSS-C-16 — a missing parent writes nothing, does not commit, and does not roll back other changes
- **Rules:** `create` R5, R12; D2
- **Kind:** error
- **Expect:** pass

**Given**
1. R = msg.
2. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Reply", parent_id=0))`, with **spies**, inside `raises: (TypeError, NotFoundError)` (today's `TypeError` or the fixed class).

**Then**
1. raises: `isinstance(exc.value, (TypeError, NotFoundError))`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `discussions` rows with `message == "Extra"`: exactly 1.
5. count: `discussions` rows with `message == "Reply"`: exactly 0.
6. count: `notifications` rows of W1: exactly 0.

### DSS-C-17 — a reply to a reply writes nothing, does not commit, and does not roll back other changes
- **Rules:** `create` R6, R12; D2
- **Kind:** error
- **Expect:** pass

**Given**
1. R = msg.
2. Q = reply on R.
3. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Deeper", parent_id=Q.id))`, with **spies**, inside `raises: (TypeError, AppValidationError)` (today's `TypeError` or the fixed class).

**Then**
1. raises: `isinstance(exc.value, (TypeError, AppValidationError))`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `discussions` rows with `message == "Extra"`: exactly 1.
5. count: `discussions` rows with `message == "Deeper"`: exactly 0.

### DSS-C-18 — a reply on another record writes nothing, does not commit, and does not roll back other changes
- **Rules:** `create` R7, R12; D2
- **Kind:** error
- **Expect:** pass

**Given**
1. P2 = project, `name "Project Two"`.
2. R = msg.
3. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P2.id, message="Wrong place", parent_id=R.id))`, with **spies**, inside `raises: (TypeError, AppValidationError)` (today's `TypeError` or the fixed class).

**Then**
1. raises: `isinstance(exc.value, (TypeError, AppValidationError))`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `discussions` rows with `message == "Extra"`: exactly 1.
5. count: `discussions` rows with `message == "Wrong place"`: exactly 0.

### DSS-C-19 — a message on an unknown record is refused
- **Rules:** `create` R3 [BUG-1686], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1686
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. W1 has no discussions.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=MISSING, message="Ghost"))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. count: `discussions` rows with `message == "Ghost"`: exactly 0.

### DSS-C-20 — a message on another workspace's record is refused
- **Rules:** `create` R3 [BUG-1686], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1686
- **Fails today on:** Then 1 (no error: the message is stored under W1)

**Given**
1. W1 has no discussions.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P9.id, message="Ghost"))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. count: `discussions` rows with `message == "Ghost"`: exactly 0.

### DSS-C-21 — a message on a soft-deleted project is refused
- **Rules:** `create` R4 [BUG-1687], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1687
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. PD = project, `name "Old Project"`, `is_deleted True`.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PD.id, message="Ghost"))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. count: `discussions` rows with `message == "Ghost"`: exactly 0.

### DSS-C-22 — a message on an inactive item is refused
- **Rules:** `create` R4 [BUG-1687], Errors row 1
- **Kind:** bug
- **Expect:** xfail BUG-1687
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. ID = item, but `is_active False`.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("item"), entity_id=ID.id, message="Ghost"))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. count: `discussions` rows with `message == "Ghost"`: exactly 0.

### DSS-C-23 — the record is checked before the parent
- **Rules:** `create` R2, R3 [BUG-1686]
- **Kind:** bug
- **Expect:** xfail BUG-1686
- **Fails today on:** Then 1 (the call raises TypeError: the parent check runs and builds `APIException` wrongly)

**Given**
1. W1 has no discussions.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=MISSING, message="Ghost", parent_id=0))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Record not found"`.

### DSS-C-24 — a record refusal does not commit and leaves other changes pending
- **Rules:** `create` R3, R12 [BUG-1686]; D2
- **Kind:** bug
- **Expect:** xfail BUG-1686
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. R = msg.
2. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=MISSING, message="Ghost"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-25 — a message on a purchase order (no soft delete) is stored
- **Rules:** `create` R1, R3, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = stage.
2. O = purchase on S.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("purchase_order"), entity_id=O.id, message="Arrived"))`.

**Then**
1. returns: `result.entity_type == "purchase_order"`, `result.entity_id == O.id`.
2. committed: re-read the row `mid`: `entity_type == "purchase_order"`, `entity_id == O.id`, `workspace_id == W1.id`.

### DSS-C-26 — an unknown author: the database error reaches the caller and the service does not roll back
- **Rules:** `create` R12, Errors row 6; D3
- **Kind:** error
- **Expect:** pass

**Given**
1. R = msg.
2. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=MISSING, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Orphan"))`, with **spies**, inside `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. mock called: `rb.call_count == 0`.
4. mock called: `cm.call_count == 0`.
5. session: inactive.
6. committed: `discussions` rows with `message == "Orphan"`: exactly 0.
7. committed: `discussions` rows with `message == "Extra"`: exactly 0.

### DSS-C-27 — a failing commit reaches the caller; the service does not roll back; nothing is saved
- **Rules:** `create` R12; D3
- **Kind:** error
- **Expect:** pass

**Given**
1. W1 has no discussions.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"Lost @[{UB.id}]"))`, inside **failing commit**.

**Then**
1. raises: `str(exc.value) == "boom"`.
2. mock called: `rb.call_count == 0`.
3. committed: `discussions` rows of W1: exactly 0.
4. committed: `notifications` rows of W1: exactly 0.

### DSS-C-28 — a plain member cannot post on a private project's thread: 404, nothing written, other changes kept
- **Rules:** `create` R11, R12 [BUG-1867], Errors row 2; D2
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. PP = private project, `name "Secret Project"`.
2. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-29 — a plain member cannot post on a help ticket they did not create: 404, nothing written, other changes kept
- **Rules:** `create` R11a, R12 [BUG-1868], Errors row 2; D2
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. T = ticket.
2. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-30 — a parent of another workspace: nothing written, no commit, no rollback of other changes
- **Rules:** `create` R5, R12; D2
- **Kind:** error
- **Expect:** pass

**Given**
1. RZ = msg, but `workspace_id W2.id`.
2. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Reply", parent_id=RZ.id))`, with **spies**, inside `raises: (TypeError, NotFoundError)` (today's `TypeError` or the fixed class).

**Then**
1. raises: `isinstance(exc.value, (TypeError, NotFoundError))`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `discussions` rows with `message == "Extra"`: exactly 1.
5. count: `discussions` rows with `message == "Reply"`: exactly 0.

### DSS-C-31 — a parent on another record type with the same id: nothing written, no commit, no rollback of other changes
- **Rules:** `create` R7, R12; D2
- **Kind:** error
- **Expect:** pass

**Given**
1. R = msg, but `entity_type "machine"`.
2. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message="Wrong type", parent_id=R.id))`, with **spies**, inside `raises: (TypeError, AppValidationError)` (today's `TypeError` or the fixed class).

**Then**
1. raises: `isinstance(exc.value, (TypeError, AppValidationError))`.
2. mock called: `cm.call_count == 0`.
3. mock called: `rb.call_count == 0`.
4. count: `discussions` rows with `message == "Extra"`: exactly 1.
5. count: `discussions` rows with `message == "Wrong type"`: exactly 0.

### DSS-C-32 — two distinct active members mentioned are both notified; a suspended one is not
- **Rules:** `create` R9
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. UC = `make_profile(db, name="Cid")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=UC.id, role="member", status="active")`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"@[{US.id}] @[{UB.id}] @[{UC.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `recipients(mid) == sorted([UB.id, UC.id])`.

### DSS-C-33 — the creator posts on a private project's thread
- **Rules:** `create` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. PP = private project, `name "Secret Project"`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UA.id`, `result.entity_id == PP.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-34 — the workspace owner posts on a private project's thread
- **Rules:** `create` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. UW = person "Wes" as "member".
2. W1 owner is UW.
3. PP = private project, `name "Secret Project"`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UW.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UW.id`, `result.entity_id == PP.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-35 — a member with role owner posts on a private project's thread
- **Rules:** `create` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. UR = person "Ron" as "owner".
2. PP = private project, `name "Secret Project"`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UR.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UR.id`, `result.entity_id == PP.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-36 — a member with role ground-team-manager posts on a private project's thread
- **Rules:** `create` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. UM = person "Mia" as "ground-team-manager".
2. PP = private project, `name "Secret Project"`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UM.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UM.id`, `result.entity_id == PP.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-37 — a person invited to a private project posts on its thread
- **Rules:** `create` R11
- **Kind:** happy
- **Expect:** pass

**Given**
1. UP = person "Pia" as "member".
2. PP = private project, `name "Secret Project"`.
3. invite UP to PP.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UP.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UP.id`, `result.entity_id == PP.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-38 — the creator of a help ticket posts on its thread
- **Rules:** `create` R11a
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = ticket, but `created_by UB.id`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UB.id`, `result.entity_id == T.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-39 — a member with role ground-team-manager posts on any help ticket
- **Rules:** `create` R11a
- **Kind:** happy
- **Expect:** pass

**Given**
1. UM = person "Mia" as "ground-team-manager".
2. T = ticket.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UM.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UM.id`, `result.entity_id == T.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-40 — a member with role owner posts on any help ticket
- **Rules:** `create` R11a
- **Kind:** happy
- **Expect:** pass

**Given**
1. UR = person "Ron" as "owner".
2. T = ticket.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UR.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UR.id`, `result.entity_id == T.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-41 — a platform admin with no membership posts on any help ticket
- **Rules:** `create` R11a
- **Kind:** happy
- **Expect:** pass

**Given**
1. admin PA.
2. T = ticket.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=PA.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == PA.id`, `result.entity_id == T.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-42 — a component of a private project: a plain member cannot post
- **Rules:** `create` R11b, R12 [BUG-1867], Errors row 2; D2
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. PP = private project, `name "Secret Project"`.
2. C = component of PP.
3. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project_component"), entity_id=C.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-43 — a component of a private project: a person invited to the project posts
- **Rules:** `create` R11b
- **Kind:** happy
- **Expect:** pass

**Given**
1. UP = person "Pia" as "member".
2. PP = private project, `name "Secret Project"`.
3. invite UP to PP.
4. C = component of PP.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UP.id, data=DiscussionCreate(entity_type=ET("project_component"), entity_id=C.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UP.id`, `result.entity_id == C.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-44 — a component of a workspace-visibility project: every member posts
- **Rules:** `create` R11b
- **Kind:** happy
- **Expect:** pass

**Given**
1. C = component of P1.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project_component"), entity_id=C.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UB.id`, `result.entity_id == C.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-45 — another record type (purchase order) keeps membership as its only check
- **Rules:** `create` R11c
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = stage.
2. O = purchase on S.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("purchase_order"), entity_id=O.id, message="Visible"))`.

**Then**
1. returns: `result.user_id == UB.id`, `result.entity_id == O.id`.
2. committed: `discussions` rows with `message == "Visible"`: exactly 1.

### DSS-C-46 — an invitation to other private projects (lower and higher id) does not open this one
- **Rules:** `create` R11 [BUG-1867], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. PA2 = private project, `name "Alpha Secret"`.
2. PP = private project, `name "Secret Project"`.
3. PZ3 = private project, `name "Zeta Secret"`.
4. invite UB to PA2.
5. invite UB to PZ3.
6. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-47 — role owner in another workspace does not open a private project here
- **Rules:** `create` R11 [BUG-1867], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. `WorkspaceMember(workspace_id=W2.id, user_id=UB.id, role="owner", status="active")`.
2. PP = private project, `name "Secret Project"`.
3. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-48 — owning another workspace does not open a private project here
- **Rules:** `create` R11 [BUG-1867], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. `W2.owner_user_id = UB.id`, then `db.flush()`.
2. PP = private project, `name "Secret Project"`.
3. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-49 — having created other help tickets (lower and higher id) does not open this one
- **Rules:** `create` R11a [BUG-1868], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. T1 = ticket, but `ticket_number "HELP-2026-002"`, `created_by UB.id`.
2. T = ticket.
3. T3 = ticket, but `ticket_number "HELP-2026-003"`, `created_by UB.id`.
4. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-50 — the visibility check runs before the parent check
- **Rules:** `create` R2, R11 [BUG-1867]
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (the call raises TypeError: the parent check runs and builds `APIException` wrongly)

**Given**
1. PP = private project, `name "Secret Project"`.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UB.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden", parent_id=0))`.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.detail == "Record not found"`.

### DSS-C-51 — a suspended member with role ground-team-manager cannot post on a private project
- **Rules:** `create` R11 [BUG-1867], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. UQ = `make_profile(db, name="Quinn")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=UQ.id, role="ground-team-manager", status="suspended")`.
3. PP = private project, `name "Secret Project"`.
4. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UQ.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-52 — a private project: only the mentioned person who may open it is notified
- **Rules:** `create` R9a [BUG-1879]
- **Kind:** bug
- **Expect:** xfail BUG-1879
- **Fails today on:** Then 4 (UB is notified too)

**Given**
1. UP = person "Pia" as "member".
2. PP = private project, `name "Secret Project"`.
3. invite UP to PP.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message=f"Heads up @[{UP.id}] @[{UB.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `discussions` rows with `id == mid`: exactly 1.
3. committed: notes(mid) with `recipient_user_id == UP.id`: exactly 1.
4. committed: notes(mid) with `recipient_user_id == UB.id`: exactly 0.

### DSS-C-53 — a component of a private project: only the mentioned person who may open the project is notified
- **Rules:** `create` R9a [BUG-1879]
- **Kind:** bug
- **Expect:** xfail BUG-1879
- **Fails today on:** Then 4 (UB is notified too)

**Given**
1. UP = person "Pia" as "member".
2. PP = private project, `name "Secret Project"`.
3. invite UP to PP.
4. C = component of PP.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project_component"), entity_id=C.id, message=f"Heads up @[{UP.id}] @[{UB.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `discussions` rows with `id == mid`: exactly 1.
3. committed: notes(mid) with `recipient_user_id == UP.id`: exactly 1.
4. committed: notes(mid) with `recipient_user_id == UB.id`: exactly 0.

### DSS-C-54 — a help ticket: only the mentioned person who may open it is notified
- **Rules:** `create` R9a [BUG-1879]
- **Kind:** bug
- **Expect:** xfail BUG-1879
- **Fails today on:** Then 4 (UB is notified too)

**Given**
1. UM = person "Mia" as "ground-team-manager".
2. T = ticket.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message=f"Heads up @[{UM.id}] @[{UB.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `discussions` rows with `id == mid`: exactly 1.
3. committed: notes(mid) with `recipient_user_id == UM.id`: exactly 1.
4. committed: notes(mid) with `recipient_user_id == UB.id`: exactly 0.

### DSS-C-55 — nobody mentioned may open the record: no notification, the message is stored
- **Rules:** `create` R9a [BUG-1879]
- **Kind:** bug
- **Expect:** xfail BUG-1879
- **Fails today on:** Then 3 (UB is notified)

**Given**
1. PP = private project, `name "Secret Project"`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message=f"Heads up @[{UB.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `discussions` rows with `id == mid`: exactly 1.
3. committed: notes(mid) with `recipient_user_id == UB.id`: exactly 0.
4. committed: notes(mid) has exactly 0 rows.

### DSS-C-56 — a workspace-visibility project: every mentioned active member is notified
- **Rules:** `create` R9, R9a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. UP = person "Pia" as "member".

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=P1.id, message=f"Heads up @[{UP.id}] @[{UB.id}]"))`.

**Then**
1. returns: `result.id == mid`.
2. committed: `discussions` rows with `id == mid`: exactly 1.
3. committed: notes(mid) with `recipient_user_id == UP.id`: exactly 1.
4. committed: notes(mid) with `recipient_user_id == UB.id`: exactly 1.

### DSS-C-57 — a platform admin cannot post on a private project: admins are allowed on tickets only
- **Rules:** `create` R11, R12 [BUG-1867], Errors row 2; D2
- **Kind:** bug
- **Expect:** xfail BUG-1867
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. admin PA.
2. PP = private project, `name "Secret Project"`.
3. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=PA.id, data=DiscussionCreate(entity_type=ET("project"), entity_id=PP.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-58 — a suspended member with role owner cannot post on a help ticket they did not create
- **Rules:** `create` R11a, R12 [BUG-1868], Errors row 2; D2
- **Kind:** bug
- **Expect:** xfail BUG-1868
- **Fails today on:** Then 1 (no error: the message is stored)

**Given**
1. UQ = `make_profile(db, name="Quinn")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=UQ.id, role="owner", status="suspended")`.
3. T = ticket.
4. XM.

**When**
- `svc.create(db, workspace_id=W1.id, user_id=UQ.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Hidden"))`, with **spies**.

**Then**
1. raises: `NotFoundError`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Record not found"`.
4. mock called: `cm.call_count == 0`.
5. mock called: `rb.call_count == 0`.
6. count: `discussions` rows with `message == "Hidden"`: exactly 0.
7. count: `discussions` rows with `message == "Extra"`: exactly 1.

### DSS-C-59 — the creator of a help ticket posts on it whatever their membership status
- **Rules:** `create` R11a
- **Kind:** happy
- **Expect:** pass

**Given**
1. UZ = `make_profile(db, name="Zed")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=UZ.id, role="member", status="suspended")`.
3. T = ticket, but `created_by UZ.id`.

**When**
- `result = svc.create(db, workspace_id=W1.id, user_id=UZ.id, data=DiscussionCreate(entity_type=ET("support_ticket"), entity_id=T.id, message="Still broken"))`.

**Then**
1. returns: `result.user_id == UZ.id`, `result.entity_id == T.id`.
2. committed: `discussions` rows with `message == "Still broken"`: exactly 1.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| RFC 7807 body of `NotFoundError` / `ValidationError` (BUG-1694, BUG-1686, BUG-1687) | `GET`, `POST /discussions/` (integration) | Status and body over HTTP. |
| `entity_type` parsing into `DiscussionEntityType`; `skip >= 0`, `1 <= limit <= 200` | endpoint | Endpoint bounds. |
| Blank message refused (`DiscussionCreate`, "Message cannot be empty"); 400 today, BUG-461 | schema / endpoint | Schema rule, not a rule of this service. |
| `DiscussionResponse` rendering of `author` and nested `replies` (BUG-1490) | endpoint (integration) | Rendering. |
| Who is notified (active members, dedupe, BUG-1535) and the preview text (BUG-1534, BUG-1536) | `tests/unit/services/notification_service.cases.md` | One pass-through card each here. |

## Spec gaps
None. Revision 1's gap 1 is closed by spec Gap log G1.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_extract_mentions` | R1 | DSS-X-01, DSS-X-02, DSS-X-03, DSS-X-04 |
| `_extract_mentions` | R2 [BUG-1536] | DSS-X-05 |
| `list` | R1 | DSS-L-01, DSS-L-02, DSS-L-03, DSS-L-06, DSS-L-07, DSS-L-17 |
| `list` | R1 [BUG-1438] | DSS-L-12 |
| `list` | R1 [BUG-1439] | DSS-L-13 |
| `list` | R1 [BUG-1490] | DSS-L-14 |
| `list` | R2 [BUG-1686] | DSS-L-08, DSS-L-09 |
| `list` | R3 | DSS-L-06, DSS-L-07 |
| `list` | R3 [BUG-1687] | DSS-L-10, DSS-L-11 |
| `list` | R4 | DSS-L-04, DSS-L-05 |
| `list` | R5 [BUG-1867] | DSS-L-15, DSS-L-18, DSS-L-19, DSS-L-20, DSS-L-21, DSS-L-22, DSS-L-23, DSS-L-32 |
| `list` | R5a [BUG-1868] | DSS-L-16, DSS-L-24, DSS-L-25, DSS-L-26, DSS-L-27, DSS-L-33 |
| `list` | R5b [BUG-1867] | DSS-L-28, DSS-L-29, DSS-L-30 |
| `list` | R5c | DSS-L-06, DSS-L-07 |
| `list` | R5c [BUG-1867] | DSS-L-31 |
| `list` | Errors | DSS-L-04, DSS-L-08, DSS-L-09, DSS-L-10, DSS-L-11 |
| `list` | Returns | DSS-L-01 |
| `create` | R1 | DSS-C-01, DSS-C-02, DSS-C-25 |
| `create` | R2 [BUG-1686] | DSS-C-23 |
| `create` | R3 | DSS-C-25 |
| `create` | R3 [BUG-1686] | DSS-C-19, DSS-C-20, DSS-C-24 |
| `create` | R4 | DSS-C-25 |
| `create` | R4 [BUG-1687] | DSS-C-21, DSS-C-22 |
| `create` | R5 | DSS-C-16, DSS-C-30 |
| `create` | R5 [BUG-1694] | DSS-C-09, DSS-C-10, DSS-C-11 |
| `create` | R6 | DSS-C-17 |
| `create` | R6 [BUG-1694] | DSS-C-12, DSS-C-15 |
| `create` | R7 | DSS-C-18, DSS-C-31 |
| `create` | R7 [BUG-1694] | DSS-C-13, DSS-C-14, DSS-C-15 |
| `create` | R8 | DSS-C-03 |
| `create` | R9 | DSS-C-04, DSS-C-05, DSS-C-06, DSS-C-32 |
| `create` | R9 [BUG-1534] | DSS-C-08 |
| `create` | R9 [BUG-1535] | DSS-C-07 |
| `create` | R10 | DSS-C-01 |
| `create` | R11 | DSS-C-03, DSS-C-33, DSS-C-34, DSS-C-35, DSS-C-36, DSS-C-37 |
| `create` | R11 [BUG-1867] | DSS-C-28, DSS-C-46, DSS-C-47, DSS-C-48, DSS-C-51, DSS-C-57 |
| `create` | R11a | DSS-C-38, DSS-C-39, DSS-C-40, DSS-C-41, DSS-C-59 |
| `create` | R11a [BUG-1868] | DSS-C-29, DSS-C-49, DSS-C-58 |
| `create` | R11b | DSS-C-43, DSS-C-44 |
| `create` | R11b [BUG-1867] | DSS-C-42 |
| `create` | R11c | DSS-C-25, DSS-C-45 |
| `create` | R9a | DSS-C-56 |
| `create` | R9a [BUG-1879] | DSS-C-52, DSS-C-53, DSS-C-54, DSS-C-55 |
| `create` | R2 [BUG-1867] | DSS-C-50 |
| `create` | Errors row 2 [BUG-1867] [BUG-1868] | DSS-C-28, DSS-C-29, DSS-C-42, DSS-C-46, DSS-C-47, DSS-C-48, DSS-C-49, DSS-C-51, DSS-C-57, DSS-C-58 |
| `create` | R12 | DSS-C-16, DSS-C-17, DSS-C-18, DSS-C-26, DSS-C-27, DSS-C-30, DSS-C-31 |
| `create` | Errors row 1 | DSS-C-19, DSS-C-20, DSS-C-21, DSS-C-22 |
| `create` | Errors row 3 | DSS-C-09, DSS-C-10, DSS-C-11 |
| `create` | Errors row 4 | DSS-C-12, DSS-C-15 |
| `create` | Errors row 5 | DSS-C-13, DSS-C-14 |
| `create` | Errors row 6 | DSS-C-26 |
| `create` | Returns | DSS-C-01 |
| Transaction rules | D1 | DSS-C-01, DSS-C-04 |
| Transaction rules | D2 | DSS-C-16, DSS-C-17, DSS-C-18, DSS-C-24, DSS-C-30, DSS-C-31; [BUG-1867] [BUG-1868] DSS-C-28, DSS-C-29, DSS-C-42, DSS-C-57, DSS-C-58 |
| Transaction rules | D3 | DSS-C-26, DSS-C-27 |
| Transaction rules | D4 | DSS-L-04, DSS-L-05 |
