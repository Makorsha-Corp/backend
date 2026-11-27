# Test cases — `app/dao/attachment_link.py`

> **Spec:** `tests/unit/dao/attachment_link.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1–P4 and Q1 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `attachment_link.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): R-1 → ALK-CN-12 … CN-16; R-2 → ALK-CN-17, GL-11; R-3 → ALK-GL-12; R-4 → ALK-GL-10 gains Then 7 (`FOR UPDATE`), its `nothing written:` line moves from 7 to 8. No other card changed; no ID retired. Ruling on ALK-GA-30: no change.
> **Counts:** 78 cases · 70 expected-to-pass · 8 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `AttachmentLinkCreateSchema` 5 · `get_attachments_for_entity` 32 (3 bug) · `count_linked_attachments_for_entity` 17 (1 bug) · `get_links_for_attachment` 12 (3 bug) · inherited `create` 12 (1 bug).
- **Depth:** lighter target (skill step 1a). Three filtered reads, a plain payload class and the inherited insert; no stock, money or order state.
- **Expected-to-fail:** BUG-1432 3: ALK-GA-28, GA-29 non-strict, GA-30 strict (the SQL recorder). BUG-1433 3: ALK-GL-07, GL-12 non-strict, GL-08 strict. BUG-1434 1, strict: ALK-CN-01; ALK-CN-02 is the passing companion (R1a). BUG-1431 1, strict: ALK-CR-02 (`Asia/Dhaka`); ALK-CR-03 is the `UTC` companion.
- **Commit spies:** inherited `create` 1 (ALK-CR-12). The three reads have none.
- **Notable design choices:**
  - Passing cards never compare an order resting on tied `uploaded_at`: rows of one transaction share it. Order cards use `age`, so stamps and ids do not rise together.
  - Exact compare of `entity_type`: capitals, a part, a leading space and `_` on the argument side, `_` and a leading space on the stored side, on the list; revision 1 gives the count its own set (ALK-CN-12 … CN-16), as it is a separate query.
  - The filter-before-paging cards put the hidden row newest, ahead of the skipped row, today and after the fix.
  - ALK-CR-02 compares `linked_at` with `now() AT TIME ZONE 'UTC'` within 5 minutes, not exactly (Spec gap 1).
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `ALK` = `app/dao/attachment_link.py`. `SC` AttachmentLinkCreateSchema · `GA` get_attachments_for_entity · `CN` count_linked_attachments_for_entity · `GL` get_links_for_attachment · `CR` inherited create.

