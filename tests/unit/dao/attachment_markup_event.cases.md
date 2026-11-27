# Test cases — `app/dao/attachment_markup_event.py`

> **Spec:** `tests/unit/dao/attachment_markup_event.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1, P2 were decided by Claude under the reviewer's delegation.
> **Revision:** 1 — the spec did not change. Additive, from `attachment_markup_event.verify.md` (case-missing Finding 1; recipe R-1): R-1 → AME-LA-14. No other card changed; no ID retired. Ruling on AME-LA-09: no change.
> **Counts:** 25 cases · 22 expected-to-pass · 3 expected-to-fail (bugs) · 5 deferred

## Reviewer summary
- **Per callable:** `list_for_attachment` 14 (3 bug) · `create_event` 11.
- **Depth:** lighter target (skill step 1a). An append-only history: one read, one insert; no stock, money or order state.
- **Expected-to-fail:** BUG-1436 2: AME-LA-08 non-strict, AME-LA-09 strict (the SQL recorder). BUG-1437 1, strict: AME-LA-10 (201 entries). AME-LA-11 is the passing companion: the first 200 are the newest 200, today and after the fix.
- **Commit spies:** `create_event` 1 (AME-CE-11).
- **Notable design choices:**
  - `created_at` is a Python default bound at import, which a patch of a module name does not reach (spec Externals). Read cards build rows with `created_at` given; AME-CE-02 checks the default against the database's real clock (`clock_timestamp()`), within 5 seconds, under `Asia/Dhaka`, so a local-time default would be six hours off.
  - The `limit` parameter is never passed by the caller and goes with BUG-1437; its negative and zero values get no card.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `AME` = `app/dao/attachment_markup_event.py`. `LA` list_for_attachment · `CE` create_event.

**Actors and fixed values.**
- `dao` = the singleton `attachment_markup_event_dao` (`from app.dao.attachment_markup_event import attachment_markup_event_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `AttachmentMarkupEvent` = `app.models.attachment_markup_event.AttachmentMarkupEvent`. `Attachment` = `app.models.attachment.Attachment`. `IntegrityError`, `DataError` = `sqlalchemy.exc` classes. `text` = `sqlalchemy.text`. `datetime`, `timedelta` = the `datetime` module's classes.
- MISSING = `999999999`: an id that no row of any table has.
- T10, T11, T12 = `datetime(2026, 3, 4, 10, 0, 0)`, `datetime(2026, 3, 4, 11, 0, 0)`, `datetime(2026, 3, 4, 12, 0, 0)` — naive.

**Externals.** None. Nothing is mocked.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line: W1, W2 = two `workspaces` rows (`make_workspace`); U1 = a `profiles` row (`make_profile`); AT1 = `Attachment(workspace_id=W1.id, file_name="a1.png", mime_type="image/png", file_size=100, uploaded_by=U1.id, upload_status="ready")`; AT2 = the same, but `file_name "a2.png"`; ATD = the same as AT1, but `file_name "gone.png"`, `is_deleted True`, `deleted_by U1.id`.
- **entry** = `AttachmentMarkupEvent(workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_saved", description="Saved")`; the card always gives `created_at`; after "but" it lists every other column that differs. No entry exists unless the Given lists it.
- **bumpE(X)** = `db.execute(text("UPDATE attachment_markup_events SET description = description || '!' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
- A time-zone line of a Given is the first statement of the test body after the standing rows.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **stored_json(X)** = `db.scalar(text("SELECT metadata_json::text FROM attachment_markup_events WHERE id = :i"), {"i": X.id})`. **is_sql_null(X)** = `db.scalar(text("SELECT metadata_json IS NULL FROM attachment_markup_events WHERE id = :i"), {"i": X.id})`.
- **UTC_CLOCK** = `db.scalar(text("SELECT clock_timestamp() AT TIME ZONE 'UTC'"))`, read after the call: the real moment in UTC, naive.
- **nothing written** = the number of `attachment_markup_events` rows stored (all workspaces) equals its value before the call.
- `pending:` lines check the session after the call, before anything expires it. A card lists them ahead of its `nothing written:` and `unchanged:` lines.
- `raises: E` (`IntegrityError` or `DataError`) = wrap the call: `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, one `assert` per line.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `attachment_markup_events`; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT`; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `AttachmentMarkupEventDAO.list_for_attachment`

### AME-LA-01 — returns a list of the attachment's entries, newest first
- **Rules:** `list_for_attachment` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`.
2. B = entry, `created_at T11`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `isinstance(result[0], AttachmentMarkupEvent)`.

### AME-LA-02 — a newer entry of another attachment is not returned
- **Rules:** `list_for_attachment` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`.
2. B = entry, `created_at T12`, but `attachment_id AT2.id`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### AME-LA-03 — a newer entry under another workspace is not returned
- **Rules:** `list_for_attachment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`.
2. Z = entry, `created_at T12`, but `workspace_id W2.id`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### AME-LA-04 — an unknown attachment id returns an empty list
- **Rules:** `list_for_attachment` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=MISSING)`.

