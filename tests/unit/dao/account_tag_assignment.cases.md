# Test cases — `app/dao/account_tag_assignment.py`

> **Spec:** `tests/unit/dao/account_tag_assignment.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1–P3 were decided by Claude under the reviewer's delegation, each by the matching item tag assignment DAO decision.
> **Revision:** 2 — `account_tag_assignment.verify.md` S-1, S-2 (case-missing): new ATA-GA-05 (W2 asked for a W1 link), ATA-GA-06 (another account, same tag), ATA-RA-06 (W2 asked: nothing removed), ATA-RA-07 (another account: nothing of A1 removed). Cascade references repointed to ATG-INH-08, ACC-INH-10 after the G1 spec fix. No ID retired.
> **Counts:** 36 cases · 33 expected-to-pass · 3 expected-to-fail (bugs) · 6 deferred

## Reviewer summary
- **Per callable:** `get_account_tag_dao` 2 · `get_tags_for_account` 9 (3 bug) · `get_assignment` 6 · `assignment_exists` 3 · `delete_assignment` 5 · `remove_all_tags_from_account` 7 · inherited 4.
- **Depth:** lighter target (skill step 1a). Link rows between accounts and tags, and a tag counter lowered through the account tag DAO; no stock, money or order state.
- **Expected-to-fail:** BUG-865 1 strict (TFA-06; TFA-01 is the passing companion for active tags) · BUG-1486 2 (TFA-07 non-strict; TFA-08 strict SQL recorder).
- **Commit spies:** `delete_assignment` 1 (DA-05) · `remove_all_tags_from_account` 1 (RA-05).
- **Notable design choices:**
  - `get_assignment` "another tag" and "another account" share one card (GA-03): two links A1–T1 and A2–T2, ask for A1–T2; dropping either filter finds a row.
  - A soft-deleted account is built in its real closed state (`is_deleted True`, `is_active False`, `deleted_at`, `deleted_by`).
  - BUG-1487 (links to deleted tags erased by a save) is the account manager's: Deferred. R2 of `remove_all_tags_from_account` is tested as it behaves today, as the spec says.
- **Needs a decision:** None blocking. See Spec gaps 1 (schema module and fields assumed), 2 (case-insensitive key in the recorder card).

## Conventions for this module

**IDs.** `ATA` = `app/dao/account_tag_assignment.py`. `GD` get_account_tag_dao · `TFA` get_tags_for_account · `GA` get_assignment · `AE` assignment_exists · `DA` delete_assignment · `RA` remove_all_tags_from_account · `INH` inherited.

**Names.**
- `dao` = the singleton `account_tag_assignment_dao` (`from app.dao.account_tag_assignment import account_tag_assignment_dao`). `mod` = the module `app.dao.account_tag_assignment`. `account_tag_dao` = `from app.dao.account_tag import account_tag_dao`. `db` = the test's real database session, first argument; every other argument by keyword. `result` = what the When call returns.
- `Account`, `AccountTag`, `AccountTagAssignment` = the models in `app.models.account`, `app.models.account_tag`, `app.models.account_tag_assignment`. `AccountTagAssignmentCreate` = schema of `app.schemas.account_tag_assignment` (Spec gap 1). `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `select`, `text`, `func` = from `sqlalchemy`. `datetime` = the `datetime` class.
- MISSING = `999999999`: an id no row of any table has.

