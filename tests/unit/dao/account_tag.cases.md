# Test cases — `app/dao/account_tag.py`

> **Spec:** `tests/unit/dao/account_tag.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1–P5 were decided by Claude under the reviewer's delegation, each by the matching item tag DAO decision.
> **Revision:** 2 — spec Gap log G1 (inherited R5 split; new R6: ORM `remove` of a tag with an assignment raises 23502, nothing deleted; a tag with no assignment is removed; SQL `DELETE` cascades). ATG-INH-06 now expects 23502 and cites R6; new ATG-INH-07 (unreferenced tag removed), ATG-INH-08 (SQL `DELETE` cascades). No ID retired.
> **Revision:** 3 — `account_tag.verify.md` T-1, T-2 (case-missing): new ATG-CODE-14 (trailing space on the argument), ATG-CODE-15 (`_` in the stored code); one Then line `"DESC" not in order_part.upper()` added to ATG-SYS-07. No ID retired.
> **Counts:** 61 cases · 51 expected-to-pass · 10 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `get_by_tag_code_in_workspace` 15 · `get_active_tags_in_workspace` 10 (4 bug) · `get_system_tags_in_workspace` 8 (3 bug) · `increment_usage_count` 9 (1 bug) · `decrement_usage_count` 11 (2 bug) · inherited 8.
- **Depth:** lighter target (skill step 1a). Tag labels and a usage counter; no stock, money or order state. The 1b shapes are applied once per query; exact-compare cards on the code lookup cover a part, `%`, `_`, capitals and a leading space on the argument side, capitals and a leading space on the stored side.
- **Expected-to-fail:** BUG-1482 5 (ACT-07, ACT-08, SYS-06 non-strict; ACT-09, SYS-07 strict SQL recorders) · BUG-1483 1 strict (SYS-05) · BUG-1485 1 strict (ACT-05; ACT-06 is the passing companion: a deleted tag ahead of 100 active ones) · BUG-1484 3 strict (INC-06, DEC-08, DEC-09; INC-07 is the passing control with the object expired).
- **Commit spies:** `increment_usage_count` 1 (INC-09) · `decrement_usage_count` 1 (DEC-11).
- **Notable design choices:**
  - A deleted **system** tag is used where a rule says "a deleted tag and a system tag are treated like any other" (INC-04, DEC-07): a filter added on either flag drops it, so one card catches both.
  - Generic base behavior (paging, `get_multi`, BUG-100 order) is not repeated: Deferred to `base.cases.md`.
- **Needs a decision:** None blocking. See Spec gaps 1 (schema module and fields assumed), 2 (case-insensitive key in the recorder cards).

## Conventions for this module

**IDs.** `ATG` = `app/dao/account_tag.py`. `CODE` get_by_tag_code_in_workspace · `ACT` get_active_tags_in_workspace · `SYS` get_system_tags_in_workspace · `INC` increment_usage_count · `DEC` decrement_usage_count · `INH` inherited `BaseDAO` methods.

**Names.**
- `dao` = the singleton `account_tag_dao` (`from app.dao.account_tag import account_tag_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `AccountTag` = `app.models.account_tag.AccountTag`. `Account` = `app.models.account.Account`. `AccountTagAssignment` = `app.models.account_tag_assignment.AccountTagAssignment`. `AccountTagCreate`, `AccountTagUpdate` = schemas of `app.schemas.account_tag` (Spec gap 1). `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `select`, `text` = `sqlalchemy.select`, `sqlalchemy.text`.
- W1, W2 = two `workspaces` rows (`make_workspace`); they exist in every test and need no Given line. MISSING = `999999999`: an id no row of any table has.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- **tag** = `AccountTag(workspace_id=W1.id, is_system_tag=False, is_active=True, usage_count=0)`; the card always gives `name` and `tag_code`; after "but" it lists every other column that differs. **system tag** = a tag, but `is_system_tag True`. **deleted** = `is_active False`. No tag exists unless the Given lists it.
- **bumpT(X)** = `db.execute(text("UPDATE account_tags SET description = coalesce(description, '') || '!' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.
- A Given line written as code is a step to run exactly as written, at that place. A change without `db.flush()` stays pending.

**Named checks.**
- **ids(result)** = `[t.id for t in result]`, **names(result)** = `[t.name for t in result]` — in the order returned. `sorted(ids(result)) == [...]` is used where the order is not part of the check; the right side is in Given order (ascending ids).
- **stored_count(T)** = `db.scalar(select(AccountTag.usage_count).where(AccountTag.id == T.id))` — the database value, without expiring T.
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values (expiring discards unflushed changes).
- **unchanged(X)** = after re-read, every column of X equals its value before the call.
- **nothing written** = the number of `account_tags` rows (all workspaces) equals its value before the call.
- `pending:` lines check the session after the call, before anything expires it; they come before `nothing written:` lines.
- `raises: IntegrityError` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Stored value changed behind the object.** `db.execute(text("UPDATE account_tags SET usage_count = <n> WHERE id = :i"), {"i": T1.id})` after T1 was flushed, without expiring T1: the object keeps its old `usage_count`. One session, never a second connection.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `account_tags`; `order_part` = the text of `sql` after `ORDER BY` (`""` when there is none); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`; `updates` = every recorded `UPDATE`.

**Relative update** (BUG-1484). An `UPDATE` of `account_tags` whose `SET` computes the counter from the stored column (`usage_count = usage_count + ...` or `usage_count - ...`); for the decrease the same statement's `WHERE` also tests the stored column (`usage_count >`).

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. The assertion is never weakened.

**Externals.** None. Nothing is mocked. **Race simulations.** None.

## `AccountTagDAO.get_by_tag_code_in_workspace`

### ATG-CODE-01 — returns the workspace's tag with that code
- **Rules:** `get_by_tag_code_in_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `isinstance(result, AccountTag)`.
2. returns: `result.id == T1.id`.

### ATG-CODE-02 — another workspace's tags with that code, before and after by id, are never returned
- **Rules:** `get_by_tag_code_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`.
2. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
3. Z2 = tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result.id == T1.id`.

### ATG-CODE-03 — a code that exists only in another workspace returns None
- **Rules:** `get_by_tag_code_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Vendor"`, `tag_code "vendor"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="vendor")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-04 — an unknown workspace returns None
- **Rules:** `get_by_tag_code_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=MISSING, tag_code="supplier")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-05 — argument with capitals returns None
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="Supplier")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-06 — argument with a leading space returns None
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code=" supplier")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-07 — a part of the code returns None
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="sup")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-08 — "sup%" is not a pattern
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="sup%")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-09 — "s_pplier" is not a pattern
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="s_pplier")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-10 — a code of None returns None
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code=None)`.

**Then**
1. returns: `result is None`.

### ATG-CODE-11 — stored side: capitals or a leading space in the stored code are not matched by the plain code
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier A"`, `tag_code "Supplier"`.
2. T2 = tag, `name "Supplier B"`, `tag_code " supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-12 — a deleted tag and a system tag are found by their codes
- **Rules:** `get_by_tag_code_in_workspace` R3 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = system tag, `name "Vendor"`, `tag_code "vendor"`, but `is_active False`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="vendor")`.

**Then**
1. returns: `result.id == TD.id`.
2. returns: `result.is_active is False`.

### ATG-CODE-13 — two tags with one code: one of them; the read writes nothing
- **Rules:** `get_by_tag_code_in_workspace` R4, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Bank A"`, `tag_code "bank"`.
2. T2 = tag, `name "Bank B"`, `tag_code "bank"`.
3. `T2.name = "Bank Edited"` (not flushed).
4. `P = AccountTag(workspace_id=W1.id, name="Pending", tag_code="bank", is_system_tag=False, is_active=True, usage_count=0)`, then `db.add(P)` (not flushed).

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="bank")`.

**Then**
1. returns: `result.id in {T1.id, T2.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `T2 in db.dirty`.
5. pending: `len(db.dirty) == 1`.

### ATG-CODE-14 — argument with a trailing space returns None
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="supplier ")`.

**Then**
1. returns: `result is None`.

### ATG-CODE-15 — stored side: "_" in the stored code is not a wildcard
- **Rules:** `get_by_tag_code_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "s_pplier"`.

**When**
- `result = dao.get_by_tag_code_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result is None`.

## `AccountTagDAO.get_active_tags_in_workspace`

### ATG-ACT-01 — returns a list of the workspace's active system and user tags
- **Rules:** `get_active_tags_in_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. S1 = system tag, `name "Client"`, `tag_code "client"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [T1.id, S1.id]`.
3. returns: `isinstance(result[0], AccountTag)`.

### ATG-ACT-02 — deleted user and system tags are not returned
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = tag, `name "Old"`, `tag_code "old"`, but `is_active False`.
2. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
3. SD = system tag, `name "Seed"`, `tag_code "seed"`, but `is_active False`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.

### ATG-ACT-03 — another workspace's tags are not returned
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`.
2. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.

### ATG-ACT-04 — an unknown workspace returns an empty list
- **Rules:** `get_active_tags_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ATG-ACT-05 — every active tag is returned: 101 give 101
- **Rules:** `get_active_tags_in_workspace` R2 [BUG-1485]
- **Kind:** bug
- **Expect:** xfail BUG-1485
- **Fails today on:** Then 2 (at most 100 are returned)

**Given**
1. 101 tags N1 … N101, built with `add_all` and flushed: Nk = tag, `name` = `f"Tag {k:03d}"`, `tag_code` = `f"tag_{k:03d}"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `len(result) == 101`.

### ATG-ACT-06 — a deleted tag ahead of 100 active ones does not take a place
- **Rules:** `get_active_tags_in_workspace` R1, R2 (filter before the cap; holds today and after the fix)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TD = system tag, `name "Aaa"`, `tag_code "aaa"`, but `is_active False`.
2. 100 tags N1 … N100, built with `add_all` and flushed: Nk = tag, `name` = `f"Tag {k:03d}"`, `tag_code` = `f"tag_{k:03d}"`.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `TD.id not in ids(result)`.

### ATG-ACT-07 — every system tag comes before every user tag
- **Rules:** `get_active_tags_in_workspace` R3 [BUG-1482]
- **Kind:** bug
- **Expect:** xfail BUG-1482 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; the system tag, highest id and updated, usually comes last)

**Given**
1. T1 = tag, `name "Alpha"`, `tag_code "alpha"`.
2. T2 = tag, `name "Bravo"`, `tag_code "bravo"`.
3. S1 = system tag, `name "Zed"`, `tag_code "zed"`.
4. seqscan.
5. bumpT(S1).

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, T2.id, S1.id]`.
2. returns: `ids(result) == [S1.id, T1.id, T2.id]`.

### ATG-ACT-08 — within a group: name case-insensitive, then id
- **Rules:** `get_active_tags_in_workspace` R4 [BUG-1482]
- **Kind:** bug
- **Expect:** xfail BUG-1482 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical order after the update)

