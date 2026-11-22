# Test cases — `app/dao/attachment_ledger.py`

> **Spec:** `tests/unit/dao/attachment_ledger.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `attachment_ledger.verify.md` (case-missing Findings 1 … 6; recipes R-1 … R-7): R-1, R-2 → ATL-G-57 … ATL-G-63; R-3 → ATL-G-64 … ATL-G-71; R-4 → ATL-G-72; R-5 → ATL-G-73; R-6 → Conventions: ATD gains `deleted_by U1.id`; ATL-G-55's Given line says so; R-7 → ATL-G-42 now updates the higher id, B; its title and `Fails today on` parenthesis corrected (Finding 6). New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 73 cases · 64 expected-to-pass · 9 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_by_workspace` 73 (9 bug).
- **Depth:** lighter target (skill step 1a) for a plain filtered read, with full boundaries on the date rules R5, R6, R7, R7a, as asked.
- **Expected-to-fail:** BUG-1281 6, all strict: ATL-G-32, ATL-G-33, ATL-G-35, ATL-G-36, ATL-G-37, ATL-G-38. ATL-G-31, ATL-G-34 are the passing `UTC` companions. BUG-640 3: ATL-G-42, ATL-G-43 non-strict, ATL-G-44 strict (the SQL recorder). ATL-G-41 is the passing companion.
- **Commit spies:** none, the module has no writer of its own.
- **Notable design choices:**
  - Every time-zone card sets `SET LOCAL TIME ZONE` itself, and every stamp is an aware UTC value, as the spec's Notes ask.
  - The moment stands on 2026-03-05, the spec's own example, before the US clock change: New York is five hours behind UTC.
  - R7 has both bounds under all three zones, with a row one microsecond past the bound, so a fix that cuts the zone off fails.
  - ATL-G-53 and ATL-G-54 hold one decoy per filter; in the paging card each decoy sorts ahead of the skipped row.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** ATL-G-57 … ATL-G-71 hold R3 and R4 to an exact compare, on the argument side one value per card and on the stored side one card each; ATL-G-72 (the higher attachment id); ATL-G-73 (an unflushed edit stays unflushed); ATD carries `deleted_by`; ATL-G-42 updates the higher id.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `ATL` = `app/dao/attachment_ledger.py`. `G` get_by_workspace.

**Actors and fixed values.**
- `dao` = the singleton `attachment_ledger_dao` (`from app.dao.attachment_ledger import attachment_ledger_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `AttachmentLedger` = `app.models.attachment_ledger.AttachmentLedger`. `Attachment` = `app.models.attachment.Attachment`. `datetime`, `timedelta`, `timezone` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- H9 … H14 = `datetime(2026, 3, 5, h, 0, 0, tzinfo=timezone.utc)` with h = 9 … 14: aware UTC moments, before the US clock change. US = `timedelta(microseconds=1)`. P6 = `timezone(timedelta(hours=6))`, M5 = `timezone(timedelta(hours=-5))`. T12 = `datetime(2026, 3, 4, 12, 0, 0)`, naive.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - AT1 = `Attachment(workspace_id=W1.id, file_name="file.png", mime_type="image/png", file_size=100, uploaded_by=U1.id)`. AT2 = the same. AT9 = the same, but `workspace_id W2.id`. ATD = the same as AT1, but `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
- **entry** = `attachment_ledger` row built with `AttachmentLedger`: `workspace_id W1.id`, `attachment_id AT1.id`, `transaction_type "ready"`, `file_name "file.png"`, `mime_type "image/png"`, `file_size 100`, `entity_type "purchase_order"`; `entity_id`, `performed_by` are not passed. The card always gives `performed_at`; after the word "but" it lists every other column that differs. `entity_type None` means the keyword is passed with the value `None`.
- No `attachment_ledger` row exists unless the card's Given lists it.
- A time-zone line of a Given is the first statement of the test body after the standing rows; `SET LOCAL` ends with the rollback.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `attachment_ledger` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the call: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards (the savepoint is rolled back). Further `raises:` lines are assertions on `exc.value.orig`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-640, BUG-1281.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `attachment_ledger`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `AttachmentLedgerDAO.get_by_workspace`

### ATL-G-01 — returns a list of the workspace's entries, newest first
- **Rules:** `get_by_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.
2. B = entry, `performed_at H12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `isinstance(result[0], AttachmentLedger)`.

### ATL-G-02 — a newer entry of another workspace is not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.
2. B = entry, `performed_at H12`, but `workspace_id W2.id`, `attachment_id AT9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-03 — another workspace returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### ATL-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ATL-G-05 — attachment_id keeps that attachment's entries; a newer one of another attachment is not returned
- **Rules:** `get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.
2. B = entry, `performed_at H12`, but `attachment_id AT2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=AT1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-06 — attachment_id=0 is a real filter and returns an empty list
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=0)`.

**Then**
1. returns: `result == []`.

### ATL-G-07 — attachment_id=None applies no filter
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.
2. B = entry, `performed_at H12`, but `attachment_id AT2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=None)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### ATL-G-08 — an attachment of another workspace reaches nothing
- **Rules:** `get_by_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`, but `workspace_id W2.id`, `attachment_id AT9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=AT9.id)`.

**Then**
1. returns: `result == []`.

### ATL-G-09 — entity_type keeps exact matches: another value and NULL are left out
- **Rules:** `get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `entity_type "sales_order"`.
3. C = entry, `performed_at H12`, but `entity_type None`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="purchase_order")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-10 — entity_type=None applies no filter: a NULL row is kept
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `entity_type "sales_order"`.
3. C = entry, `performed_at H12`, but `entity_type None`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type=None)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### ATL-G-11 — entity_type="" applies no filter: a NULL row is kept
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `entity_type "sales_order"`.
3. C = entry, `performed_at H12`, but `entity_type None`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="")`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### ATL-G-12 — entity_type in another case returns an empty list
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `entity_type "sales_order"`.
3. C = entry, `performed_at H12`, but `entity_type None`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="PURCHASE_ORDER")`.