**Actors and fixed values.**
- `dao` = the singleton `attachment_link_dao`; `Schema` = `AttachmentLinkCreateSchema` (both `from app.dao.attachment_link import …`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `Attachment` = `app.models.attachment.Attachment`. `AttachmentLink` = `app.models.attachment_link.AttachmentLink`. `IntegrityError`, `DataError` = `sqlalchemy.exc` classes. `text` = `sqlalchemy.text`. `timedelta` = the `datetime` module's class.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`); U1 = a `profiles` row (`make_profile`).
- **attachment** = `Attachment(workspace_id=W1.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=U1.id, upload_status="ready")`; after "but" the card lists every column that differs. **deleted** adds `is_deleted True`, `deleted_by U1.id`.
- **link on X** = `AttachmentLink(workspace_id=W1.id, attachment_id=X.id, entity_type="purchase_order", entity_id=501, linked_by=U1.id)`; after "but" the card lists every column that differs. No `purchase_order` row 501 exists, nor is one needed.
- Rows of one transaction share `uploaded_at`. **age(X, n)** = `db.execute(text("UPDATE attachments SET uploaded_at = now() - make_interval(days => :n) WHERE id = :i"), {"n": n, "i": X.id})`, then `db.expire_all()`.
- **bump(X)** = `db.execute(text("UPDATE attachments SET note = 'bumped' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`. **bumpL(L)** = `db.execute(text("UPDATE attachment_links SET linked_by = linked_by WHERE id = :i"), {"i": L.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A time-zone line of a Given is the first statement of the test body after the standing rows.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **links_of(X)** = `db.scalar(text("SELECT count(*) FROM attachment_links WHERE attachment_id = :i"), {"i": X.id})`.
- **nothing written** = the numbers of `attachments` and of `attachment_links` rows stored (all workspaces) equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` and `unchanged:` lines.
- `raises: E` (`IntegrityError` or `DataError`) = wrap the call: `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, after the `with` block, one `assert` per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` sent; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `AttachmentLinkCreateSchema`

### ALK-SC-01 — keywords are stored and model_dump gives exactly the five keys
- **Rules:** `AttachmentLinkCreateSchema` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `S = Schema(workspace_id=11, attachment_id=22, entity_type="project", entity_id=33, linked_by=44)`

**When**
- `result = S.model_dump()`.

**Then**
1. returns: `result == {"workspace_id": 11, "attachment_id": 22, "entity_type": "project", "entity_id": 33, "linked_by": 44}`.
2. returns: `S.entity_type == "project"`.

### ALK-SC-02 — nothing is validated: any value, None included, is stored
- **Rules:** `AttachmentLinkCreateSchema` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `S = Schema(workspace_id=None, attachment_id="abc", entity_type="", entity_id=-5, linked_by=None)`

**When**
- `result = S.model_dump()`.

**Then**
1. returns: `result == {"workspace_id": None, "attachment_id": "abc", "entity_type": "", "entity_id": -5, "linked_by": None}`.

### ALK-SC-03 — a positional call raises TypeError
- **Rules:** `AttachmentLinkCreateSchema` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `Schema(11, 22, "project", 33, 44)`, inside `with pytest.raises(TypeError):`.

**Then**
1. raises: `TypeError`.

### ALK-SC-04 — a missing argument raises TypeError
- **Rules:** `AttachmentLinkCreateSchema` R1, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `Schema(workspace_id=11, attachment_id=22, entity_type="project", entity_id=33)`, inside `with pytest.raises(TypeError):`.

**Then**
1. raises: `TypeError`.

### ALK-SC-05 — the object itself passed to create raises TypeError and adds nothing
- **Rules:** `AttachmentLinkCreateSchema` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.
2. `S = Schema(workspace_id=W1.id, attachment_id=A.id, entity_type="purchase_order", entity_id=501, linked_by=U1.id)`

**When**
- `dao.create(db, obj_in=S)`, inside `with pytest.raises(TypeError) as exc:`.

**Then**
1. raises: `"by_alias" in str(exc.value)`.
2. count: `links_of(A) == 0`.
3. pending: `len(db.new) == 0`.

## `AttachmentLinkDAO.get_attachments_for_entity`

### ALK-GA-01 — returns a list of the record's ready attachments
- **Rules:** `get_attachments_for_entity` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.
3. returns: `isinstance(result[0], Attachment)`.

### ALK-GA-02 — an attachment of another entity id is not returned
- **Rules:** `get_attachments_for_entity` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_id 502`.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-03 — an attachment of another entity type is not returned
- **Rules:** `get_attachments_for_entity` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_type "project"`.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-04 — the entity type in capitals matches nothing
- **Rules:** `get_attachments_for_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="PURCHASE_ORDER", entity_id=501)`.

**Then**
1. returns: `result == []`.

### ALK-GA-05 — a part of the entity type matches nothing
- **Rules:** `get_attachments_for_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase", entity_id=501)`.

**Then**
1. returns: `result == []`.

### ALK-GA-06 — a leading space in the argument matches nothing
- **Rules:** `get_attachments_for_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type=" purchase_order", entity_id=501)`.

**Then**
1. returns: `result == []`.

### ALK-GA-07 — _ in the argument is no wildcard: a stored "purchase-order" is not found
- **Rules:** `get_attachments_for_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_type "purchase-order"`.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-08 — a stored type with a leading space is not found
- **Rules:** `get_attachments_for_entity` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_type " purchase_order"`.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-09 — a W2 link to a W1 attachment is not followed for W1
- **Rules:** `get_attachments_for_entity` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `workspace_id W2.id`.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-10 — a W2 link to a W1 attachment returns that attachment for W2
- **Rules:** `get_attachments_for_entity` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `workspace_id W2.id`.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W2.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### ALK-GA-11 — a pending attachment is left out
- **Rules:** `get_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `upload_status "pending"`.
4. link on B.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-12 — a failed attachment is left out
- **Rules:** `get_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `upload_status "failed"`.
4. link on B.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-13 — a deleted ready attachment is left out
- **Rules:** `get_attachments_for_entity` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. D = attachment, deleted.
4. link on D.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `set(ids(result)) == {A.id}`.

### ALK-GA-14 — the status filter comes before the page: a newer pending row takes no place
- **Rules:** `get_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = attachment, but `upload_status "pending"`.
2. link on X.
3. A = attachment.
4. link on A.
5. age(A, 1).
6. B = attachment.
7. link on B.
8. age(B, 2).

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### ALK-GA-15 — the deleted filter comes before the page: a newer deleted row takes no place
- **Rules:** `get_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = attachment, deleted.
2. link on X.
3. A = attachment.
4. link on A.
5. age(A, 1).
6. B = attachment.
7. link on B.
8. age(B, 2).

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### ALK-GA-16 — an unknown entity id returns an empty list
- **Rules:** `get_attachments_for_entity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ALK-GA-17 — entity id 0 returns an empty list
- **Rules:** `get_attachments_for_entity` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=0)`.

**Then**
1. returns: `result == []`.

### ALK-GA-18 — with the defaults 101 ready attachments give 100
- **Rules:** `get_attachments_for_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 attachments E1 … E101, built with `add_all` and flushed: Ek = attachment, but `file_name` = `f"f{k}.png"`.
2. 101 links built with `add_all` and flushed: link on Ek for every k.
3. `all_ids` = the set of the ids of E1 … E101.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `set(ids(result)) <= all_ids`.

