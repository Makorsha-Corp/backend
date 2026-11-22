# Test cases — `app/dao/attachment_markup.py`

> **Spec:** `tests/unit/dao/attachment_markup.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1 was decided by Claude under the reviewer's delegation.
> **Counts:** 41 cases · 39 expected-to-pass · 2 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `get_for_attachment` 13 (2 bug) · `get_for_user` 8 · `upsert_for_user` 14 · `delete_for_user` 6.
- **Depth:** lighter target (skill step 1a). One user's JSON drawing layer per attachment: create, replace, delete, read; no stock, money or order state.
- **Expected-to-fail:** BUG-1435 2: AMK-GF-10 non-strict, AMK-GF-11 strict (the SQL recorder). AMK-GF-08, GF-09 are the passing companions with distinct times.
- **Commit spies:** `upsert_for_user` 2 (insert AMK-UP-12, update AMK-UP-13) · `delete_for_user` 1 (AMK-DL-06).
- **Notable design choices:**
  - `updated_at` cannot move forward inside one transaction (it is `now()`). R4 is checked by the statement recorder (no `UPDATE` sent) and by an hour-older stamp that stays, or becomes `now()`.
  - Layers of one transaction share `updated_at`; the older layer in the tie cards has the highest id, so stamp and id do not rise together.
  - AMK-UP-10 puts the other workspace's layer on the same attachment and user, the one shape the unique constraint without `workspace_id` refuses.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `AMK` = `app/dao/attachment_markup.py`. `GF` get_for_attachment · `GU` get_for_user · `UP` upsert_for_user · `DL` delete_for_user.

**Actors and fixed values.**
- `dao` = the singleton `attachment_markup_dao` (`from app.dao.attachment_markup import attachment_markup_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `AttachmentMarkup` = `app.models.attachment_markup.AttachmentMarkup`. `Attachment` = `app.models.attachment.Attachment`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.

**Externals.** None. Nothing is mocked. `updated_at` comes from the database.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`); U1, U2, U3 = three `profiles` rows (`make_profile`); AT1 = `Attachment(workspace_id=W1.id, file_name="a1.png", mime_type="image/png", file_size=100, uploaded_by=U1.id, upload_status="ready")`; AT2 = the same, but `file_name "a2.png"`; ATD = the same as AT1, but `file_name "gone.png"`, `is_deleted True`, `deleted_by U1.id`; AT9 = the same as AT1, but `file_name "far.png"`, `workspace_id W2.id`.
- **layer** = `AttachmentMarkup(workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [1]})`; after "but" the card lists every column that differs. No `attachment_markups` row exists unless the Given lists it.
- **hour_older(X)** = `db.execute(text("UPDATE attachment_markups SET updated_at = now() - interval '1 hour' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **bump(X)** = `db.execute(text("UPDATE attachment_markups SET payload = CAST(:p AS json) WHERE id = :i"), {"p": '{"shapes": [9]}', "i": X.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values. **NOW_DB** = `db.scalar(text("SELECT now()"))`.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **stored_json(X)** = `db.scalar(text("SELECT payload::text FROM attachment_markups WHERE id = :i"), {"i": X.id})`.
- **layers(a, u)** = `db.scalar(text("SELECT count(*) FROM attachment_markups WHERE attachment_id = :a AND user_id = :u"), {"a": a, "u": u})`.
- **nothing written** = the numbers of `attachment_markups` and of `attachment_markup_events` rows stored (all workspaces) equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` and `unchanged:` lines.
- `raises: IntegrityError` = wrap the call: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, one `assert` per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** `Expect: xfail BUG-1435` = `pytest.mark.xfail(strict=True, reason="BUG-1435")`; `(non-strict)` = `strict=False`. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `attachment_markups`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `AttachmentMarkupDAO.get_for_attachment`

### AMK-GF-01 — returns a list of every user's layer on the attachment
- **Rules:** `get_for_attachment` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `user_id U2.id`.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `set(ids(result)) == {A.id, B.id}`.
3. returns: `isinstance(result[0], AttachmentMarkup)`.

### AMK-GF-02 — a layer on another attachment is not returned
- **Rules:** `get_for_attachment` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = layer, but `attachment_id AT2.id`, `user_id U2.id`.
2. A = layer.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### AMK-GF-03 — a W2 layer on a W1 attachment is not returned for W1
- **Rules:** `get_for_attachment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `workspace_id W2.id`, `user_id U2.id`.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### AMK-GF-04 — a W2 layer on a W1 attachment is returned for W2
- **Rules:** `get_for_attachment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `workspace_id W2.id`, `user_id U2.id`.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W2.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### AMK-GF-05 — an unknown attachment id returns an empty list
- **Rules:** `get_for_attachment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=MISSING)`.

**Then**
1. returns: `result == []`.

### AMK-GF-06 — attachment id 0 returns an empty list
- **Rules:** `get_for_attachment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=0)`.

**Then**
1. returns: `result == []`.

### AMK-GF-07 — an attachment without layers returns an empty list
- **Rules:** `get_for_attachment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT2.id)`.

**Then**
1. returns: `result == []`.

### AMK-GF-08 — the hour-older layer comes first, though its id is higher
- **Rules:** `get_for_attachment` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `user_id U2.id`.
3. hour_older(B).

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### AMK-GF-09 — on a tie both layers follow the older one
- **Rules:** `get_for_attachment` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `user_id U2.id`.
3. D = layer, but `user_id U3.id`.
4. hour_older(D).

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0].id == D.id`.
3. returns: `set(ids(result)[1:]) == {A.id, B.id}`.