**Then**
1. returns: `result == []`.

### AME-LA-05 — attachment id 0 returns an empty list
- **Rules:** `list_for_attachment` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=0)`.

**Then**
1. returns: `result == []`.

### AME-LA-06 — newest first, whatever the ids
- **Rules:** `list_for_attachment` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`.
2. B = entry, `created_at T12`.
3. C = entry, `created_at T11`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### AME-LA-07 — on a tie both entries sit between the newer and the older one
- **Rules:** `list_for_attachment` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `created_at T11`.
2. B = entry, `created_at T11`.
3. C = entry, `created_at T12`.
4. D = entry, `created_at T10`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `set(ids(result)[1:3]) == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### AME-LA-08 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `list_for_attachment` R3 [BUG-1436]
- **Kind:** bug
- **Expect:** xfail BUG-1436 (non-strict)
- **Fails today on:** Then 2 (no tie-break; the updated lowest id moves last by physical order)

**Given**
1. A = entry, `created_at T11`.
2. B = entry, `created_at T11`.
3. C = entry, `created_at T11`.
4. D = entry, `created_at T12`.
5. seqscan.
6. bumpE(A).

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `ids(result) == [D.id, C.id, B.id, A.id]`.

### AME-LA-09 — the query orders by created_at, then id, both descending
- **Rules:** `list_for_attachment` R3 [BUG-1436]
- **Kind:** bug
- **Expect:** xfail BUG-1436
- **Fails today on:** Then 3 (the query orders by `created_at` alone)

**Given**
1. A = entry, `created_at T10`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"created_at" in order_part`.
3. statement: `".id" in order_part`.
4. statement: `order_part.index("created_at") < order_part.index(".id")`.
5. statement: `order_part.upper().count("DESC") == 2`.

### AME-LA-10 — every entry is returned: 201 give 201
- **Rules:** `list_for_attachment` R4 [BUG-1437]
- **Kind:** bug
- **Expect:** xfail BUG-1437
- **Fails today on:** Then 2 (at most 200 are returned)

**Given**
1. 201 entries E1 … E201, built with `add_all` and flushed: Ek = entry, `created_at` = `T10 + timedelta(minutes=k)`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 201`.

### AME-LA-11 — of 201 entries the first 200 returned are the newest 200, newest first
- **Rules:** `list_for_attachment` R4 [BUG-1437]
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 201 entries E1 … E201, built with `add_all` and flushed: Ek = entry, `created_at` = `T10 + timedelta(minutes=k)`.
2. `newest` = the ids of E201, E200, … E1, in that order.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result)[:200] == newest[:200]`.

### AME-LA-12 — the entries of a soft-deleted attachment are returned
- **Rules:** `list_for_attachment` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`, but `attachment_id ATD.id`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=ATD.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### AME-LA-13 — writes nothing: a pending entry stays pending, an unflushed edit stays unflushed
- **Rules:** `list_for_attachment` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry, `created_at T10`.
2. B = entry, `created_at T10`, but `attachment_id AT2.id`.
3. `B.description = "Edited"` (not flushed).
4. `P = AttachmentMarkupEvent(workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_saved", description="Pending", created_at=T12)`
5. `db.add(P)` (not flushed).
6. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `B in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. statement: `"FOR UPDATE" not in sql.upper()`.
8. nothing written: nothing written.

### AME-LA-14 — asked for W2, only the W2 entry is returned, though the W1 entry is earlier
- **Rules:** `list_for_attachment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, `created_at T11`.
2. Z = entry, `created_at T11`, but `workspace_id W2.id`.

**When**
- `result = dao.list_for_attachment(db, workspace_id=W2.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [Z.id]`.

## `AttachmentMarkupEventDAO.create_event`

### AME-CE-01 — a row is created with the given values
- **Rules:** `create_event` R1, R2, Returns, Side effects
- **Kind:** happy
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_updated", description="Updated layer", session_id="sess-1", metadata_json={"shapes": 2})`.

**Then**
1. returns: `isinstance(result, AttachmentMarkupEvent)`.
2. returns: `result.id is not None`.
3. re-read result: `workspace_id == W1.id`, `attachment_id == AT1.id`, `user_id == U1.id`.
4. re-read result: `event_type == "markup_updated"`, `description == "Updated layer"`, `session_id == "sess-1"`.
5. re-read result: `metadata_json == {"shapes": 2}`.
6. count: `attachment_markup_events` has exactly 1 row with `attachment_id == AT1.id`.

### AME-CE-02 — under Asia/Dhaka created_at is the real moment in UTC, naive
- **Rules:** `create_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`

**When**
- `result = dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_saved", description="Saved")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `created_at.tzinfo is None`.
3. re-read result: `abs(UTC_CLOCK - created_at) < timedelta(seconds=5)`.

### AME-CE-03 — session_id and metadata_json default to None; None is stored as JSON null
- **Rules:** `create_event` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_saved", description="Saved")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `session_id is None`, `metadata_json is None`.
3. re-read result: `stored_json(result) == "null"`.
4. re-read result: `is_sql_null(result) is False`.

### AME-CE-04 — empty event type and description are stored
- **Rules:** `create_event` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="", description="")`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `event_type == ""`, `description == ""`.

### AME-CE-05 — a session_id of 37 characters raises DataError
- **Rules:** `create_event` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_saved", description="Saved", session_id="s" * 37)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22001"`.
2. nothing written: nothing written.

### AME-CE-06 — a session_id of 36 and an event type of 32 characters are stored
- **Rules:** `create_event` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `result = dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="e" * 32, description="Saved", session_id="s" * 36)`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `event_type == "e" * 32`, `session_id == "s" * 36`.

### AME-CE-07 — an event type of 33 characters raises DataError
- **Rules:** `create_event` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="e" * 33, description="Saved")`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "22001"`.
2. nothing written: nothing written.

### AME-CE-08 — description None raises IntegrityError 23502
- **Rules:** `create_event` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_saved", description=None)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. nothing written: nothing written.

### AME-CE-09 — an unknown attachment raises IntegrityError 23503
- **Rules:** `create_event` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, attachment_id=MISSING, user_id=U1.id, event_type="markup_saved", description="Saved")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### AME-CE-10 — an unknown user raises IntegrityError 23503
- **Rules:** `create_event` R3, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. No entry exists.

**When**
- `dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=MISSING, event_type="markup_saved", description="Saved")`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

### AME-CE-11 — flushed, not committed: a rollback removes the row
- **Rules:** `create_event` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No entry exists.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.create_event(db, workspace_id=W1.id, attachment_id=AT1.id, user_id=U1.id, event_type="markup_saved", description="Saved")`.