**Then**
1. returns: `result == []`.

### ATL-G-13 — an unknown entity_type returns an empty list
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `entity_type "sales_order"`.
3. C = entry, `performed_at H12`, but `entity_type None`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="nothing")`.

**Then**
1. returns: `result == []`.

### ATL-G-14 — transaction_type keeps exact matches
- **Rules:** `get_by_workspace` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `transaction_type "failed"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="ready")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-15 — transaction_type=None applies no filter
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `transaction_type "failed"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type=None)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### ATL-G-16 — transaction_type="" applies no filter
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `transaction_type "failed"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="")`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### ATL-G-17 — transaction_type in another case returns an empty list
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `transaction_type "failed"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="READY")`.

**Then**
1. returns: `result == []`.

### ATL-G-18 — an unknown transaction_type returns an empty list
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`, but `transaction_type "failed"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="nothing")`.

**Then**
1. returns: `result == []`.

### ATL-G-19 — start_date keeps the row at that moment and later; one microsecond before is left out
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12 - US`.
2. B = entry, `performed_at H12`.
3. C = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=H12)`.

**Then**
1. returns: `ids(result) == [C.id, B.id]`.

### ATL-G-20 — end_date keeps the row at that moment and earlier; one microsecond after is left out
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12 - US`.
2. B = entry, `performed_at H12`.
3. C = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=H12)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### ATL-G-21 — start_date equal to end_date keeps the rows at that moment only
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12 - US`.
2. B = entry, `performed_at H12`.
3. C = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=H12, end_date=H12)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### ATL-G-22 — start_date after end_date returns an empty list, with no error
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12 - US`.
2. B = entry, `performed_at H12`.
3. C = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=H13, end_date=H11)`.

**Then**
1. returns: `result == []`.

### ATL-G-23 — start_date one microsecond after end_date returns an empty list
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12 - US`.
2. B = entry, `performed_at H12`.
3. C = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=H12 + US, end_date=H12)`.

**Then**
1. returns: `result == []`.