**Given**
1. T1 = tag, `name "bravo"`, `tag_code "bravo"`.
2. T2 = tag, `name "Alpha"`, `tag_code "alpha_upper"`.
3. T3 = tag, `name "alpha"`, `tag_code "alpha_lower"`.
4. T4 = tag, `name "Charlie"`, `tag_code "charlie"`.
5. seqscan.
6. bumpT(T2).

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, T2.id, T3.id, T4.id]`.
2. returns: `ids(result) == [T2.id, T3.id, T1.id, T4.id]`.

### ATG-ACT-09 — the query orders by system first, then name case-insensitive, then id
- **Rules:** `get_active_tags_in_workspace` R3, R4 [BUG-1482]
- **Kind:** bug
- **Expect:** xfail BUG-1482
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"account_tags.is_system_tag DESC" in order_part`.
4. statement: `"lower(account_tags.name)" in order_part`.
5. statement: `"account_tags.id" in order_part`.

### ATG-ACT-10 — the read writes nothing and keeps the caller's pending changes
- **Rules:** `get_active_tags_in_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`, but `workspace_id W2.id`.
3. `T2.name = "Client Edited"` (not flushed).
4. `P = AccountTag(workspace_id=W1.id, name="Pending", tag_code="pending", is_system_tag=False, is_active=True, usage_count=0)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_active_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `T2 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