### ALK-GA-19 — limit=1000 gives all 101
- **Rules:** `get_attachments_for_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 attachments E1 … E101, built with `add_all` and flushed: Ek = attachment, but `file_name` = `f"f{k}.png"`.
2. 101 links built with `add_all` and flushed: link on Ek for every k.
3. `all_ids` = the set of the ids of E1 … E101.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `set(ids(result)) == all_ids`.

### ALK-GA-20 — limit=0 returns an empty list
- **Rules:** `get_attachments_for_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, limit=0)`.

**Then**
1. returns: `result == []`.

### ALK-GA-21 — limit=1 returns one row
- **Rules:** `get_attachments_for_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, limit=1)`.

**Then**
1. returns: `len(result) == 1`.

### ALK-GA-22 — skip past the end returns an empty list
- **Rules:** `get_attachments_for_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, skip=2)`.

**Then**
1. returns: `result == []`.

### ALK-GA-23 — skip at the last row returns it
- **Rules:** `get_attachments_for_entity` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B.
5. age(B, 1).

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### ALK-GA-24 — a negative limit raises DataError
- **Rules:** `get_attachments_for_entity` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. nothing written: nothing written.

### ALK-GA-25 — a negative skip raises DataError
- **Rules:** `get_attachments_for_entity` R5, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. nothing written: nothing written.

### ALK-GA-26 — newest first, whatever the ids
- **Rules:** `get_attachments_for_entity` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B.
5. age(B, 2).
6. C = attachment, but `file_name "c.png"`.
7. link on C.
8. age(C, 1).

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `ids(result) == [A.id, C.id, B.id]`.

### ALK-GA-27 — three sharing one time come first, the day-older one last
- **Rules:** `get_attachments_for_entity` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. D = attachment, but `file_name "d.png"`.
2. link on D.
3. age(D, 1).
4. A = attachment.
5. link on A.
6. B = attachment, but `file_name "b.png"`.
7. link on B.
8. C = attachment, but `file_name "c.png"`.
9. link on C.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `set(ids(result)[:3]) == {A.id, B.id, C.id}`.
3. returns: `result[3].id == D.id`.

### ALK-GA-28 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_attachments_for_entity` R6 [BUG-1432]
- **Kind:** bug
- **Expect:** xfail BUG-1432 (non-strict)
- **Fails today on:** Then 2 (no tie-break; the updated lowest id moves by physical order)

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B.
5. C = attachment, but `file_name "c.png"`.
6. link on C.
7. D = attachment, but `file_name "d.png"`.
8. link on D.
9. age(D, 1).
10. seqscan.
11. bump(A).

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [C.id, B.id, A.id, D.id]`.

### ALK-GA-29 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_attachments_for_entity` R6 [BUG-1432]
- **Kind:** bug
- **Expect:** xfail BUG-1432 (non-strict)
- **Fails today on:** Then 2 (no tie-break; pages follow physical order)

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B.
5. C = attachment, but `file_name "c.png"`.
6. link on C.
7. D = attachment, but `file_name "d.png"`.
8. link on D.
9. seqscan.
10. bump(A).