### ATL-G-24 — a day apart: bounds compare the whole moment, not the time of day
- **Rules:** `get_by_workspace` R5, R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12 - timedelta(days=1)`.
2. B = entry, `performed_at H12`.
3. C = entry, `performed_at H12 + timedelta(days=1)`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=H11, end_date=H13)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### ATL-G-25 — end_date with a zone is an exact moment under UTC
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=datetime(2026, 3, 5, 18, 0, 0, tzinfo=P6))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-26 — end_date with a zone is an exact moment under Asia/Dhaka
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=datetime(2026, 3, 5, 18, 0, 0, tzinfo=P6))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-27 — end_date with a zone is an exact moment under America/New_York
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H12 + US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=datetime(2026, 3, 5, 18, 0, 0, tzinfo=P6))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-28 — start_date with a zone is an exact moment under UTC
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H12 - US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 5, 7, 0, 0, tzinfo=M5))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-29 — start_date with a zone is an exact moment under Asia/Dhaka
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H12 - US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 5, 7, 0, 0, tzinfo=M5))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-30 — start_date with a zone is an exact moment under America/New_York
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H12 - US`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 5, 7, 0, 0, tzinfo=M5))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-31 — a naive end_date means UTC, under UTC
- **Rules:** `get_by_workspace` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H13`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=datetime(2026, 3, 5, 12, 0, 0))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-32 — a naive end_date means UTC, under Asia/Dhaka
- **Rules:** `get_by_workspace` R7a [BUG-1281]
- **Kind:** bug
- **Expect:** xfail BUG-1281
- **Fails today on:** Then 1 (read as 12:00 Dhaka, 06:00 UTC, so neither entry is kept)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H13`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=datetime(2026, 3, 5, 12, 0, 0))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-33 — a naive end_date means UTC, under America/New_York
- **Rules:** `get_by_workspace` R7a [BUG-1281]
- **Kind:** bug
- **Expect:** xfail BUG-1281
- **Fails today on:** Then 1 (read as 12:00 New York, 17:00 UTC, so both entries are kept)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H13`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, end_date=datetime(2026, 3, 5, 12, 0, 0))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-34 — a naive start_date means UTC, under UTC
- **Rules:** `get_by_workspace` R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'UTC'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 5, 12, 0, 0))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-35 — a naive start_date means UTC, under Asia/Dhaka
- **Rules:** `get_by_workspace` R7a [BUG-1281]
- **Kind:** bug
- **Expect:** xfail BUG-1281
- **Fails today on:** Then 1 (read as 06:00 UTC, so both entries are kept)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 5, 12, 0, 0))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-36 — a naive start_date means UTC, under America/New_York
- **Rules:** `get_by_workspace` R7a [BUG-1281]
- **Kind:** bug
- **Expect:** xfail BUG-1281
- **Fails today on:** Then 1 (read as 17:00 UTC, so neither entry is kept)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'America/New_York'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 5, 12, 0, 0))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-37 — a naive start_date with an aware end_date: each bound keeps its own meaning
- **Rules:** `get_by_workspace` R7a [BUG-1281]
- **Kind:** bug
- **Expect:** xfail BUG-1281
- **Fails today on:** Then 1 (the naive start is read as 06:00 UTC, so both entries are kept)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H11`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=datetime(2026, 3, 5, 12, 0, 0), end_date=H12)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-38 — an aware start_date with a naive end_date: each bound keeps its own meaning
- **Rules:** `get_by_workspace` R7a [BUG-1281]
- **Kind:** bug
- **Expect:** xfail BUG-1281
- **Fails today on:** Then 1 (the naive end is read as 06:00 UTC, so no entry is kept)

**Given**
1. `db.execute(text("SET LOCAL TIME ZONE 'Asia/Dhaka'"))`
2. A = entry, `performed_at H12`.
3. B = entry, `performed_at H13`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, start_date=H12, end_date=datetime(2026, 3, 5, 12, 0, 0))`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-39 — entries are ordered by performed_at descending, against id and text
- **Rules:** `get_by_workspace` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12`, but `file_name "alpha.png"`.
2. B = entry, `performed_at H13`, but `file_name "zeta.png"`.
3. C = entry, `performed_at H11`, but `file_name "mid.png"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id, C.id]`.

### ATL-G-40 — one microsecond inside one day decides the order, against id
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12 + US`.
2. B = entry, `performed_at H12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### ATL-G-41 — on a tie both entries are returned, before the older one
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H12`.
2. B = entry, `performed_at H12`.
3. C = entry, `performed_at H11`.
4. `A.file_size = 200`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[2].id == C.id`.
3. returns: `{r.id for r in result[:2]} == {A.id, B.id}`.

### ATL-G-42 — on a tie the higher id comes first, when the higher id was updated
- **Rules:** `get_by_workspace` R8 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; the updated higher id moves after A in the heap, so physical order puts A first)