**Standing rows** (every test, no Given line, flushed in this order): W1, W2 = two `workspaces` rows (`make_workspace`); U1 = a `profiles` row (`make_profile`); A1 = `Account(workspace_id=W1.id, name="Acme")`; A2 = `Account(workspace_id=W1.id, name="Beta")`; A9 = `Account(workspace_id=W2.id, name="Far")`.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- **tag** = `AccountTag(workspace_id=W1.id, is_system_tag=False, is_active=True, usage_count=0)`; the card gives `name` and `tag_code`, and after "but" every other column that differs. **deleted** tag = `is_active False`.
- **link** = `AccountTagAssignment(workspace_id=W1.id, account_id=A1.id, tag_id=<tag>.id)`; the card gives the tag, and after "but" every other column that differs.
- **close(A)** = set on account A: `is_deleted = True`, `is_active = False`, `deleted_at = datetime(2026, 3, 1, 9, 0, 0)`, `deleted_by = U1.id`, then `db.flush()`.
- **bumpT(X)** = `db.execute(text("UPDATE account_tags SET description = coalesce(description, '') || '!' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.
- A Given line written as code is a step to run exactly as written. A change or `db.add` without `db.flush()` stays pending.

**Named checks.**
- **ids(result)** = `[t.id for t in result]` in the order returned; `sorted(ids(result)) == [...]` where order is not checked (right side in Given order).
- **links(A, W)** = `db.scalar(select(func.count()).select_from(AccountTagAssignment).where(AccountTagAssignment.account_id == A.id, AccountTagAssignment.workspace_id == W.id))`.
- **stored_count(T)** = `db.scalar(select(AccountTag.usage_count).where(AccountTag.id == T.id))`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value before the call.
- **nothing written** = the numbers of `account_tag_assignments` and `account_tags` rows (all workspaces) equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it.
- `raises: IntegrityError` = `with pytest.raises(IntegrityError) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards.
- **rolled back** = `sp = db.begin_nested()` directly before the call and a spy that wraps `db.commit` (still callable, records calls); "inside the savepoint" checks first; then `sp.rollback()` and the "after the savepoint rollback" checks.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `account_tags`; `order_part` = the text of `sql` after `ORDER BY` (`""` when none); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Never weakened.

**Externals.** None. The module global of GD cards is set with pytest's `monkeypatch.setattr` (restored after the test). **Race simulations.** None.

## `get_account_tag_dao`

### ATA-GD-01 — the first call imports the account tag DAO and stores it
- **Rules:** `get_account_tag_dao` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `monkeypatch.setattr(mod, "account_tag_dao", None)`

**When**
- `result = mod.get_account_tag_dao()`.

**Then**
1. returns: `result is account_tag_dao`.
2. returns: `mod.account_tag_dao is account_tag_dao`.

### ATA-GD-02 — a stored object is returned as it is
- **Rules:** `get_account_tag_dao` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `sentinel = object()`
2. `monkeypatch.setattr(mod, "account_tag_dao", sentinel)`

**When**
- `result = mod.get_account_tag_dao()`.

**Then**
1. returns: `result is sentinel`.

## `AccountTagAssignmentDAO.get_tags_for_account`

### ATA-TFA-01 — returns the account's active tags linked in the workspace, each once; another account's link is not returned
- **Rules:** `get_tags_for_account` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. T3 = tag, `name "Bank"`, `tag_code "bank"`.
4. L1 = link, tag T1.
5. L2 = link, tag T2.
6. L3 = link, tag T3, but `account_id A2.id`.

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [T1.id, T2.id]`.
3. returns: `isinstance(result[0], AccountTag)`.

### ATA-TFA-02 — a link recorded under another workspace is not returned
- **Rules:** `get_tags_for_account` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. L1 = link, tag T1, but `workspace_id W2.id`.
4. L2 = link, tag T2.

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T2.id]`.

### ATA-TFA-03 — asking with the other workspace returns only the link recorded there
- **Rules:** `get_tags_for_account` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. L1 = link, tag T1, but `workspace_id W2.id`.
4. L2 = link, tag T2.

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.

### ATA-TFA-04 — an unknown account returns an empty list
- **Rules:** `get_tags_for_account` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.