### AMK-GF-10 — on a tie the lowest id comes first, when it was updated in place
- **Rules:** `get_for_attachment` R4 [BUG-1435]
- **Kind:** bug
- **Expect:** xfail BUG-1435 (non-strict)
- **Fails today on:** Then 2 (no tie-break; the updated layer moves last by physical order)

**Given**
1. A = layer.
2. B = layer, but `user_id U2.id`.
3. C = layer, but `user_id U3.id`.
4. seqscan.
5. bump(A).

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### AMK-GF-11 — the query orders by updated_at, then id, ascending
- **Rules:** `get_for_attachment` R4 [BUG-1435]
- **Kind:** bug
- **Expect:** xfail BUG-1435
- **Fails today on:** Then 3 (the query orders by `updated_at` alone)

**Given**
1. A = layer.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"updated_at" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("updated_at") < order_part.index(".id")`.
5. statement: `"DESC" not in order_part.upper()`.

### AMK-GF-12 — the layers of a soft-deleted attachment are returned
- **Rules:** `get_for_attachment` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = layer, but `attachment_id ATD.id`.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=ATD.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### AMK-GF-13 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_for_attachment` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `attachment_id AT2.id`.
3. `B.payload = {"shapes": [5]}` (not flushed).
4. `P = AttachmentMarkup(workspace_id=W1.id, attachment_id=AT1.id, user_id=U2.id, payload={"shapes": [3]})`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

## `AttachmentMarkupDAO.get_for_user`

### AMK-GU-01 — returns the user's layer, the instance the session holds
- **Rules:** `get_for_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = layer, but `user_id U2.id`.
2. A = layer.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id)`.

**Then**
1. returns: `result is A`.

### AMK-GU-02 — another user returns None
- **Rules:** `get_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.

### AMK-GU-03 — another attachment returns None
- **Rules:** `get_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, attachment_id=AT2.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.

### AMK-GU-04 — another workspace's earlier layer returns None
- **Rules:** `get_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = layer, but `workspace_id W2.id`, `attachment_id AT9.id`.
2. A = layer.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, attachment_id=AT9.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.

### AMK-GU-05 — the layer asked for under another workspace returns None
- **Rules:** `get_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.get_for_user(db, workspace_id=W2.id, attachment_id=AT1.id, user_id=U1.id)`.

**Then**
1. returns: `result is None`.

### AMK-GU-06 — ids of 0 return None, with no error
- **Rules:** `get_for_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, attachment_id=0, user_id=0)`.

**Then**
1. returns: `result is None`.

### AMK-GU-07 — the layer on a soft-deleted attachment is returned
- **Rules:** `get_for_user` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = layer, but `attachment_id ATD.id`.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, attachment_id=ATD.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.

### AMK-GU-08 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_for_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `user_id U2.id`.
3. `B.payload = {"shapes": [5]}` (not flushed).
4. `P = AttachmentMarkup(workspace_id=W1.id, attachment_id=AT2.id, user_id=U1.id, payload={"shapes": [3]})`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

## `AttachmentMarkupDAO.upsert_for_user`

### AMK-UP-01 — the first save creates the layer with the four values, stamped now
- **Rules:** `upsert_for_user` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No layer exists.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [1]})`.

**Then**
1. returns: `isinstance(result, AttachmentMarkup)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `attachment_id == AT1.id`, `user_id == U1.id`, `payload == {"shapes": [1]}`.
4. re-read result: `updated_at == NOW_DB`.
5. count: `layers(AT1.id, U1.id) == 1`.
6. count: `attachment_markup_events` has 0 rows with `attachment_id == AT1.id`.

### AMK-UP-02 — a later save replaces the payload of the same row
- **Rules:** `upsert_for_user` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [2]})`.