**When**
- `pages = [dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501, skip=k, limit=1) for k in range(4)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [D.id, C.id, B.id, A.id]`.

### ALK-GA-30 — the query orders by uploaded_at, then id, both descending
- **Rules:** `get_attachments_for_entity` R6 [BUG-1432]
- **Kind:** bug
- **Expect:** xfail BUG-1432
- **Fails today on:** Then 3 (the query orders by `uploaded_at` alone)

**Given**
1. A = attachment.
2. link on A.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"uploaded_at" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("uploaded_at") < order_part.index(".id")`.
5. statement: `order_part.upper().count("DESC") == 2`.

### ALK-GA-31 — the record itself is not looked at: a link to an id with no record is followed
- **Rules:** `get_attachments_for_entity` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A, but `entity_type "machine"`, `entity_id MISSING`.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="machine", entity_id=MISSING)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ALK-GA-32 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_attachments_for_entity` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. `B.note = "Edited"` (not flushed).
5. `P = Attachment(workspace_id=W1.id, file_name="p.png", mime_type="image/png", file_size=1, uploaded_by=U1.id, upload_status="ready")`
6. `db.add(P)` (not flushed).
7. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

## `AttachmentLinkDAO.count_linked_attachments_for_entity`

### ALK-CN-01 — failed attachments do not count; ready and pending do
- **Rules:** `count_linked_attachments_for_entity` R1 [BUG-1434], Returns
- **Kind:** bug
- **Expect:** xfail BUG-1434
- **Fails today on:** Then 2 (the failed one counts too: 3)

**Given**
1. R = attachment.
2. link on R.
3. P = attachment, but `upload_status "pending"`.
4. link on P.
5. F = attachment, but `upload_status "failed"`.
6. link on F.
7. D = attachment, deleted.
8. link on D.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 2`.

### ALK-CN-02 — a pending one counts, a deleted one never
- **Rules:** `count_linked_attachments_for_entity` R1a, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. R = attachment.
2. link on R.
3. P = attachment, but `upload_status "pending"`.
4. link on P.
5. D = attachment, deleted.
6. link on D.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `isinstance(result, int)`.
2. returns: `result == 2`.

### ALK-CN-03 — no cap: 101 ready attachments count 101
- **Rules:** `count_linked_attachments_for_entity` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 attachments E1 … E101, built with `add_all` and flushed: Ek = attachment, but `file_name` = `f"f{k}.png"`.
2. 101 links built with `add_all` and flushed: link on Ek for every k.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 101`.

### ALK-CN-04 — another entity id does not count
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_id 502`.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 1`.

### ALK-CN-05 — another entity type does not count
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_type "project"`.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 1`.

### ALK-CN-06 — the entity type in capitals counts nothing
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="PURCHASE_ORDER", entity_id=501)`.

**Then**
1. returns: `result == 0`.

### ALK-CN-07 — a W2 link to a W1 attachment does not count for W1
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `workspace_id W2.id`.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 1`.

### ALK-CN-08 — an unknown entity id counts 0
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=MISSING)`.

**Then**
1. returns: `result == 0`.

### ALK-CN-09 — entity id 0 counts 0
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=0)`.

