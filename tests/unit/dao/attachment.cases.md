# Test cases — `app/dao/attachment.py`

> **Spec:** `tests/unit/dao/attachment.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1–P3 were decided by Claude under the reviewer's delegation.
> **Counts:** 25 cases · 24 expected-to-pass · 1 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_active` 12 · `soft_delete` 13 (1 bug).
- **Depth:** lighter target (skill step 1a). One by-id read and one soft delete of file metadata; no stock, money or order state.
- **Expected-to-fail:** BUG-1430 1, strict: ATT-SD-02 (`Asia/Dhaka`). ATT-SD-01 is the passing `UTC` companion (R2a).
- **Commit spies:** `soft_delete` 1 (ATT-SD-09).
- **Notable design choices:**
  - Every `soft_delete` card that reads `deleted_at` sets `SET LOCAL TIME ZONE` itself and reads the stored moment as `AT TIME ZONE 'UTC'`. The test database runs `America/New_York`, so R1 and R4 cards set `UTC`, or they would fail on BUG-1430.
  - By-id shapes: another workspace's row with the earlier id and with the later id, on both callables.
  - ATT-SD-12 builds a link, a markup layer, a markup event and a ledger row; their constructors come from the sibling specs (Spec gap 1).
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `ATT` = `app/dao/attachment.py`. `GA` get_active · `SD` soft_delete.

**Actors and fixed values.**
- `dao` = the singleton `attachment_dao` (`from app.dao.attachment import attachment_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword unless the card says "positionally". `result` = what the When call returns.
- `Attachment` = `app.models.attachment.Attachment`. `AttachmentLink` = `app.models.attachment_link.AttachmentLink`. `AttachmentMarkup` = `app.models.attachment_markup.AttachmentMarkup`. `AttachmentMarkupEvent` = `app.models.attachment_markup_event.AttachmentMarkupEvent`. `AttachmentLedger` = `app.models.attachment_ledger.AttachmentLedger`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `text` = `sqlalchemy.text`. `datetime`, `timezone` = the `datetime` module's classes.
- MISSING = `999999999`: an id that no row of any table has.
- NOW = `datetime(2026, 11, 3, 17, 8)`, naive. T0 = `datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc)`.

**Externals.** In every `SD` card `app.dao.attachment.utcnow` is patched to return NOW (`mock.patch("app.dao.attachment.utcnow", return_value=NOW)`), active during the When. `GA` cards patch nothing.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`); U1, U2 = two `profiles` rows (`make_profile`).
- **attachment** = `Attachment(workspace_id=W1.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=U1.id, upload_status="ready")`; after the word "but" the card lists every column that differs.
- **deleted attachment** = attachment, but `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`.
- A time-zone line of a Given is the first statement of the test body after the standing rows; `SET LOCAL` ends with the rollback.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **stored_utc(X)** = `db.scalar(text("SELECT deleted_at AT TIME ZONE 'UTC' FROM attachments WHERE id = :i"), {"i": X.id})` — a naive datetime, the stored moment in UTC.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `attachments` rows stored (all workspaces) and the number with `is_deleted` true equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it (`db.new`, `db.dirty`, `db.deleted`). A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- `raises: IntegrityError` = wrap the call: `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, after the `with` block, one `assert` per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); the "inside the savepoint" checks run first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-1430")`.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `attachments`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `AttachmentDAO.get_active`

### ATT-GA-01 — a live ready attachment is returned, the instance the session holds
- **Rules:** `get_active` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = attachment, but `file_name "other.png"`.
2. A = attachment.

**When**
- `result = dao.get_active(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, Attachment)`.
2. returns: `result is A`.
3. returns: `result.file_name == "file.png"`.

### ATT-GA-02 — a pending attachment counts as active
- **Rules:** `get_active` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment, but `upload_status "pending"`.