**Then**
1. returns: `result is A`.
2. re-read A: `payload == {"shapes": [2]}`.
3. count: `layers(AT1.id, U1.id) == 1`.

### AMK-UP-03 — {} is stored as {} on insert
- **Rules:** `upsert_for_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No layer exists.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `payload == {}`.
3. re-read result: `stored_json(result) == "{}"`.

### AMK-UP-04 — None is stored as JSON null on insert
- **Rules:** `upsert_for_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No layer exists.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload=None)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `payload is None`.
3. re-read result: `stored_json(result) == "null"`.

### AMK-UP-05 — None is stored as JSON null on update
- **Rules:** `upsert_for_user` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload=None)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `stored_json(A) == "null"`.

### AMK-UP-06 — an equal payload sends no UPDATE and the stamp stays
- **Rules:** `upsert_for_user` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.
2. hour_older(A).
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [1]})`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `written == []`.
3. unchanged: unchanged(A).

### AMK-UP-07 — a different payload sends one UPDATE and the stamp becomes now
- **Rules:** `upsert_for_user` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.
2. hour_older(A).
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [2]})`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `len(written) == 1`.
3. statement: `written[0].lstrip().upper().startswith("UPDATE")`.
4. re-read A: `updated_at == NOW_DB`.

### AMK-UP-08 — an unknown attachment fails at the flush with 23503
- **Rules:** `upsert_for_user` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No layer exists.

**When**
- `dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=MISSING, user_id=U1.id, payload={"shapes": [1]})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### AMK-UP-09 — an unknown user fails at the flush with 23503
- **Rules:** `upsert_for_user` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No layer exists.

**When**
- `dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=MISSING, payload={"shapes": [1]})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### AMK-UP-10 — the same attachment and user under another workspace is refused with 23505
- **Rules:** `upsert_for_user` R6, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. Z = layer, but `workspace_id W2.id`.

**When**
- `dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [2]})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. raises: `"uq_attachment_markup_user" in str(exc.value.orig)`.
3. unchanged: unchanged(Z).
4. count: `layers(AT1.id, U1.id) == 1`.

### AMK-UP-11 — a W2 layer is created on a W1 attachment
- **Rules:** `upsert_for_user` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No layer exists.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W2.id, attachment_id=AT1.id, user_id=U2.id, payload={"shapes": [1]})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W2.id`, `attachment_id == AT1.id`, `user_id == U2.id`.

### AMK-UP-12 — an insert is flushed, not committed: a rollback removes it
- **Rules:** `upsert_for_user` R8, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No layer exists.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [1]})`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `layers(AT1.id, U1.id) == 1`.
3. count: after the savepoint rollback, `layers(AT1.id, U1.id) == 0`.
4. mock called: the `db.commit` spy was never called.

### AMK-UP-13 — an update is flushed, not committed: a rollback restores the old payload
- **Rules:** `upsert_for_user` R8, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = layer.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [2]})`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: inside the savepoint, `payload == {"shapes": [2]}`.
3. re-read A: after the savepoint rollback, `payload == {"shapes": [1]}`.
4. mock called: the `db.commit` spy was never called.

### AMK-UP-14 — the user's layer on another attachment and another user's layer here are not taken
- **Rules:** `upsert_for_user` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. B = layer, but `attachment_id AT2.id`.
2. C = layer, but `user_id U2.id`.

**When**
- `result = dao.upsert_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, payload={"shapes": [7]})`.

**Then**
1. returns: `result.id not in {B.id, C.id}`.
2. count: `layers(AT1.id, U1.id) == 1`.
3. unchanged: unchanged(B).
4. unchanged: unchanged(C).

## `AttachmentMarkupDAO.delete_for_user`

### AMK-DL-01 — the user's layer is deleted and True returned; the others stay
- **Rules:** `delete_for_user` R1, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = layer.
2. B = layer, but `user_id U2.id`.

**When**
- `result = dao.delete_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id)`.

**Then**
1. returns: `result is True`.
2. count: `layers(AT1.id, U1.id) == 0`.
3. unchanged: unchanged(B).
4. count: `attachment_markup_events` has 0 rows with `attachment_id == AT1.id`.

### AMK-DL-02 — another user's call returns False and deletes nothing
- **Rules:** `delete_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.delete_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U2.id)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(A).

### AMK-DL-03 — a call under another workspace returns False and deletes nothing
- **Rules:** `delete_for_user` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.delete_for_user(db, workspace_id=W2.id, attachment_id=AT1.id, user_id=U1.id)`.

**Then**
1. returns: `result is False`.
2. unchanged: unchanged(A).