**Then**
1. returns: `result == 0`.

### ALK-CN-10 — the record itself is not looked at: a link to an id with no record counts
- **Rules:** `count_linked_attachments_for_entity` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A, but `entity_type "machine"`, `entity_id MISSING`.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="machine", entity_id=MISSING)`.

**Then**
1. returns: `result == 1`.

### ALK-CN-11 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `count_linked_attachments_for_entity` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. `A.note = "Edited"` (not flushed).
4. `P = Attachment(workspace_id=W1.id, file_name="p.png", mime_type="image/png", file_size=1, uploaded_by=U1.id, upload_status="ready")`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 1`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### ALK-CN-12 — _ in the argument is no wildcard: a stored "purchase-order" does not count
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_type "purchase-order"`.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 1`.

### ALK-CN-13 — the start of the entity type counts nothing
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase", entity_id=501)`.

**Then**
1. returns: `result == 0`.

### ALK-CN-14 — the end of the entity type counts nothing
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="order", entity_id=501)`.

**Then**
1. returns: `result == 0`.

### ALK-CN-15 — a leading space in the argument counts nothing
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type=" purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 0`.

### ALK-CN-16 — a stored type with a leading space does not count
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `entity_type " purchase_order"`.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W1.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 1`.

### ALK-CN-17 — asked for W2, only the W2 link counts, though the W1 link is earlier
- **Rules:** `count_linked_attachments_for_entity` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.
3. B = attachment, but `file_name "b.png"`.
4. link on B, but `workspace_id W2.id`.

**When**
- `result = dao.count_linked_attachments_for_entity(db, workspace_id=W2.id, entity_type="purchase_order", entity_id=501)`.

**Then**
1. returns: `result == 1`.

## `AttachmentLinkDAO.get_links_for_attachment`

### ALK-GL-01 — returns every link of the attachment, whatever the entity type
- **Rules:** `get_links_for_attachment` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment.
2. L1 = link on A.
3. L2 = link on A, but `entity_type "project"`, `entity_id 7`.
4. L3 = link on A, but `entity_type "machine"`, `entity_id 9`.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(ids(result)) == {L1.id, L2.id, L3.id}`.
3. returns: `isinstance(result[0], AttachmentLink)`.

### ALK-GL-02 — no cap: 101 links give 101
- **Rules:** `get_links_for_attachment` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. 101 links built with `add_all` and flushed: link on A, but `entity_id` = `k` for k = 1 … 101.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `len(result) == 101`.

### ALK-GL-03 — an earlier link of another attachment is not returned
- **Rules:** `get_links_for_attachment` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = attachment, but `file_name "b.png"`.
2. LB = link on B.
3. A = attachment.
4. LA = link on A.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `ids(result) == [LA.id]`.

### ALK-GL-04 — a link of the attachment under W2 is not returned
- **Rules:** `get_links_for_attachment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. LA = link on A.
3. LZ = link on A, but `workspace_id W2.id`, `entity_id 502`.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `ids(result) == [LA.id]`.

### ALK-GL-05 — an unknown attachment id returns an empty list
- **Rules:** `get_links_for_attachment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ALK-GL-06 — attachment id 0 returns an empty list
- **Rules:** `get_links_for_attachment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. link on A.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=0)`.

**Then**
1. returns: `result == []`.

### ALK-GL-07 — links come in the order they were made, also after the first was updated
- **Rules:** `get_links_for_attachment` R4 [BUG-1433]
- **Kind:** bug
- **Expect:** xfail BUG-1433 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the updated first link moves last by physical order)