**Given**
1. A = entry, `performed_at H12`, but `file_name "zeta.png"`.
2. B = entry, `performed_at H12`, but `file_name "alpha.png"`.
3. `B.file_size = 200`, then `db.flush()`.
4. `db.expire_all()`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [B.id, A.id]`.

### ATL-G-43 — on a tie the higher id comes first, with no update
- **Rules:** `get_by_workspace` R8 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; today's order rests on physical row order)

**Given**
1. A = entry, `performed_at H12`, but `file_name "zeta.png"`.
2. B = entry, `performed_at H12`, but `file_name "alpha.png"`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [B.id, A.id]`.

### ATL-G-44 — the query orders by performed_at, then id, both descending
- **Rules:** `get_by_workspace` R8 [BUG-640]
- **Kind:** bug
- **Expect:** xfail BUG-640
- **Fails today on:** Then 3 (the query orders by `performed_at` alone)

**Given**
1. A = entry, `performed_at H12`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"performed_at DESC" in order_part`.
3. statement: `".id DESC" in order_part`.
4. statement: `order_part.index("performed_at") < order_part.index(".id")`.

### ATL-G-45 — with the default limit 105 rows give 100
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 105 entries E1 … E105, built with `add_all`: Ek = entry, `performed_at` = `H10 + timedelta(minutes=k)`. `in_order` = the ids of E105, E104, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == in_order[:100]`.

### ATL-G-46 — limit=1000 gives all 105 rows
- **Rules:** `get_by_workspace` R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 105 entries E1 … E105, built with `add_all`: Ek = entry, `performed_at` = `H10 + timedelta(minutes=k)`. `in_order` = the ids of E105, E104, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 105`.
2. returns: `ids(result) == in_order`.

### ATL-G-47 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`.
3. C = entry, `performed_at H12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### ATL-G-48 — skip past the end returns an empty list
- **Rules:** `get_by_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`.
3. C = entry, `performed_at H12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=3)`.

**Then**
1. returns: `result == []`.

### ATL-G-49 — a negative limit is refused by Postgres
- **Rules:** `get_by_workspace` R11, Errors row 1 (negative `limit`)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ATL-G-50 — a negative skip is refused by Postgres
- **Rules:** `get_by_workspace` R11, Errors row 2 (negative `skip`)
- **Kind:** error
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### ATL-G-51 — limit=1 returns the newest row: the other side of limit=0
- **Rules:** `get_by_workspace` R10, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`.
3. C = entry, `performed_at H12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### ATL-G-52 — skip=2 of three rows returns the oldest: the other side of skip past the end
- **Rules:** `get_by_workspace` R10, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`.
3. C = entry, `performed_at H12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-53 — all filters combine: a row failing any one of them is left out
- **Rules:** `get_by_workspace` R12
- **Kind:** happy
- **Expect:** pass

**Given**
1. M = entry, `performed_at H11`.
2. D1 = entry, `performed_at H12`, but `attachment_id AT2.id`.
3. D2 = entry, `performed_at H12`, but `entity_type "sales_order"`.
4. D3 = entry, `performed_at H12`, but `transaction_type "failed"`.
5. D4 = entry, `performed_at H14`.
6. D5 = entry, `performed_at H9`.
7. D6 = entry, `performed_at H12`, but `workspace_id W2.id`, `attachment_id AT9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=AT1.id, entity_type="purchase_order", transaction_type="ready", start_date=H10, end_date=H13)`.

**Then**
1. returns: `ids(result) == [M.id]`.

### ATL-G-54 — filters apply before skip and limit: hidden rows that sort first use up no skip
- **Rules:** `get_by_workspace` R12, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M1 = entry, `performed_at H10`.
2. M2 = entry, `performed_at H11`.
3. D1 = entry, `performed_at H12`, but `attachment_id AT2.id`.
4. D2 = entry, `performed_at H12`, but `entity_type "sales_order"`.
5. D3 = entry, `performed_at H12`, but `transaction_type "failed"`.
6. D4 = entry, `performed_at H14`.
7. D6 = entry, `performed_at H12`, but `workspace_id W2.id`, `attachment_id AT9.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=AT1.id, entity_type="purchase_order", transaction_type="ready", start_date=H10, end_date=H13, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [M1.id]`.

### ATL-G-55 — every entry of a soft-deleted attachment is returned
- **Rules:** `get_by_workspace` R13
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Attachment ATD has `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`: it is a standing row.
2. A = entry, `performed_at H10`, but `attachment_id ATD.id`, `transaction_type "pending"`.
3. B = entry, `performed_at H11`, but `attachment_id ATD.id`, `transaction_type "ready"`.
4. C = entry, `performed_at H12`, but `attachment_id ATD.id`, `transaction_type "deleted"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=ATD.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### ATL-G-56 — writes nothing: a newer pending row stays pending and alone in the session
- **Rules:** `get_by_workspace` Side effects, R13
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`.
2. `P = AttachmentLedger(workspace_id=W1.id, attachment_id=AT1.id, transaction_type="ready", file_name="file.png", mime_type="image/png", file_size=100, performed_at=H12)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. statement: `"attachments" not in sql`.
11. nothing written: nothing written.
12. unchanged: unchanged(A).