### AMK-DL-04 — unknown ids return False
- **Rules:** `delete_for_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.

**When**
- `result = dao.delete_for_user(db, workspace_id=W1.id, attachment_id=MISSING, user_id=MISSING)`.

**Then**
1. returns: `result is False`.
2. nothing written: nothing written.

### AMK-DL-05 — a second call after a delete returns False
- **Rules:** `delete_for_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = layer.
2. `dao.delete_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id)`

**When**
- `result = dao.delete_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id)`.

**Then**
1. returns: `result is False`.
2. count: `layers(AT1.id, U1.id) == 0`.

### AMK-DL-06 — flushed, not committed: a rollback brings the row back
- **Rules:** `delete_for_user` R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = layer.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.delete_for_user(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id)`.

**Then**
1. returns: `result is True`.
2. count: inside the savepoint, `layers(AT1.id, U1.id) == 0`.
3. count: after the savepoint rollback, `layers(AT1.id, U1.id) == 1`.
4. mock called: the `db.commit` spy was never called.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec FU-1 (a) — two first saves of one user's layer at once: the second fails 23505 → 500 | `AttachmentMarkupManager.put_own_layer` | Needs two connections; the manager may retry. |
| Spec FU-1 (b) — `markup_updated` logged when the payload equals the stored one | `AttachmentMarkupManager.put_own_layer` | Here the row is not written (AMK-UP-06). |
| P1 — the markup endpoints answer 404 `Attachment <id> not found.` for a deleted attachment | `AttachmentMarkupManager._get_ready_attachment` | The DAO keeps its raw reads (AMK-GF-12, GU-07). |
| HR-16 — the attachment is checked in the caller's workspace before a layer is written | `AttachmentMarkupManager` | AMK-UP-11 shows the DAO accepts what it is given. |
| Inherited `BaseDAO` methods; module singleton | `tests/unit/dao/base.cases.md` / none | No caller. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_for_attachment` Returns | "no paging, no cap" has no number; one layer per user means a cap test needs more than 100 profiles. | No cap card. |
| 2 | Notes | Keyword-only parameters stated as a note, not a rule. | No `TypeError` card. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_for_attachment` | Returns | AMK-GF-01 |
| `get_for_attachment` | R1 | AMK-GF-01, AMK-GF-02 |
| `get_for_attachment` | R2 | AMK-GF-03, AMK-GF-04 |
| `get_for_attachment` | R3 | AMK-GF-05, AMK-GF-06, AMK-GF-07 |
| `get_for_attachment` | R4 | AMK-GF-08, AMK-GF-09 |
| `get_for_attachment` | R4 [BUG-1435] | AMK-GF-10, AMK-GF-11 |
| `get_for_attachment` | R5 | AMK-GF-12 |
| `get_for_attachment` | Side effects | AMK-GF-13 |
| `get_for_user` | Returns | AMK-GU-01 |
| `get_for_user` | R1 | AMK-GU-01 |
| `get_for_user` | R2 | AMK-GU-02, AMK-GU-03, AMK-GU-04, AMK-GU-05 |
| `get_for_user` | R3 | AMK-GU-06 |
| `get_for_user` | R4 | AMK-GU-07 |
| `get_for_user` | Side effects | AMK-GU-08 |
| `upsert_for_user` | Returns | AMK-UP-01 |
| `upsert_for_user` | R1 | AMK-UP-01, AMK-UP-14 |
| `upsert_for_user` | R2 | AMK-UP-02 |
| `upsert_for_user` | R3 | AMK-UP-03, AMK-UP-04, AMK-UP-05 |
| `upsert_for_user` | R4 | AMK-UP-06, AMK-UP-07 |
| `upsert_for_user` | R5 | AMK-UP-08, AMK-UP-09 |
| `upsert_for_user` | R6 | AMK-UP-10 |
| `upsert_for_user` | R7 | AMK-UP-11 |
| `upsert_for_user` | R8 | AMK-UP-12, AMK-UP-13 |
| `upsert_for_user` | Errors row 1 | AMK-UP-08, AMK-UP-09 |
| `upsert_for_user` | Errors row 2 | AMK-UP-10 |
| `upsert_for_user` | Side effects | AMK-UP-01, AMK-UP-12, AMK-UP-13 |
| `delete_for_user` | Returns | AMK-DL-01 |
| `delete_for_user` | R1 | AMK-DL-01 |
| `delete_for_user` | R2 | AMK-DL-02, AMK-DL-03, AMK-DL-04, AMK-DL-05 |
| `delete_for_user` | R3 | AMK-DL-06 |
| `delete_for_user` | Side effects | AMK-DL-01, AMK-DL-06 |