**Given**
1. A = attachment.
2. L1 = link on A, but `entity_id 1`.
3. L2 = link on A, but `entity_id 2`.
4. L3 = link on A, but `entity_id 3`.
5. seqscan.
6. bumpL(L1).

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [L1.id, L2.id, L3.id]`.

### ALK-GL-08 — the query orders by id ascending
- **Rules:** `get_links_for_attachment` R4 [BUG-1433]
- **Kind:** bug
- **Expect:** xfail BUG-1433
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A = attachment.
2. L1 = link on A.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.

### ALK-GL-09 — the links of a soft-deleted attachment are returned
- **Rules:** `get_links_for_attachment` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = attachment, deleted.
2. L1 = link on D.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=D.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.

### ALK-GL-10 — writes nothing: a pending link stays pending, an unflushed edit stays unflushed
- **Rules:** `get_links_for_attachment` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. L1 = link on A.
3. B = attachment, but `file_name "b.png"`.
4. LB = link on B.
5. `LB.entity_id = 777` (not flushed).
6. `P = AttachmentLink(workspace_id=W1.id, attachment_id=A.id, entity_type="project", entity_id=8, linked_by=U1.id)`
7. `db.add(P)` (not flushed).
8. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `ids(result) == [L1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `LB in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### ALK-GL-11 — asked for W2, only the W2 link is returned, though the W1 link is earlier
- **Rules:** `get_links_for_attachment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. LA = link on A.
3. LZ = link on A, but `workspace_id W2.id`, `entity_id 502`.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W2.id, attachment_id=A.id)`.

**Then**
1. returns: `ids(result) == [LZ.id]`.

### ALK-GL-12 — links come in id order, not entity order
- **Rules:** `get_links_for_attachment` R4 [BUG-1433]
- **Kind:** bug
- **Expect:** xfail BUG-1433 (non-strict)
- **Fails today on:** Then 2 (no order is requested; the result rests on physical row order, which can match by accident)

**Given**
1. A = attachment.
2. L1 = link on A, but `entity_id 9`.
3. L2 = link on A, but `entity_id 5`.
4. L3 = link on A, but `entity_id 7`.

**When**
- `result = dao.get_links_for_attachment(db, workspace_id=W1.id, attachment_id=A.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [L1.id, L2.id, L3.id]`.

## Inherited `BaseDAO.create` on `AttachmentLink`

### ALK-CR-01 — the dict of model_dump creates and flushes the link
- **Rules:** `create` R1, Returns; `AttachmentLinkCreateSchema` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.create(db, obj_in=Schema(workspace_id=W1.id, attachment_id=A.id, entity_type="purchase_order", entity_id=501, linked_by=U1.id).model_dump())`.

**Then**
1. returns: `isinstance(result, AttachmentLink)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `attachment_id == A.id`, `entity_type == "purchase_order"`, `entity_id == 501`, `linked_by == U1.id`.
4. count: `links_of(A) == 1`.

### ALK-CR-02 — under Asia/Dhaka linked_at is the UTC moment of the insert
- **Rules:** `create` R2 [BUG-1431]
- **Kind:** bug
- **Expect:** xfail BUG-1431
- **Fails today on:** Then 3 (Dhaka local time is stored, six hours after UTC)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = attachment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "purchase_order", "entity_id": 501, "linked_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `linked_at.tzinfo is None`.
3. re-read result: `abs(linked_at - db.scalar(text("SELECT now() AT TIME ZONE 'UTC'"))) < timedelta(minutes=5)`.

### ALK-CR-03 — under UTC linked_at is the UTC moment of the insert
- **Rules:** `create` R2 [BUG-1431]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = attachment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "purchase_order", "entity_id": 501, "linked_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `abs(linked_at - db.scalar(text("SELECT now() AT TIME ZONE 'UTC'"))) < timedelta(minutes=5)`.

### ALK-CR-04 — a second link for the same attachment and record is refused
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.
2. L1 = link on A.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "purchase_order", "entity_id": 501, "linked_by": U1.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. raises: `"uq_attachment_link_entity" in str(exc.value.orig)`.
3. count: `links_of(A) == 1`.

### ALK-CR-05 — the duplicate is refused also under another workspace
- **Rules:** `create` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.
2. L1 = link on A.

**When**
- `dao.create(db, obj_in={"workspace_id": W2.id, "attachment_id": A.id, "entity_type": "purchase_order", "entity_id": 501, "linked_by": U1.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. count: `links_of(A) == 1`.

### ALK-CR-06 — the same attachment may be linked to another record
- **Rules:** `create` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. L1 = link on A.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "purchase_order", "entity_id": 502, "linked_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. count: `links_of(A) == 2`.

### ALK-CR-07 — an entity type of 65 characters raises DataError
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "x" * 65, "entity_id": 501, "linked_by": U1.id})`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22001"`.
2. count: `links_of(A) == 0`.

### ALK-CR-08 — an entity type of 64 characters is stored
- **Rules:** `create` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "x" * 64, "entity_id": 501, "linked_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `entity_type == "x" * 64`.

### ALK-CR-09 — an unknown attachment id raises IntegrityError 23503
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": MISSING, "entity_type": "purchase_order", "entity_id": 501, "linked_by": U1.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### ALK-CR-10 — an unknown linked_by raises IntegrityError 23503
- **Rules:** `create` R4, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "purchase_order", "entity_id": 501, "linked_by": MISSING})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. count: `links_of(A) == 0`.