### ATL-G-57 — entity_type=" purchase_order" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type=" purchase_order")`.

**Then**
1. returns: `result == []`.

### ATL-G-58 — entity_type="purchase_order " returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="purchase_order ")`.

**Then**
1. returns: `result == []`.

### ATL-G-59 — entity_type="purchase" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="purchase")`.

**Then**
1. returns: `result == []`.

### ATL-G-60 — entity_type="order" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="order")`.

**Then**
1. returns: `result == []`.

### ATL-G-61 — entity_type="purchase%" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="purchase%")`.

**Then**
1. returns: `result == []`.

### ATL-G-62 — entity_type="purchase_orde_" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="purchase_orde_")`.

**Then**
1. returns: `result == []`.

### ATL-G-63 — entity_type matches the stored value exactly: case, spaces, longer values and look-alikes are left out
- **Rules:** `get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M = entry, `performed_at H10`.
2. D1 = entry, `performed_at H11`, but `entity_type "PURCHASE_ORDER"`.
3. D2 = entry, `performed_at H11`, but `entity_type " purchase_order"`.
4. D3 = entry, `performed_at H11`, but `entity_type "purchase_order "`.
5. D4 = entry, `performed_at H11`, but `entity_type "purchase_orderX"`.
6. D5 = entry, `performed_at H11`, but `entity_type "Xpurchase_order"`.
7. D6 = entry, `performed_at H11`, but `entity_type "purchaseXorder"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, entity_type="purchase_order")`.

**Then**
1. returns: `ids(result) == [M.id]`.

### ATL-G-64 — transaction_type=" ready" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type=" ready")`.

**Then**
1. returns: `result == []`.

### ATL-G-65 — transaction_type="ready " returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="ready ")`.

**Then**
1. returns: `result == []`.

### ATL-G-66 — transaction_type="rea" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="rea")`.

**Then**
1. returns: `result == []`.

### ATL-G-67 — transaction_type="dy" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="dy")`.

**Then**
1. returns: `result == []`.

### ATL-G-68 — transaction_type="rea%" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="rea%")`.

**Then**
1. returns: `result == []`.

### ATL-G-69 — transaction_type="r_ady" returns an empty list: the compare is exact
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="r_ady")`.

**Then**
1. returns: `result == []`.

### ATL-G-70 — transaction_type matches the stored value exactly: case, spaces and longer values are left out
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. M = entry, `performed_at H10`.
2. D1 = entry, `performed_at H11`, but `transaction_type "READY"`.
3. D2 = entry, `performed_at H11`, but `transaction_type " ready"`.
4. D3 = entry, `performed_at H11`, but `transaction_type "ready "`.
5. D4 = entry, `performed_at H11`, but `transaction_type "readyX"`.
6. D5 = entry, `performed_at H11`, but `transaction_type "Xready"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="ready")`.

**Then**
1. returns: `ids(result) == [M.id]`.

### ATL-G-71 — an underscore in transaction_type is a plain character
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`, but `transaction_type "pendingX"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, transaction_type="pending_")`.

**Then**
1. returns: `result == []`.