**When**
- `result = dao.get_tags_for_account(db, account_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### ATA-TFA-05 — another workspace's tag linked under this workspace is returned; count and system flag play no part
- **Rules:** `get_tags_for_account` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`, `is_system_tag True`, `usage_count 0`.
2. L1 = link, tag Z1.

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [Z1.id]`.

### ATA-TFA-06 — a deleted tag is not returned
- **Rules:** `get_tags_for_account` R3 [BUG-865]
- **Kind:** bug
- **Expect:** xfail BUG-865
- **Fails today on:** Then 2 (the deleted tag is returned)

**Given**
1. TD = tag, `name "Old"`, `tag_code "old"`, but `is_active False`.
2. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
3. LD = link, tag TD.
4. L1 = link, tag T1.

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `T1.id in ids(result)`.
2. returns: `ids(result) == [T1.id]`.

### ATA-TFA-07 — ordered by name case-insensitive, then id; system tags not grouped first
- **Rules:** `get_tags_for_account` R4 [BUG-1486]
- **Kind:** bug
- **Expect:** xfail BUG-1486 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical order after the update)

**Given**
1. T1 = tag, `name "bravo"`, `tag_code "bravo"`.
2. T2 = tag, `name "Alpha"`, `tag_code "alpha_upper"`.
3. T3 = tag, `name "alpha"`, `tag_code "alpha_lower"`.
4. T4 = tag, `name "Charlie"`, `tag_code "charlie"`, but `is_system_tag True`.
5. L1 = link, tag T1. L2 = link, tag T2. L3 = link, tag T3. L4 = link, tag T4 (four lines, in this order).
6. seqscan.
7. bumpT(T2).

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `sorted(ids(result)) == [T1.id, T2.id, T3.id, T4.id]`.
2. returns: `ids(result) == [T2.id, T3.id, T1.id, T4.id]`.

### ATA-TFA-08 — the query orders by name case-insensitive, then id, not by the system flag
- **Rules:** `get_tags_for_account` R4 [BUG-1486]
- **Kind:** bug
- **Expect:** xfail BUG-1486
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"lower(account_tags.name)" in order_part`.
4. statement: `"account_tags.id" in order_part`.
5. statement: `"is_system_tag" not in order_part`.