### ALK-CR-11 — hard-deleting the attachment deletes its links
- **Rules:** `create` R5
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. L1 = link on A.
3. B = attachment, but `file_name "b.png"`.
4. LB = link on B.

**When**
- `db.execute(text("DELETE FROM attachments WHERE id = :i"), {"i": A.id})`.

**Then**
1. count: `links_of(A) == 0`.
2. count: `links_of(B) == 1`.

### ALK-CR-12 — create is flushed, not committed: a rollback removes the link
- **Rules:** `create` R1, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "attachment_id": A.id, "entity_type": "purchase_order", "entity_id": 501, "linked_by": U1.id})`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `links_of(A) == 1`.
3. count: after the savepoint rollback, `links_of(A) == 0`.
4. mock called: the `db.commit` spy was never called.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec FU-1 (a) — P2: `GET /attachments/` answers 404 for an unknown, other-workspace or soft-deleted record; also the sign path. **OWNER, access:** private projects' attachments listed to any member | `AttachmentService.list_attachments`, `AttachmentManager` sign path | The DAO keeps R7 / CN R4 (ALK-GA-31, CN-10). |
| Spec FU-1 (b) — a `pending` attachment never confirmed holds a place for ever | `AttachmentManager` | A clean-up or age limit; not a DAO rule. |
| Spec FU-1 (c) — `_append_attachment_ledger` takes `links[0]`; with BUG-1433 that is the first link made | `AttachmentManager._append_attachment_ledger` | Depends on GL R4. |
| BUG-1091, BUG-1192 — cross-workspace links written by the sign path | `AttachmentManager` sign path | Already logged; GA R2 here reads what is stored. |
| HR-7 — `GET /attachments/` requires `skip >= 0`, `1 <= limit <= 200` | `GET /attachments/` | Endpoint rule; the DAO's negatives are ALK-GA-24, GA-25. |
| P3 — `get_by_entity` is dead code | `docs/testing/dead-code-removal-checklist.md` | No case. |
| Inherited `BaseDAO` methods other than `create`; module singleton | `tests/unit/dao/base.cases.md` / none | No caller. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | inherited `create` R2, Notes | The note says `linked_at` "equal" to `now() AT TIME ZONE 'UTC'`; after the fix (Python `utcnow()`) it is the insert moment, not the transaction's start, so exact equality would not hold. | ALK-CR-02, CR-03 compare within 5 minutes: today's Dhaka value is 6 hours off, so the strict card still fails today. |
| 2 | `AttachmentLinkCreateSchema` R2 | "accepts no arguments" is shown only through `create` (R3). | No separate card for `model_dump(by_alias=True)`; ALK-SC-05 covers it through `create`. |
| 3 | `get_attachments_for_entity` R1 | "exact, case-sensitive equality" names case only; the other exact-compare shapes (part, leading space, `_`) are taken from the skill. | ALK-GA-05 … GA-08. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `AttachmentLinkCreateSchema` | Returns | ALK-SC-01 |
| `AttachmentLinkCreateSchema` | R1 | ALK-SC-01, ALK-SC-02, ALK-SC-03, ALK-SC-04 |
| `AttachmentLinkCreateSchema` | R2 | ALK-SC-01, ALK-SC-02 |
| `AttachmentLinkCreateSchema` | R3 | ALK-SC-05, ALK-CR-01 |
| `AttachmentLinkCreateSchema` | Errors | ALK-SC-03, ALK-SC-04, ALK-SC-05 |
| `AttachmentLinkCreateSchema` | Side effects | ALK-SC-01 |
| `get_attachments_for_entity` | Returns | ALK-GA-01 |
| `get_attachments_for_entity` | R1 | ALK-GA-01, ALK-GA-02, ALK-GA-03, ALK-GA-04, ALK-GA-05, ALK-GA-06, ALK-GA-07, ALK-GA-08 |
| `get_attachments_for_entity` | R2 | ALK-GA-09, ALK-GA-10 |
| `get_attachments_for_entity` | R3 | ALK-GA-11, ALK-GA-12, ALK-GA-13, ALK-GA-14, ALK-GA-15 |
| `get_attachments_for_entity` | R4 | ALK-GA-16, ALK-GA-17 |
| `get_attachments_for_entity` | R5 | ALK-GA-18, ALK-GA-19, ALK-GA-20, ALK-GA-21, ALK-GA-22, ALK-GA-23, ALK-GA-24, ALK-GA-25 |
| `get_attachments_for_entity` | R6 | ALK-GA-26, ALK-GA-27 |
| `get_attachments_for_entity` | R6 [BUG-1432] | ALK-GA-28, ALK-GA-29, ALK-GA-30 |
| `get_attachments_for_entity` | R7 | ALK-GA-31 |
| `get_attachments_for_entity` | Errors | ALK-GA-24, ALK-GA-25 |
| `get_attachments_for_entity` | Side effects | ALK-GA-32 |
| `count_linked_attachments_for_entity` | Returns | ALK-CN-01, ALK-CN-02 |
| `count_linked_attachments_for_entity` | R1 [BUG-1434] | ALK-CN-01 |
| `count_linked_attachments_for_entity` | R1a | ALK-CN-02 |
| `count_linked_attachments_for_entity` | R2 | ALK-CN-03 |
| `count_linked_attachments_for_entity` | R3 | ALK-CN-04, ALK-CN-05, ALK-CN-06, ALK-CN-07, ALK-CN-08, ALK-CN-09, ALK-CN-12, ALK-CN-13, ALK-CN-14, ALK-CN-15, ALK-CN-16, ALK-CN-17 |
| `count_linked_attachments_for_entity` | R4 | ALK-CN-10 |
| `count_linked_attachments_for_entity` | Side effects | ALK-CN-11 |
| `get_links_for_attachment` | Returns | ALK-GL-01 |
| `get_links_for_attachment` | R1 | ALK-GL-01, ALK-GL-02, ALK-GL-03 |
| `get_links_for_attachment` | R2 | ALK-GL-04, ALK-GL-11 |
| `get_links_for_attachment` | R3 | ALK-GL-05, ALK-GL-06 |
| `get_links_for_attachment` | R4 [BUG-1433] | ALK-GL-07, ALK-GL-08, ALK-GL-12 |
| `get_links_for_attachment` | R5 | ALK-GL-09 |
| `get_links_for_attachment` | Side effects | ALK-GL-10 |
| `create` | Returns | ALK-CR-01 |
| `create` | R1 | ALK-CR-01, ALK-CR-12 |
| `create` | R2 [BUG-1431] | ALK-CR-02, ALK-CR-03 |
| `create` | R3 | ALK-CR-04, ALK-CR-05, ALK-CR-06 |
| `create` | R4 | ALK-CR-07, ALK-CR-08, ALK-CR-09, ALK-CR-10 |
| `create` | R5 | ALK-CR-11 |
| `create` | Errors | ALK-CR-04, ALK-CR-05, ALK-CR-07, ALK-CR-09, ALK-CR-10 |
| `create` | Side effects | ALK-CR-12 |