### ATL-G-72 — attachment_id keeps the higher attachment's entries; an entry of the lower attachment is not returned
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = entry, `performed_at H11`, but `attachment_id AT2.id`.
2. B = entry, `performed_at H12`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, attachment_id=AT2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### ATL-G-73 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = entry, `performed_at H10`.
2. B = entry, `performed_at H11`.
3. `B.file_name = "edited.png"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.file_name == "edited.png"`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_workspace` R8 — BUG-640, the other ledger lists | `LedgerManager` | The manager's cards carry them; for attachments the line to fix is this DAO. |
| Review, HR-7 — BUG-642: `GET /ledgers/attachments/` requires `limit >= 1` | `GET /ledgers/attachments/` | The DAO's `limit=0` and negative rules stand. |
| Review — BUG-991: `end_date` as a plain date becomes midnight | `GET /ledgers/attachments/` | It happens at the endpoint, before this DAO. |
| Overview — rows are written through inherited `create` | `AttachmentManager._append_attachment_ledger` | Append-only is a convention; nothing in the database enforces it. |
| Inherited `BaseDAO` methods | `tests/unit/dao/base.spec.md` | This DAO overrides `get_by_workspace`; the rest is generic. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | `get_by_workspace` R13 | The spec names no soft-delete column for an attachment. `is_deleted`, `deleted_at` come from the wording of `machine_maintenance_log.spec.md` Q on `soft_delete`; `deleted_by` is not known. | The ATD row uses those two. **Closed in revision 1:** `deleted_by` added from `attachment_ledger.verify.md` Finding 5. |
| 2 | `get_by_workspace` R3, R4 | The spec gives no sample value for `entity_type`, `transaction_type`. `"purchase_order"`, `"sales_order"` follow `AttachmentEntityTypeEnum` as tests use it; `"pending"`, `"ready"`, `"failed"`, `"deleted"` follow the Overview. The columns are plain strings, and the rules are exact matches. | Conventions use them. |
| 3 | `get_by_workspace` R7a | The spec's Today note lists one bound at a time. ATL-G-37, ATL-G-38 mix a naive and an aware bound; they follow from the same note. | Designed; say so if a fix should not be held to them. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_workspace` | Returns | ATL-G-01 |
| `get_by_workspace` | R1 | ATL-G-01, ATL-G-02, ATL-G-03, ATL-G-04 |
| `get_by_workspace` | R2 | ATL-G-05, ATL-G-06, ATL-G-07, ATL-G-08, ATL-G-72 |
| `get_by_workspace` | R3 | ATL-G-09, ATL-G-10, ATL-G-11, ATL-G-12, ATL-G-13, ATL-G-57, ATL-G-58, ATL-G-59, ATL-G-60, ATL-G-61, ATL-G-62, ATL-G-63 |
| `get_by_workspace` | R4 | ATL-G-14, ATL-G-15, ATL-G-16, ATL-G-17, ATL-G-18, ATL-G-64, ATL-G-65, ATL-G-66, ATL-G-67, ATL-G-68, ATL-G-69, ATL-G-70, ATL-G-71 |
| `get_by_workspace` | R5 | ATL-G-19, ATL-G-24 |
| `get_by_workspace` | R6 | ATL-G-20, ATL-G-21, ATL-G-22, ATL-G-23, ATL-G-24 |
| `get_by_workspace` | R7 | ATL-G-25, ATL-G-26, ATL-G-27, ATL-G-28, ATL-G-29, ATL-G-30 |
| `get_by_workspace` | R7a | ATL-G-31, ATL-G-34 |
| `get_by_workspace` | R7a [BUG-1281] | ATL-G-32, ATL-G-33, ATL-G-35, ATL-G-36, ATL-G-37, ATL-G-38 |
| `get_by_workspace` | R8 | ATL-G-39, ATL-G-40, ATL-G-41, ATL-G-51, ATL-G-52, ATL-G-54 |
| `get_by_workspace` | R8 [BUG-640] | ATL-G-42, ATL-G-43, ATL-G-44 |
| `get_by_workspace` | R9 | ATL-G-45, ATL-G-46 |
| `get_by_workspace` | R10 | ATL-G-47, ATL-G-48, ATL-G-51, ATL-G-52 |
| `get_by_workspace` | R11 | ATL-G-49, ATL-G-50 |
| `get_by_workspace` | R12 | ATL-G-53, ATL-G-54 |
| `get_by_workspace` | R13 | ATL-G-55, ATL-G-56 |
| `get_by_workspace` | Errors row 1 (negative `limit`) | ATL-G-49 |
| `get_by_workspace` | Errors row 2 (negative `skip`) | ATL-G-50 |
| `get_by_workspace` | Side effects | ATL-G-56, ATL-G-73 |