### ATA-TFA-09 — a closed account's tags are returned; the read writes nothing and keeps pending changes
- **Rules:** `get_tags_for_account` R5, Side effects
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. close(A1).
2. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
3. T2 = tag, `name "Client"`, `tag_code "client"`.
4. L1 = link, tag T1.
5. `T2.name = "Client Edited"` (not flushed).
6. `P = AccountTagAssignment(workspace_id=W1.id, account_id=A1.id, tag_id=T2.id)`, then `db.add(P)` (not flushed).
7. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_tags_for_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [T1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `T2 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `AccountTagAssignmentDAO.get_assignment`

### ATA-GA-01 — returns the link with that account, tag and workspace
- **Rules:** `get_assignment` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. L1 = link, tag T1.
4. L2 = link, tag T2.

**When**
- `result = dao.get_assignment(db, account_id=A1.id, tag_id=T2.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, AccountTagAssignment)`.
2. returns: `result.id == L2.id`.

### ATA-GA-02 — the pair recorded under another workspace returns None
- **Rules:** `get_assignment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1, but `workspace_id W2.id`.

**When**
- `result = dao.get_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ATA-GA-03 — another tag or another account does not match
- **Rules:** `get_assignment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. L1 = link, tag T1.
4. L2 = link, tag T2, but `account_id A2.id`.

**When**
- `result = dao.get_assignment(db, account_id=A1.id, tag_id=T2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ATA-GA-04 — a link of a closed account to a deleted tag is found
- **Rules:** `get_assignment` R3 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. close(A1).
2. TD = tag, `name "Old"`, `tag_code "old"`, but `is_active False`.
3. LD = link, tag TD.

**When**
- `result = dao.get_assignment(db, account_id=A1.id, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == LD.id`.

### ATA-GA-05 — asking with the other workspace does not find a W1 link
- **Rules:** `get_assignment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.

**When**
- `result = dao.get_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### ATA-GA-06 — another account with the same tag does not match
- **Rules:** `get_assignment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.

**When**
- `result = dao.get_assignment(db, account_id=A2.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

## `AccountTagAssignmentDAO.assignment_exists`

### ATA-AE-01 — True when the link exists
- **Rules:** `assignment_exists` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.

**When**
- `result = dao.assignment_exists(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### ATA-AE-02 — False for the pair recorded under another workspace
- **Rules:** `assignment_exists` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1, but `workspace_id W2.id`.

**When**
- `result = dao.assignment_exists(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### ATA-AE-03 — a link of a closed account to a deleted tag counts
- **Rules:** `assignment_exists` R2 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. close(A1).
2. TD = tag, `name "Old"`, `tag_code "old"`, but `is_active False`.
3. LD = link, tag TD.

**When**
- `result = dao.assignment_exists(db, account_id=A1.id, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

## `AccountTagAssignmentDAO.delete_assignment`

### ATA-DA-01 — the link is hard-deleted and flushed; True; the tag's counter is untouched
- **Rules:** `delete_assignment` R1, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 4`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. L1 = link, tag T1.
4. L2 = link, tag T2.

**When**
- `result = dao.delete_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. returns: `dao.get_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id) is None`.
3. count: `links(A1, W1) == 1`.
4. returns: `stored_count(T1) == 4`.

### ATA-DA-02 — the pair under another workspace: False, nothing deleted
- **Rules:** `delete_assignment` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1, but `workspace_id W2.id`.

**When**
- `result = dao.delete_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. nothing written: nothing written.
3. unchanged: unchanged(L1).

### ATA-DA-03 — calling again after a delete returns False
- **Rules:** `delete_assignment` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.
3. `dao.delete_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)` (returns True).

**When**
- `result = dao.delete_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. count: `links(A1, W1) == 0`.

### ATA-DA-04 — a link of a closed account to a deleted tag is deleted
- **Rules:** `delete_assignment` R3 (P1)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. close(A1).
2. TD = tag, `name "Old"`, `tag_code "old"`, but `is_active False`, `usage_count 2`.
3. LD = link, tag TD.

**When**
- `result = dao.delete_assignment(db, account_id=A1.id, tag_id=TD.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. count: `links(A1, W1) == 0`.
3. returns: `stored_count(TD) == 2`.

### ATA-DA-05 — flushed, not committed: a rollback restores the link
- **Rules:** `delete_assignment` R1, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.delete_assignment(db, account_id=A1.id, tag_id=T1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. count: inside the savepoint, `links(A1, W1) == 0`.
3. count: after the savepoint rollback, `links(A1, W1) == 1`.
4. mock called: the `db.commit` spy was never called.

## `AccountTagAssignmentDAO.remove_all_tags_from_account`

### ATA-RA-01 — every link of the account is removed and each counter lowered, never below 0
- **Rules:** `remove_all_tags_from_account` R1, R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. TZ = tag, `name "Zulu"`, `tag_code "zulu"`, but `usage_count 3`.
2. TO = tag, `name "Old"`, `tag_code "old"`, but `is_active False`, `usage_count 2`.
3. TW = tag, `name "Far"`, `tag_code "far"`, but `workspace_id W2.id`, `usage_count 5`.
4. T0 = tag, `name "Zero"`, `tag_code "zero"`, but `usage_count 0`.
5. LZ = link, tag TZ. LO = link, tag TO. LW = link, tag TW. L0 = link, tag T0 (four lines, in this order).

**When**
- `result = dao.remove_all_tags_from_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 4`.
2. count: `links(A1, W1) == 0`.
3. returns: `stored_count(TZ) == 2`.
4. returns: `stored_count(TO) == 1`.
5. returns: `stored_count(TW) == 5`.
6. returns: `stored_count(T0) == 0`.
7. re-read TO: `is_active is False`, `name == "Old"`.
8. unchanged: unchanged(A1).

### ATA-RA-02 — links of another account and links under another workspace stay
- **Rules:** `remove_all_tags_from_account` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. T2 = tag, `name "Client"`, `tag_code "client"`, but `usage_count 2`.
3. L1 = link, tag T1.
4. LB = link, tag T1, but `account_id A2.id`.
5. LX = link, tag T2, but `workspace_id W2.id`.

**When**
- `result = dao.remove_all_tags_from_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. count: `links(A2, W1) == 1`.
3. count: `links(A1, W2) == 1`.
4. returns: `stored_count(T2) == 2`.

### ATA-RA-03 — no link: 0, nothing changes
- **Rules:** `remove_all_tags_from_account` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. LB = link, tag T1, but `account_id A2.id`.

**When**
- `result = dao.remove_all_tags_from_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.
2. nothing written: nothing written.
3. unchanged: unchanged(T1).

### ATA-RA-04 — an unflushed link is not counted or removed; the method's flush inserts it
- **Rules:** `remove_all_tags_from_account` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. T2 = tag, `name "Client"`, `tag_code "client"`, but `usage_count 2`.
3. L1 = link, tag T1.
4. `P = AccountTagAssignment(workspace_id=W1.id, account_id=A1.id, tag_id=T2.id)`, then `db.add(P)` (not flushed).

**When**
- `result = dao.remove_all_tags_from_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. count: `links(A1, W1) == 1`.
3. returns: `dao.get_assignment(db, account_id=A1.id, tag_id=T2.id, workspace_id=W1.id) is not None`.
4. returns: `stored_count(T2) == 2`.

### ATA-RA-05 — flushed, not committed: a rollback restores links and counters
- **Rules:** `remove_all_tags_from_account` R6, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 3`.
2. L1 = link, tag T1.
3. Savepoint and commit spy per **rolled back** (Conventions).

**When**
- `result = dao.remove_all_tags_from_account(db, account_id=A1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 1`.
2. count: inside the savepoint, `links(A1, W1) == 0`.
3. count: after the savepoint rollback, `links(A1, W1) == 1`.
4. returns: after the savepoint rollback, `stored_count(T1) == 3`.
5. mock called: the `db.commit` spy was never called.

### ATA-RA-06 — asking with the other workspace removes nothing
- **Rules:** `remove_all_tags_from_account` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. L1 = link, tag T1.

**When**
- `result = dao.remove_all_tags_from_account(db, account_id=A1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == 0`.
2. count: `links(A1, W1) == 1`.
3. returns: `stored_count(T1) == 2`.

### ATA-RA-07 — another account's call removes nothing of A1
- **Rules:** `remove_all_tags_from_account` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `usage_count 2`.
2. L1 = link, tag T1.

**When**
- `result = dao.remove_all_tags_from_account(db, account_id=A2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == 0`.
2. count: `links(A1, W1) == 1`.
3. returns: `stored_count(T1) == 2`.

## Inherited `BaseDAO` methods on `AccountTagAssignment`

### ATA-INH-01 — create with a dict stores the link with assigned_at set
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "account_id": A1.id, "tag_id": T1.id})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `account_id == A1.id`, `tag_id == T1.id`.
3. re-read result: `assigned_at is not None`, `assigned_by is None`.

### ATA-INH-02 — create with an AccountTagAssignmentCreate fails on flush (no workspace_id)
- **Rules:** inherited R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `dao.create(db, obj_in=AccountTagAssignmentCreate(account_id=A1.id, tag_id=T1.id))`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. nothing written: nothing written.

### ATA-INH-03 — a second link for the same pair under another workspace is refused
- **Rules:** inherited R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. L1 = link, tag T1.

**When**
- `dao.create(db, obj_in={"workspace_id": W2.id, "account_id": A1.id, "tag_id": T1.id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23505"`.
2. raises: `"uq_account_tag" in str(exc.value.orig)`.
3. nothing written: nothing written.

### ATA-INH-04 — an unknown tag is refused (23503)
- **Rules:** inherited R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No link exists.

**When**
- `dao.create(db, obj_in={"workspace_id": W1.id, "account_id": A1.id, "tag_id": MISSING})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23503"`.
2. nothing written: nothing written.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| P2 / BUG-870 — the replace-all save re-creates unchanged links; this method goes with the fix | `AccountManager.update_account` (account manager cases) | Here `remove_all_tags_from_account` is tested as it behaves today. |
| P3 / BUG-1487 — a save must leave links to deleted tags alone | `AccountManager.update_account` (account manager cases) | Here R2 removes them (ATA-RA-01). |
| FU-1 (a)–(c) — BUG-719 citation, `update_account` R11–R13, `delete_account` R6 | account manager spec and cases | No card here. |
| inherited R3 [BUG-100] — `get_by_workspace` / `get_multi` ordered by `id` | `tests/unit/dao/base.cases.md` | Fix in `app/dao/base.py`; not repeated. |
| inherited R4 — cascade on hard delete of the account, the tag or the workspace | `account_tag.cases.md` (ATG-INH-08, SQL `DELETE` of a tag), `account.cases.md` (ACC-INH-10, SQL `DELETE` of an account); workspace: `base.cases.md` | ATA-INH-04 covers only the FK refusal. An ORM `remove` of a linked account or tag raises 23502 instead (ACC-INH-08, ATG-INH-06). |
| Notes "keyword-only parameters"; module singleton | none (no rule) | No card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | inherited R1 (`AccountTagAssignmentCreate`) | The schema's module and fields are not given. | Conventions assume `app.schemas.account_tag_assignment`; ATA-INH-02 builds it with `account_id`, `tag_id`. |
| 2 | `get_tags_for_account` R4 ("name case-insensitive") | How the case-insensitive key is written in SQL is not stated. | ATA-TFA-08 asserts `lower(account_tags.name)`; change with the fix if another form is used. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_account_tag_dao` | R1 | ATA-GD-01 |
| `get_account_tag_dao` | R2 | ATA-GD-01, ATA-GD-02 |
| `get_tags_for_account` | Returns | ATA-TFA-01 |
| `get_tags_for_account` | R1 | ATA-TFA-01, ATA-TFA-02, ATA-TFA-03, ATA-TFA-04 |
| `get_tags_for_account` | R2 | ATA-TFA-05 |
| `get_tags_for_account` | R3 [BUG-865] | ATA-TFA-06; ATA-TFA-01 (pass companion) |
| `get_tags_for_account` | R4 [BUG-1486] | ATA-TFA-07, ATA-TFA-08 |
| `get_tags_for_account` | R5 | ATA-TFA-09 |
| `get_tags_for_account` | Side effects | ATA-TFA-09 |
| `get_assignment` | Returns | ATA-GA-01 |
| `get_assignment` | R1 | ATA-GA-01 |
| `get_assignment` | R2 | ATA-GA-02, ATA-GA-03, ATA-GA-05, ATA-GA-06 |
| `get_assignment` | R3 | ATA-GA-04 |
| `assignment_exists` | R1 | ATA-AE-01, ATA-AE-02 |
| `assignment_exists` | R2 | ATA-AE-03 |
| `delete_assignment` | R1 | ATA-DA-01, ATA-DA-05 |
| `delete_assignment` | R2 | ATA-DA-02, ATA-DA-03 |
| `delete_assignment` | R3 | ATA-DA-01, ATA-DA-04 |
| `delete_assignment` | Side effects | ATA-DA-05 |
| `remove_all_tags_from_account` | Returns | ATA-RA-01 |
| `remove_all_tags_from_account` | R1 | ATA-RA-01, ATA-RA-02, ATA-RA-06, ATA-RA-07 |
| `remove_all_tags_from_account` | R2 | ATA-RA-01 |
| `remove_all_tags_from_account` | R3 | ATA-RA-01 |
| `remove_all_tags_from_account` | R4 | ATA-RA-03 |
| `remove_all_tags_from_account` | R5 | ATA-RA-04 |
| `remove_all_tags_from_account` | R6 | ATA-RA-05 |
| `remove_all_tags_from_account` | Side effects | ATA-RA-05 |
| inherited | R1 | ATA-INH-01, ATA-INH-02 |
| inherited | R2 | ATA-INH-03, ATA-INH-04 |
| inherited | R3 [BUG-100] | Deferred (`base.cases.md`) |
| inherited | R4 | Deferred (ATG-INH-08, ACC-INH-10) |