## `AccountTagDAO.get_system_tags_in_workspace`

### ATG-SYS-01 — returns a list of the workspace's system tags, no user tag
- **Rules:** `get_system_tags_in_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Custom"`, `tag_code "custom"`.
3. S3 = system tag, `name "Client"`, `tag_code "client"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [S1.id, S3.id]`.
3. returns: `isinstance(result[0], AccountTag)`.

### ATG-SYS-02 — another workspace's system tags are not returned
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = system tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`.
2. S1 = system tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.

### ATG-SYS-03 — an unknown workspace returns an empty list
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ATG-SYS-04 — no limit: 101 system tags give 101
- **Rules:** `get_system_tags_in_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 system tags N1 … N101, built with `add_all` and flushed: Nk = system tag, `name` = `f"Seed {k:03d}"`, `tag_code` = `f"seed_{k:03d}"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.

### ATG-SYS-05 — a deleted system tag is not returned
- **Rules:** `get_system_tags_in_workspace` R2 [BUG-1483]
- **Kind:** bug
- **Expect:** xfail BUG-1483
- **Fails today on:** Then 2 (the deleted system tag is returned)

**Given**
1. SD = system tag, `name "Old Seed"`, `tag_code "old_seed"`, but `is_active False`.
2. S1 = system tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `S1.id in ids(result)`.
2. returns: `ids(result) == [S1.id]`.

### ATG-SYS-06 — ordered by name case-insensitive, then id
- **Rules:** `get_system_tags_in_workspace` R3 [BUG-1482]
- **Kind:** bug
- **Expect:** xfail BUG-1482 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical order)

**Given**
1. S1 = system tag, `name "Utility"`, `tag_code "utility"`.
2. S2 = system tag, `name "client"`, `tag_code "client"`.
3. S3 = system tag, `name "Bank"`, `tag_code "bank"`.
4. seqscan.
5. bumpT(S3).

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [S1.id, S2.id, S3.id]`.
2. returns: `names(result) == ["Bank", "client", "Utility"]`.