**Then**
1. returns: `result.id is not None`.
2. count: inside the savepoint, `attachment_markup_events` has exactly 1 row with `attachment_id == AT1.id`.
3. count: after the savepoint rollback, `attachment_markup_events` has 0 rows with `attachment_id == AT1.id`.
4. mock called: the `db.commit` spy was never called.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| P2 — the markup history endpoint answers 404 for a deleted attachment | `AttachmentMarkupManager.list_events` (`_get_ready_attachment`) | The DAO keeps R5 (AME-LA-12). |
| P1 — if a long history needs paging, it is added at the endpoint with HR-7 limits | the markup history endpoint | Not today. |
| `list_for_attachment`'s `limit` parameter — removed with the fix of BUG-1437 | `docs/testing/dead-code-removal-checklist.md` | Negative and zero `limit` get no card. |
| HR-16 — the manager passes an attachment it checked in the caller's workspace | `AttachmentMarkupManager._log_markup_event` | `create_event` stores what it is given. |
| Inherited `BaseDAO` methods; module singleton | `tests/unit/dao/base.cases.md` / none | No caller. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `create_event` R1 | "equal to the database's `now() AT TIME ZONE 'UTC'` within a second": `now()` is the transaction's start, which can be more than a second before the call. | AME-CE-02 uses `clock_timestamp()` and 5 seconds. |
| 2 | Externals | The import-bound `created_at` default cannot be patched by module name, so no card can fix its exact value. | Read cards give `created_at`; the default is checked by tolerance only. |
| 3 | Errors | The negative `limit` (`DataError` 2201W) and `limit=0` are stated as "not reachable", not as rules. | No card (Deferred). |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `list_for_attachment` | Returns | AME-LA-01 |
| `list_for_attachment` | R1 | AME-LA-01, AME-LA-02 |
| `list_for_attachment` | R2 | AME-LA-03, AME-LA-04, AME-LA-05, AME-LA-14 |
| `list_for_attachment` | R3 | AME-LA-06, AME-LA-07 |
| `list_for_attachment` | R3 [BUG-1436] | AME-LA-08, AME-LA-09 |
| `list_for_attachment` | R4 [BUG-1437] | AME-LA-10, AME-LA-11 |
| `list_for_attachment` | R5 | AME-LA-12 |
| `list_for_attachment` | Side effects | AME-LA-13 |
| `create_event` | Returns | AME-CE-01 |
| `create_event` | R1 | AME-CE-01, AME-CE-02 |
| `create_event` | R2 | AME-CE-01, AME-CE-03 |
| `create_event` | R3 | AME-CE-04, AME-CE-05, AME-CE-06, AME-CE-07, AME-CE-08, AME-CE-09, AME-CE-10 |
| `create_event` | R4 | AME-CE-11 |
| `create_event` | Errors | AME-CE-05, AME-CE-07, AME-CE-08, AME-CE-09, AME-CE-10 |
| `create_event` | Side effects | AME-CE-01, AME-CE-11 |