**When**
- `result = dao.get_active(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### ATT-GA-03 — a failed attachment counts as active
- **Rules:** `get_active` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment, but `upload_status "failed"`.

**When**
- `result = dao.get_active(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### ATT-GA-04 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `get_active` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = attachment, but `workspace_id W2.id`.
2. A = attachment.

**When**
- `result = dao.get_active(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ATT-GA-05 — another workspace's id returns None, when that row is the later one
- **Rules:** `get_active` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. Z = attachment, but `workspace_id W2.id`.

**When**
- `result = dao.get_active(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ATT-GA-06 — the id under another workspace returns None
- **Rules:** `get_active` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.get_active(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### ATT-GA-07 — an unknown id returns None
- **Rules:** `get_active` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.get_active(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ATT-GA-08 — id 0 returns None
- **Rules:** `get_active` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.get_active(db, id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ATT-GA-09 — a soft-deleted attachment returns None
- **Rules:** `get_active` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = deleted attachment.

**When**
- `result = dao.get_active(db, id=D.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ATT-GA-10 — once is_deleted is False again, the row is returned
- **Rules:** `get_active` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. D = deleted attachment.
2. `D.is_deleted = False`, `D.deleted_at = None`, `D.deleted_by = None`, then `db.flush()`.

**When**
- `result = dao.get_active(db, id=D.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == D.id`.

### ATT-GA-11 — positional arguments work
- **Rules:** `get_active` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.get_active(db, A.id, W1.id)` (positionally).

**Then**
1. returns: `result.id == A.id`.

### ATT-GA-12 — writes nothing: a pending row stays pending, an unflushed edit stays unflushed
- **Rules:** `get_active` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. B = attachment, but `file_name "other.png"`.
3. `B.note = "Edited"` (not flushed).
4. `P = Attachment(workspace_id=W1.id, file_name="p.png", mime_type="image/png", file_size=1, uploaded_by=U1.id)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `"FOR UPDATE" not in sql.upper()`.
9. nothing written: nothing written.
10. unchanged: unchanged(A).

## `AttachmentDAO.soft_delete`

### ATT-SD-01 — under UTC the row is marked deleted at NOW by the given profile; nothing else changes
- **Rules:** `soft_delete` R1, R2a, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = attachment, but `public_id "pid-1"`, `file_url "https://files.example/f.png"`.

**When**
- `result = dao.soft_delete(db, id=A.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result is A`.
2. re-read A: `is_deleted is True`, `deleted_by == U2.id`.
3. re-read A: `stored_utc(A) == NOW`.
4. re-read A: `upload_status == "ready"`, `public_id == "pid-1"`, `file_url == "https://files.example/f.png"`.
5. re-read A: `file_name == "file.png"`, `uploaded_by == U1.id`, `workspace_id == W1.id`.

### ATT-SD-02 — under Asia/Dhaka the stored moment is still NOW in UTC
- **Rules:** `soft_delete` R2 [BUG-1430]
- **Kind:** bug
- **Expect:** xfail BUG-1430
- **Fails today on:** Then 3 (the naive value is read as Dhaka time: 11:08 UTC is stored)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = attachment.

**When**
- `result = dao.soft_delete(db, id=A.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. re-read A: `is_deleted is True`.
3. re-read A: `stored_utc(A) == NOW`.

### ATT-SD-03 — the row of another workspace is not deleted, when it is the earlier one
- **Rules:** `soft_delete` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = attachment, but `workspace_id W2.id`.
2. A = attachment.

**When**
- `result = dao.soft_delete(db, id=Z.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(Z).
3. unchanged: unchanged(A).

### ATT-SD-04 — the row of another workspace is not deleted, when it is the later one
- **Rules:** `soft_delete` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.
2. Z = attachment, but `workspace_id W2.id`.

**When**
- `result = dao.soft_delete(db, id=Z.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(Z).

### ATT-SD-05 — the id under another workspace deletes nothing
- **Rules:** `soft_delete` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.soft_delete(db, id=A.id, workspace_id=W2.id, deleted_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(A).

### ATT-SD-06 — an unknown id returns None and writes nothing
- **Rules:** `soft_delete` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.soft_delete(db, id=MISSING, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. statement: `written == []`.
3. nothing written: nothing written.

### ATT-SD-07 — id 0 returns None and writes nothing
- **Rules:** `soft_delete` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `result = dao.soft_delete(db, id=0, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### ATT-SD-08 — an already deleted row is deleted again: the stamp is overwritten
- **Rules:** `soft_delete` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. D = deleted attachment.

**When**
- `result = dao.soft_delete(db, id=D.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result is D`.
2. re-read D: `is_deleted is True`, `deleted_by == U2.id`.
3. re-read D: `stored_utc(D) == NOW`.

### ATT-SD-09 — flushed, not committed: a savepoint rollback leaves the row live
- **Rules:** `soft_delete` R5, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.soft_delete(db, id=A.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. count: inside the savepoint, `attachments` rows with `id == A.id` and `is_deleted` true: exactly 1.
3. re-read A: after the savepoint rollback, `is_deleted is False`, `deleted_by is None`, `deleted_at is None`.
4. mock called: the `db.commit` spy was never called.

### ATT-SD-10 — an unknown deleted_by fails at the flush
- **Rules:** `soft_delete` R6, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `dao.soft_delete(db, id=A.id, workspace_id=W1.id, deleted_by=MISSING)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `IntegrityError`.
2. raises: `exc.value.orig.pgcode == "23503"`.
3. re-read A: `is_deleted is False`, `deleted_by is None`, `deleted_at is None`.

### ATT-SD-11 — positional arguments raise TypeError and change nothing
- **Rules:** `soft_delete` Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = attachment.

**When**
- `dao.soft_delete(db, A.id, W1.id, U2.id)` (positionally), inside `with pytest.raises(TypeError):`.

**Then**
1. raises: `TypeError`.
2. unchanged: unchanged(A).

### ATT-SD-12 — the attachment's link, markup, markup event and ledger row are not touched
- **Rules:** `soft_delete` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. L = `AttachmentLink(workspace_id=W1.id, attachment_id=A.id, entity_type="purchase_order", entity_id=501, linked_by=U1.id)`.
3. M = `AttachmentMarkup(workspace_id=W1.id, attachment_id=A.id, user_id=U1.id, payload={"shapes": [1]})`.
4. E = `AttachmentMarkupEvent(workspace_id=W1.id, attachment_id=A.id, user_id=U1.id, event_type="markup_saved", description="Saved")`.
5. G = `AttachmentLedger(workspace_id=W1.id, attachment_id=A.id, transaction_type="ready", file_name="file.png", mime_type="image/png", file_size=100, entity_type="purchase_order", performed_at=datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc))`.

**When**
- `result = dao.soft_delete(db, id=A.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. unchanged: unchanged(L).
3. unchanged: unchanged(M).
4. unchanged: unchanged(E).
5. unchanged: unchanged(G).

### ATT-SD-13 — one UPDATE of the one row, and no other attachment changes
- **Rules:** `soft_delete` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = attachment.
2. B = attachment, but `file_name "other.png"`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.soft_delete(db, id=A.id, workspace_id=W1.id, deleted_by=U2.id)`.

**Then**
1. returns: `result.id == A.id`.
2. statement: `len(written) == 1`.
3. statement: `written[0].lstrip().upper().startswith("UPDATE ATTACHMENTS")`.
4. unchanged: unchanged(B).

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| Spec FU-1 (a) — P2: `DELETE /attachments/{id}/` on an attachment already deleted answers 404 `Attachment <id> not found`, nothing written (no second ledger row, activity entry, Cloudinary destroy) | `AttachmentManager.delete_attachment` | The DAO keeps R4 (ATT-SD-08). |
| Spec FU-1 (b) — a second attachment with the same `(workspace_id, public_id)` is refused (23505) | `AttachmentManager.create_pending_attachment` | Inherited `create`; base spec. |
| Spec FU-2 — whether production's `TimeZone` is `UTC` (stored `deleted_at` values shifted by BUG-1430) | Production check | Not a unit test. |
| P3 — `restore` is dead code | `docs/testing/dead-code-removal-checklist.md` | No case. |
| Inherited `BaseDAO` methods (`create`, `update`, `get_by_id_and_workspace`, …) | `tests/unit/dao/base.spec.md` / `base.cases.md` | Not overridden. |
| Module singleton `attachment_dao` | none (no logic) | Entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `soft_delete` R7 | The rows of `attachment_links`, `attachment_markups`, `attachment_markup_events`, `attachment_ledger` are named but not how to build them. | ATT-SD-12 takes the constructors from the sibling specs (`attachment_link`, `attachment_markup`, `attachment_markup_event`, `attachment_ledger` cases). A wrong column fails that one card. |
| 2 | `soft_delete` R2 | The `Today` note names `America/New_York` (22:08) as well as `Asia/Dhaka`. | One xfail card, under `Asia/Dhaka`; lighter target. |
| 3 | `soft_delete` R1 | "`deleted_at` = the value of `utcnow()`" does not say what the returned instance holds in memory before a re-read. | Cards check the stored moment only (`stored_utc`). |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_active` | Returns | ATT-GA-01 |
| `get_active` | R1 | ATT-GA-01, ATT-GA-02, ATT-GA-03, ATT-GA-11 |
| `get_active` | R2 | ATT-GA-04, ATT-GA-05, ATT-GA-06 |
| `get_active` | R3 | ATT-GA-07, ATT-GA-08 |
| `get_active` | R4 | ATT-GA-09, ATT-GA-10 |
| `get_active` | Side effects | ATT-GA-12 |
| `soft_delete` | Returns | ATT-SD-01 |
| `soft_delete` | R1 | ATT-SD-01 |
| `soft_delete` | R2 [BUG-1430] | ATT-SD-02 |
| `soft_delete` | R2a | ATT-SD-01 |
| `soft_delete` | R3 | ATT-SD-03, ATT-SD-04, ATT-SD-05, ATT-SD-06, ATT-SD-07 |
| `soft_delete` | R4 | ATT-SD-08 |
| `soft_delete` | R5 | ATT-SD-09 |
| `soft_delete` | R6 | ATT-SD-10 |
| `soft_delete` | R7 | ATT-SD-12 |
| `soft_delete` | Errors row 1 | ATT-SD-10 |
| `soft_delete` | Errors row 2 | ATT-SD-11 |
| `soft_delete` | Side effects | ATT-SD-01, ATT-SD-09, ATT-SD-13 |