### ATG-SYS-07 — the query orders by name case-insensitive, then id
- **Rules:** `get_system_tags_in_workspace` R3 [BUG-1482]
- **Kind:** bug
- **Expect:** xfail BUG-1482
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. S1 = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"lower(account_tags.name)" in order_part`.
4. statement: `"account_tags.id" in order_part`.
5. statement: `"DESC" not in order_part.upper()`.

### ATG-SYS-08 — the read writes nothing and keeps the caller's pending changes
- **Rules:** `get_system_tags_in_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. S1 = system tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. `T2.name = "Client Edited"` (not flushed).
4. `P = AccountTag(workspace_id=W1.id, name="Pending", tag_code="pending", is_system_tag=True, is_active=True, usage_count=0)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_system_tags_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [S1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `T2 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

## `AccountTagDAO.increment_usage_count`

### ATG-INC-01 — the counter goes up by one, flushed, and the session's object is returned
- **Rules:** `increment_usage_count` R1, R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. T2 = tag, `name "Client"`, `tag_code "client"`, but `usage_count 2`.

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 3`.
3. returns: `stored_count(T1) == 3`.
4. unchanged: unchanged(T2).
5. nothing written: nothing written.

### ATG-INC-02 — an unknown id returns None and writes nothing
- **Rules:** `increment_usage_count` R2 (P4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.

**When**
- `result = dao.increment_usage_count(db, tag_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(T1).

### ATG-INC-03 — another workspace's tag returns None and its counter stays
- **Rules:** `increment_usage_count` R2 (P4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`, `usage_count 5`.

**When**
- `result = dao.increment_usage_count(db, tag_id=Z1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. returns: `stored_count(Z1) == 5`.

### ATG-INC-04 — a deleted system tag is counted like any other
- **Rules:** `increment_usage_count` R3 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = system tag, `name "Old"`, `tag_code "old"`, but `is_active False`, `usage_count 0`.

**When**
- `result = dao.increment_usage_count(db, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is TD`.
2. re-read TD: `usage_count == 1`.
3. re-read TD: `is_active is False`, `is_system_tag is True`.

### ATG-INC-05 — a negative stored counter goes up by one
- **Rules:** `increment_usage_count` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count -2`.

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `usage_count == -1`.

### ATG-INC-06 — the increase applies to the stored value, not the loaded one
- **Rules:** `increment_usage_count` R5 [BUG-1484]
- **Kind:** bug
- **Expect:** xfail BUG-1484
- **Fails today on:** Then 2 (the loaded value is used: `result.usage_count` is 4, not 11)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. `db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": T1.id})` — T1 is not expired.

**When**
- with the statement recorder: `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 11` (read on the object, before any re-read).
3. returns: `stored_count(T1) == 11`.
4. sql: one of `updates` is a relative update that adds (`usage_count + ...`).

### ATG-INC-07 — with the object expired first, the increase starts from the stored value
- **Rules:** `increment_usage_count` R5 (control that holds today), R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. `db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": T1.id})`
3. `db.expire(T1)`

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `stored_count(T1) == 11`.

### ATG-INC-08 — the flush also saves another pending change of the session
- **Rules:** `increment_usage_count` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. `T1.name = "Suppliers"` (not flushed).

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `name == "Suppliers"`.
3. re-read T1: `usage_count == 3`.

### ATG-INC-09 — flushed, not committed: a rollback restores the old value
- **Rules:** `increment_usage_count` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.increment_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: inside the savepoint, `stored_count(T1) == 3`.
3. re-read T1 after the savepoint rollback: `usage_count == 2`.
4. mock called: the `db.commit` spy was never called.

## `AccountTagDAO.decrement_usage_count`

### ATG-DEC-01 — the counter goes down by one, flushed, and the tag is returned
- **Rules:** `decrement_usage_count` R1, R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. T2 = tag, `name "Client"`, `tag_code "client"`, but `usage_count 3`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 2`.
3. returns: `stored_count(T1) == 2`.
4. unchanged: unchanged(T2).

### ATG-DEC-02 — a counter of 1 becomes 0
- **Rules:** `decrement_usage_count` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 1`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `usage_count == 0`.

### ATG-DEC-03 — at 0 nothing is written or flushed and the tag is returned with 0
- **Rules:** `decrement_usage_count` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`. (`usage_count 0`.)
2. `T1.name = "Suppliers"` (not flushed).

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 0`.
3. re-read T1: `name == "Supplier"`.
4. re-read T1: `usage_count == 0`.

### ATG-DEC-04 — a negative stored counter is left as it is
- **Rules:** `decrement_usage_count` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count -2`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == -2`.
3. re-read T1: `usage_count == -2`.

### ATG-DEC-05 — an unknown id returns None and writes nothing
- **Rules:** `decrement_usage_count` R4 (P4)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. unchanged: unchanged(T1).

### ATG-DEC-06 — another workspace's tag returns None and its counter stays
- **Rules:** `decrement_usage_count` R4 (P4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`, `usage_count 5`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=Z1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. returns: `stored_count(Z1) == 5`.

### ATG-DEC-07 — a deleted system tag is decremented like any other
- **Rules:** `decrement_usage_count` R5 (P2)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. TD = system tag, `name "Old"`, `tag_code "old"`, but `is_active False`, `usage_count 2`.

**When**
- `result = dao.decrement_usage_count(db, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is TD`.
2. re-read TD: `usage_count == 1`.

### ATG-DEC-08 — the decrease applies to the stored value, not the loaded one
- **Rules:** `decrement_usage_count` R6 [BUG-1484]
- **Kind:** bug
- **Expect:** xfail BUG-1484
- **Fails today on:** Then 2 (the loaded value is used: `result.usage_count` is 2, not 9)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. `db.execute(text("UPDATE account_tags SET usage_count = 10 WHERE id = :i"), {"i": T1.id})` — T1 is not expired.

**When**
- with the statement recorder: `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 9` (read on the object, before any re-read).
3. returns: `stored_count(T1) == 9`.
4. sql: one of `updates` is a relative update that subtracts (`usage_count - ...`) and its `WHERE` tests `usage_count >`.

### ATG-DEC-09 — the "not below 0" check uses the stored value: stored 0 stays 0
- **Rules:** `decrement_usage_count` R6 [BUG-1484]
- **Kind:** bug
- **Expect:** xfail BUG-1484
- **Fails today on:** Then 2 (the loaded 3 passes the check: `result.usage_count` is 2, not 0)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. `db.execute(text("UPDATE account_tags SET usage_count = 0 WHERE id = :i"), {"i": T1.id})` — T1 is not expired.

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: `result.usage_count == 0` (read on the object, before any re-read).
3. returns: `stored_count(T1) == 0`.

### ATG-DEC-10 — when written, the flush also saves another pending change
- **Rules:** `decrement_usage_count` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. `T1.name = "Suppliers"` (not flushed).

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. re-read T1: `name == "Suppliers"`.
3. re-read T1: `usage_count == 2`.

### ATG-DEC-11 — flushed, not committed: a rollback restores the old value
- **Rules:** `decrement_usage_count` R7
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.decrement_usage_count(db, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is T1`.
2. returns: inside the savepoint, `stored_count(T1) == 2`.
3. re-read T1 after the savepoint rollback: `usage_count == 3`.
4. mock called: the `db.commit` spy was never called.

## Inherited `BaseDAO` methods on `AccountTag`

### ATG-INH-01 — create with a dict stores a tag with the model defaults
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Supplier", "tag_code": "supplier"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `name == "Supplier"`, `tag_code == "supplier"`.
3. re-read result: `is_system_tag is False`, `is_active is True`, `usage_count == 0`.
4. re-read result: `created_by is None`, `color is None`, `icon is None`, `description is None`.
5. re-read result: `created_at is not None`.

### ATG-INH-02 — create with an AccountTagCreate fails on flush (no workspace_id) and saves nothing
- **Rules:** inherited R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No tag exists.

**When**
- `dao.create(db, obj_in=AccountTagCreate(name="Supplier", tag_code="supplier"))`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. raises: `'column "workspace_id"' in str(exc.value.orig)`.
3. nothing written: nothing written.

### ATG-INH-03 — create checks no uniqueness: a second tag with the same name and code is saved
- **Rules:** inherited R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Supplier", "tag_code": "supplier"})`.

**Then**
1. returns: `result.id != T1.id`.
2. count: `account_tags` rows with `workspace_id == W1.id` and `tag_code == "supplier"`: exactly 2.

### ATG-INH-04 — update with an AccountTagUpdate applies only the fields set to a value
- **Rules:** inherited R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `color "#AA3300"`.

**When**
- `result = dao.update(db, db_obj=T1, obj_in=AccountTagUpdate(name="Suppliers", color=None))`.

**Then**
1. returns: `result.id == T1.id`.
2. re-read T1: `name == "Suppliers"`.
3. re-read T1: `color == "#AA3300"`.

### ATG-INH-05 — update with {"is_active": False} deletes the tag; the raw lookup still finds it
- **Rules:** inherited R3, R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.update(db, db_obj=T1, obj_in={"is_active": False})`.

**Then**
1. returns: `result.id == T1.id`.
2. re-read T1: `is_active is False`.
3. returns: `dao.get_by_id_and_workspace(db, id=T1.id, workspace_id=W1.id).id == T1.id` (the raw lookup still finds it).

### ATG-INH-06 — remove of a tag with an assignment raises 23502 and deletes nothing
- **Rules:** inherited R6
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = `Account(workspace_id=W1.id, name="Acme")`.
3. L1 = `AccountTagAssignment(workspace_id=W1.id, account_id=A1.id, tag_id=T1.id)`.
4. `t1_id = T1.id`

**When**
- `dao.remove(db, id=t1_id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. count: `account_tags` rows with `id == t1_id`: exactly 1.
3. count: `account_tag_assignments` rows with `tag_id == t1_id`: exactly 1.

### ATG-INH-07 — remove of a tag with no assignment deletes it and returns it
- **Rules:** inherited R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. `t1_id = T1.id`

**When**
- `result = dao.remove(db, id=t1_id)`.

**Then**
1. returns: `result.id == t1_id`.
2. count: `account_tags` rows with `id == t1_id`: exactly 0.
3. count: `account_tags` rows with `id == T2.id`: exactly 1.

### ATG-INH-08 — a SQL DELETE of a tag cascades to its assignments
- **Rules:** inherited R6 (database side)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = `Account(workspace_id=W1.id, name="Acme")`.
3. L1 = `AccountTagAssignment(workspace_id=W1.id, account_id=A1.id, tag_id=T1.id)`.
4. `t1_id = T1.id`

**When**
- `db.execute(text("DELETE FROM account_tags WHERE id = :i"), {"i": t1_id})`.

**Then**
1. count: `account_tags` rows with `id == t1_id`: exactly 0.
2. count: `account_tag_assignments` rows with `tag_id == t1_id`: exactly 0.
3. count: `accounts` rows with `id == A1.id`: exactly 1.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a)–(f) — duplicate check through the raw lookup, no unique index, names never checked, no code pattern, edit / delete of a deleted tag, use of `/account-tags/system/` | account tag service spec (not yet described) | Here the lookup finds a deleted tag (ATG-CODE-12) and create accepts a duplicate (ATG-INH-03). |
| FU-2 — every counter change in the account manager inherits BUG-1484 | account manager cases | The fix is in this file (ATG-INC-06, DEC-08, DEC-09). |
| P2 — the account manager must stop attaching deleted tags (BUG-629) | account manager cases | Here the counters work on a deleted tag (ATG-INC-04, DEC-07). |
| FU-3 — a future hard delete needs `passive_deletes=True` on `AccountTag.account_assignments` | account tag model / any future hard-delete caller | Here today's ORM behaviour (23502) is pinned (ATG-INH-06); that card changes with the fix. |
| inherited R4 [BUG-100] — `get_by_workspace` / `get_multi` ordered by `id` | `tests/unit/dao/base.cases.md` | The fix in `app/dao/base.py` reaches this DAO; not repeated here. |
| Inherited generic behavior (paging, missing ids, `get` ignores the workspace) | `tests/unit/dao/base.cases.md` | Only what `AccountTag` changes has cards. |
| Notes "keyword-only parameters" (positional call → `TypeError`) and the unused `skip` / `limit` of `get_active_tags_in_workspace` | none (no rule; removed with BUG-1485) | No card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | inherited R1, R3 (`AccountTagCreate`, `AccountTagUpdate`) | The module of the schemas and their required fields are not given. | Conventions assume `app.schemas.account_tag`; ATG-INH-02 builds `AccountTagCreate(name=…, tag_code=…)`, ATG-INH-04 `AccountTagUpdate(name=…, color=None)`. |
| 2 | `get_active_tags_in_workspace` R4, `get_system_tags_in_workspace` R3 ("name case-insensitive") | How the case-insensitive key is written in SQL is not stated. | The strict recorders ATG-ACT-09, SYS-07 assert `lower(account_tags.name)`; if the fix uses another form, those lines change with it. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_tag_code_in_workspace` | Returns | ATG-CODE-01 |
| `get_by_tag_code_in_workspace` | R1 | ATG-CODE-01, ATG-CODE-02, ATG-CODE-03, ATG-CODE-04 |
| `get_by_tag_code_in_workspace` | R2 | ATG-CODE-05, ATG-CODE-06, ATG-CODE-07, ATG-CODE-08, ATG-CODE-09, ATG-CODE-10, ATG-CODE-11, ATG-CODE-14, ATG-CODE-15 |
| `get_by_tag_code_in_workspace` | R3 | ATG-CODE-12 |
| `get_by_tag_code_in_workspace` | R4 | ATG-CODE-13 |
| `get_by_tag_code_in_workspace` | Side effects | ATG-CODE-13 |
| `get_active_tags_in_workspace` | Returns | ATG-ACT-01 |
| `get_active_tags_in_workspace` | R1 | ATG-ACT-01, ATG-ACT-02, ATG-ACT-03, ATG-ACT-04, ATG-ACT-06 |
| `get_active_tags_in_workspace` | R2 [BUG-1485] | ATG-ACT-05; ATG-ACT-06 (pass companion) |
| `get_active_tags_in_workspace` | R3 [BUG-1482] | ATG-ACT-07, ATG-ACT-09 |
| `get_active_tags_in_workspace` | R4 [BUG-1482] | ATG-ACT-08, ATG-ACT-09 |
| `get_active_tags_in_workspace` | Side effects | ATG-ACT-10 |
| `get_system_tags_in_workspace` | Returns | ATG-SYS-01 |
| `get_system_tags_in_workspace` | R1 | ATG-SYS-01, ATG-SYS-02, ATG-SYS-03, ATG-SYS-04 |
| `get_system_tags_in_workspace` | R2 [BUG-1483] | ATG-SYS-05 |
| `get_system_tags_in_workspace` | R3 [BUG-1482] | ATG-SYS-06, ATG-SYS-07 |
| `get_system_tags_in_workspace` | Side effects | ATG-SYS-08 |
| `increment_usage_count` | Returns | ATG-INC-01, ATG-INC-02 |
| `increment_usage_count` | R1 | ATG-INC-01, ATG-INC-07 |
| `increment_usage_count` | R2 | ATG-INC-02, ATG-INC-03 |
| `increment_usage_count` | R3 | ATG-INC-04 |
| `increment_usage_count` | R4 | ATG-INC-05 |
| `increment_usage_count` | R5 [BUG-1484] | ATG-INC-06; ATG-INC-07 (pass control) |
| `increment_usage_count` | R6 | ATG-INC-01, ATG-INC-08, ATG-INC-09 |
| `decrement_usage_count` | Returns | ATG-DEC-01, ATG-DEC-05 |
| `decrement_usage_count` | R1 | ATG-DEC-01, ATG-DEC-02 |
| `decrement_usage_count` | R2 | ATG-DEC-03 |
| `decrement_usage_count` | R3 | ATG-DEC-04 |
| `decrement_usage_count` | R4 | ATG-DEC-05, ATG-DEC-06 |
| `decrement_usage_count` | R5 | ATG-DEC-07 |
| `decrement_usage_count` | R6 [BUG-1484] | ATG-DEC-08, ATG-DEC-09 |
| `decrement_usage_count` | R7 | ATG-DEC-01, ATG-DEC-10, ATG-DEC-11 |
| inherited | R1 | ATG-INH-01, ATG-INH-02 |
| inherited | R2 | ATG-INH-03 |
| inherited | R3 | ATG-INH-04, ATG-INH-05 |
| inherited | R4 [BUG-100] | Deferred (`base.cases.md`) |
| inherited | R5 | ATG-INH-05 |
| inherited | R6 | ATG-INH-06, ATG-INH-07, ATG-INH-08 |
