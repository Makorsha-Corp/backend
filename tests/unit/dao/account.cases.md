# Test cases — `app/dao/account.py`

> **Spec:** `tests/unit/dao/account.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-03; nothing open). P1–P3 were decided by Claude under the reviewer's delegation; the house-rule lines reuse the account manager spec's bug IDs.
> **Revision:** 2 — spec Gap log G1 (inherited R5 rewritten as fact: ORM `remove` of a referenced account raises 23502; SQL `DELETE` gives 23001 / cascades). ACC-INH-07 now expects 23502 (invoice) and ACC-INH-08 23502 (tag link), both with nothing deleted; new ACC-INH-09 (SQL `DELETE` → 23001), ACC-INH-10 (SQL `DELETE` cascades to links), ACC-INH-11 (unreferenced account removed). No ID retired.
> **Revision:** 3 — `account.verify.md` R-1 … R-8 (case-missing): new ACC-IW-37 (W2 asked, earlier-id W1 row), IW-38 (link recorded in W1 for a W2 account), IW-39 (end of the code), IW-40 (stored code a part of the argument), IW-41 (`_` in the stored code), IW-42 (duplicate links take one page place, `limit=2`), IW-43 (trailing space, xfail BUG-637), ACC-BT-17, BT-18 (account / link workspace both ways), BT-19 (tag workspace not compared); one Then line `"DESC" not in order_part.upper()` added to ACC-IW-28 and ACC-BT-09. No ID retired.
> **Counts:** 76 cases · 60 expected-to-pass · 16 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `get_accounts_in_workspace` 43 (13 bug) · `count_active_accounts` 3 · `get_accounts_by_tag_id` 19 (3 bug) · inherited 11.
- **Depth:** lighter target (skill step 1a). Reads of the account list and one count; the module writes nothing of its own and no stock, money or order state. The 1b shapes are applied once per query (the two lists are separate queries).
- **Expected-to-fail:** BUG-878 1 (IW-06, the call raises `TypeError`) · BUG-637 3 (IW-08, IW-09, IW-43) · BUG-868 3 (IW-11, IW-12, IW-13) · BUG-861 3 (IW-17, IW-18, IW-19) · BUG-864 1 (IW-22; IW-23 is the passing companion) · BUG-866 2 (IW-27 non-strict; IW-28 strict SQL recorder) · BUG-1481 1 (BT-07) · BUG-1480 2 (BT-08 non-strict; BT-09 strict SQL recorder). All others strict.
- **Notable design choices:**
  - Every non-order card compares **sets** of ids (`sorted(ids(result))`), because no order is promised today.
  - The "is_deleted" filter has its own negative card with a deleted-but-still-active account (BUG-863 state, IW-04, BT-03); the real closed state (IW-03) alone would not catch a dropped `is_deleted` filter.
  - IW-19 (stored code with capitals found by the lower-case code) reads R5's "compared trimmed and case-insensitively" as both sides (Spec gap 3).
  - Paging: default limit, `limit=1000`, `limit=0`, negative `limit` / `skip` and filter-before-paging get one card each per list; skip-with-order cards are not written, since no order holds today.
- **Needs a decision:** None blocking. See Spec gaps 1–4.

## Conventions for this module

**IDs.** `ACC` = `app/dao/account.py`. `IW` get_accounts_in_workspace · `CNT` count_active_accounts · `BT` get_accounts_by_tag_id · `INH` inherited `BaseDAO` methods.

**Names.**
- `dao` = the singleton `account_dao` (`from app.dao.account import account_dao`). `db` = the test's real database session, first argument; every other argument by keyword (only `dao.get(db, <id>)` takes the id positionally). `result` = what the When call returns.
- `Account`, `AccountTag`, `AccountTagAssignment` = the models of `app.models.account`, `app.models.account_tag`, `app.models.account_tag_assignment`. `AccountInvoice` = `app.models.account_invoice.AccountInvoice` (Spec gap 2). `AccountCreate` = schema of `app.schemas.account` (Spec gap 1). `IntegrityError`, `DataError` = `sqlalchemy.exc` classes. `select`, `text`, `func` = from `sqlalchemy`. `date`, `datetime` = the `datetime` module's classes.
- MISSING = `999999999`: an id no row of any table has.
- Standing rows (every test, no Given line): W1, W2 = two `workspaces` rows (`make_workspace`); U1 = a `profiles` row (`make_profile`). No account or tag exists unless the Given lists it.

**Given rows.** Inserted directly (never through `dao`), flushed one at a time in the order written, so ids rise in that order. The session does not autoflush.
- **account** = `Account(workspace_id=W1.id, is_active=True, is_deleted=False)`; the card gives `name`, and after "but" every other column that differs. **inactive** = `is_active False`. **closed** = `is_deleted True`, `is_active False`, `deleted_at datetime(2026, 3, 1, 9, 0, 0)`, `deleted_by U1.id`. **half-closed** = `is_deleted True`, `is_active True`.
- **tag** = `AccountTag(workspace_id=W1.id, is_system_tag=False, is_active=True, usage_count=0)`; the card gives `name` and `tag_code`. **deleted** tag = `is_active False`.
- **link(A, T)** = `AccountTagAssignment(workspace_id=W1.id, account_id=A.id, tag_id=T.id)`; after "but" the columns that differ.
- **bumpA(X)** = `db.execute(text("UPDATE accounts SET city = coalesce(city, '') || '!' WHERE id = :i"), {"i": X.id})`, then `db.expire_all()`.
- **seqscan** = run `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`, in this order.
- **bulk(n)** = n accounts N1 … Nn built with `add_all` and flushed: Nk = account, `name` = `f"Acct {k:03d}"`.
- A Given line written as code is a step to run exactly as written. A change or `db.add` without `db.flush()` stays pending.

**Named checks.**
- **ids(result)** = `[a.id for a in result]` in the order returned; `sorted(ids(result)) == [...]` where the order is not checked (right side in Given order).
- **names(result)** = `[a.name for a in result]` in the order returned.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read, every column of X equals its value before the call.
- **nothing written** = the numbers of `accounts` and `account_tag_assignments` rows (all workspaces) equal their values before the call.
- `pending:` lines check the session after the call, before anything expires it.
- `raises: E` = `with pytest.raises(E) as exc:` then `with db.begin_nested():` then the call; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `accounts`; `order_part` = the text of `sql` after `ORDER BY` and before `LIMIT` (`""` when there is no `ORDER BY`); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`.

**xfail cards.** `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Never weakened.

**Externals.** None. Nothing is mocked. **Race simulations.** None.

## `AccountDAO.get_accounts_in_workspace`

### ACC-IW-01 — returns a list of the workspace's live, active accounts
- **Rules:** `get_accounts_in_workspace` R1, R2 (`name=None`), R4 (`tag_code=None`), Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A1.id, A2.id]`.
3. returns: `isinstance(result[0], Account)`.

### ACC-IW-02 — an inactive account is not returned
- **Rules:** `get_accounts_in_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AI = account, `name "Aaa"`, but `is_active False`.
2. A1 = account, `name "Acme Ltd"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-03 — a closed account is not returned
- **Rules:** `get_accounts_in_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AC = account, `name "Aaa"`, but closed.
2. A1 = account, `name "Acme Ltd"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-04 — a deleted account still marked active is not returned
- **Rules:** `get_accounts_in_workspace` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AH = account, `name "Aaa"`, but half-closed.
2. A1 = account, `name "Acme Ltd"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-05 — other workspaces' accounts, before and after by id, are not returned
- **Rules:** `get_accounts_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = account, `name "Acme Far"`, but `workspace_id W2.id`.
2. A1 = account, `name "Acme Ltd"`.
3. Z2 = account, `name "Acme Far 2"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-06 — include_inactive=True also returns inactive, not deleted accounts
- **Rules:** `get_accounts_in_workspace` R1a [BUG-878]
- **Kind:** bug
- **Expect:** xfail BUG-878
- **Fails today on:** Then 1 (the call raises TypeError: no `include_inactive` parameter)

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`, but `is_active False`.
3. A3 = account, `name "Gone Co"`, but closed.
4. Z1 = account, `name "Far Co"`, but `workspace_id W2.id`, `is_active False`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, include_inactive=True)`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.

### ACC-IW-07 — an empty name means no name filter
- **Rules:** `get_accounts_in_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="")`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.

### ACC-IW-08 — a name of only spaces means no name filter
- **Rules:** `get_accounts_in_workspace` R2 [BUG-637]
- **Kind:** bug
- **Expect:** xfail BUG-637
- **Fails today on:** Then 1 (only names containing three spaces match: `[]`)

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="   ")`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.

### ACC-IW-09 — the name is trimmed: " acme " finds "Acme Ltd"
- **Rules:** `get_accounts_in_workspace` R2 [BUG-637]
- **Kind:** bug
- **Expect:** xfail BUG-637
- **Fails today on:** Then 1 (the untrimmed text matches nothing: `[]`)

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name=" acme ")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-10 — the name matches anywhere, case-insensitively
- **Rules:** `get_accounts_in_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.
3. A3 = account, `name "Acme"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="ME L")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-11 — "%" in the text matches itself: "50%" finds "50% off", not "500 Ltd"
- **Rules:** `get_accounts_in_workspace` R3 [BUG-868]
- **Kind:** bug
- **Expect:** xfail BUG-868
- **Fails today on:** Then 1 (`%` is a wildcard: both accounts are returned)

**Given**
1. A1 = account, `name "50% off"`.
2. A2 = account, `name "500 Ltd"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="50%")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-12 — "_" alone finds only names containing "_"
- **Rules:** `get_accounts_in_workspace` R3 [BUG-868]
- **Kind:** bug
- **Expect:** xfail BUG-868
- **Fails today on:** Then 1 (`_` is a wildcard: every account is returned)

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "a_b Co"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="_")`.

**Then**
1. returns: `ids(result) == [A2.id]`.

### ACC-IW-13 — a backslash matches itself
- **Rules:** `get_accounts_in_workspace` R3 [BUG-868]
- **Kind:** bug
- **Expect:** xfail BUG-868
- **Fails today on:** Then 1 (`\` escapes the closing `%`: `[]`)

**Given**
1. A1 = account, `name "C:\\dir Co"` (Python literal; the stored name has one backslash).
2. A2 = account, `name "Acme Ltd"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="\\")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-14 — an empty tag code means no tag filter
- **Rules:** `get_accounts_in_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. A2 = account, `name "Beta Co"`.
4. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="")`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.

### ACC-IW-15 — a tag code keeps only accounts with a link to a tag of that code
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. A1 = account, `name "Acme Ltd"`.
4. A2 = account, `name "Beta Co"`.
5. A3 = account, `name "Gamma"`.
6. L1 = link(A1, T1).
7. L2 = link(A2, T2).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-16 — a link recorded under another workspace does not count
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1), but `workspace_id W2.id`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result == []`.

### ACC-IW-17 — the tag code ignores case: "Supplier" matches "supplier"
- **Rules:** `get_accounts_in_workspace` R5 [BUG-861]
- **Kind:** bug
- **Expect:** xfail BUG-861
- **Fails today on:** Then 1 (exact comparison: `[]`)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="Supplier")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-18 — the tag code is trimmed: "supplier " matches "supplier"
- **Rules:** `get_accounts_in_workspace` R5 [BUG-861]
- **Kind:** bug
- **Expect:** xfail BUG-861
- **Fails today on:** Then 1 (exact comparison: `[]`)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier ")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-19 — stored side: a stored code "Supplier" is found by "supplier"
- **Rules:** `get_accounts_in_workspace` R5 [BUG-861]
- **Kind:** bug
- **Expect:** xfail BUG-861
- **Fails today on:** Then 1 (exact comparison: `[]`)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "Supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-20 — a part of the code does not match
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supp")`.

**Then**
1. returns: `result == []`.

### ACC-IW-21 — "_" in the code is not a wildcard
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="s_pplier")`.

**Then**
1. returns: `result == []`.

### ACC-IW-22 — an account whose only tag with that code is deleted is not returned
- **Rules:** `get_accounts_in_workspace` R6 [BUG-864]
- **Kind:** bug
- **Expect:** xfail BUG-864
- **Fails today on:** Then 1 (inactive tags match: `[A1.id]`)

**Given**
1. TD = tag, `name "Supplier"`, `tag_code "supplier"`, but `is_active False`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, TD).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result == []`.

### ACC-IW-23 — with an active and a deleted tag of one code, the active one decides; returned once
- **Rules:** `get_accounts_in_workspace` R6, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. TD = tag, `name "Supplier old"`, `tag_code "supplier"`, but `is_active False`.
2. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
3. A1 = account, `name "Acme Ltd"`.
4. LD = link(A1, TD).
5. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-24 — two active tags of one code on one account: the account once
- **Rules:** `get_accounts_in_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier A"`, `tag_code "supplier"`.
2. T2 = tag, `name "Supplier B"`, `tag_code "supplier"`.
3. A1 = account, `name "Acme Ltd"`.
4. L1 = link(A1, T1).
5. L2 = link(A1, T2).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-25 — a link in this workspace to another workspace's tag with that code matches
- **Rules:** `get_accounts_in_workspace` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, Z1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-26 — name and tag code together: both must hold
- **Rules:** `get_accounts_in_workspace` R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. A2 = account, `name "Acme Two"`.
4. A3 = account, `name "Beta Co"`.
5. L1 = link(A1, T1).
6. L3 = link(A3, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="acme", tag_code="supplier")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-27 — ordered by name case-insensitive, then id
- **Rules:** `get_accounts_in_workspace` R8 [BUG-866]
- **Kind:** bug
- **Expect:** xfail BUG-866 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; plan order)

**Given**
1. A1 = account, `name "Zulu"`.
2. A2 = account, `name "apple"`.
3. A3 = account, `name "Banana"`.
4. A4 = account, `name "mango"`.
5. A5 = account, `name "Kilo"`.
6. A6 = account, `name "delta"`.
7. seqscan.
8. bumpA(A2).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 6`.
2. returns: `names(result) == ["apple", "Banana", "delta", "Kilo", "mango", "Zulu"]`.

### ACC-IW-28 — the query orders by name case-insensitive, then id
- **Rules:** `get_accounts_in_workspace` R8 [BUG-866]
- **Kind:** bug
- **Expect:** xfail BUG-866
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"lower(accounts.name)" in order_part`.
4. statement: `"accounts.id" in order_part`.
5. statement: `"DESC" not in order_part.upper()`.

### ACC-IW-29 — the default limit is 100: 107 accounts give 100
- **Rules:** `get_accounts_in_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(107).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.

### ACC-IW-30 — limit=1000 returns all 107
- **Rules:** `get_accounts_in_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(107).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 107`.

### ACC-IW-31 — limit=0 returns an empty list
- **Rules:** `get_accounts_in_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### ACC-IW-32 — skip past the end returns an empty list
- **Rules:** `get_accounts_in_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### ACC-IW-33 — a negative limit raises DataError 2201W
- **Rules:** `get_accounts_in_workspace` R10, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.

**When**
- `dao.get_accounts_in_workspace(db, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### ACC-IW-34 — a negative skip raises DataError 2201X
- **Rules:** `get_accounts_in_workspace` R10, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.

**When**
- `dao.get_accounts_in_workspace(db, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### ACC-IW-35 — filters run before paging: a hidden account does not take the one place
- **Rules:** `get_accounts_in_workspace` R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AI = account, `name "Aaa"`, but `is_active False`.
2. AH = account, `name "Aab"`, but half-closed.
3. A1 = account, `name "Acme Ltd"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-36 — the read writes nothing and keeps the caller's pending changes
- **Rules:** `get_accounts_in_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`, but `workspace_id W2.id`.
3. `A2.name = "Beta Edited"` (not flushed).
4. `P = Account(workspace_id=W1.id, name="Pending", is_active=True, is_deleted=False)`, then `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A2 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.
7. nothing written: nothing written.

### ACC-IW-37 — asking with the other workspace returns only its account, not an earlier-id W1 account
- **Rules:** `get_accounts_in_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = account, `name "Acme Far"`.
2. A1 = account, `name "Acme Ltd"`, but `workspace_id W2.id`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-IW-38 — a W2 account whose link is recorded in W1 is not found from W2
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`.
2. A1 = account, `name "Acme Ltd"`, but `workspace_id W2.id`.
3. L1 = link(A1, T1). (Recorded in W1.)

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W2.id, tag_code="supplier")`.

**Then**
1. returns: `result == []`.

### ACC-IW-39 — the end of the code does not match
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="plier")`.

**Then**
1. returns: `result == []`.

### ACC-IW-40 — stored side: a stored code that is a part of the argument does not match
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supp"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result == []`.

### ACC-IW-41 — stored side: "_" in the stored code is not a wildcard
- **Rules:** `get_accounts_in_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "s_pplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier")`.

**Then**
1. returns: `result == []`.

### ACC-IW-42 — an account with two matching links takes one place in the page
- **Rules:** `get_accounts_in_workspace` R7, R10
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier A"`, `tag_code "supplier"`.
2. T2 = tag, `name "Supplier B"`, `tag_code "supplier"`.
3. A1 = account, `name "Acme Ltd"`.
4. A2 = account, `name "Beta Co"`.
5. L1 = link(A1, T1).
6. L2 = link(A1, T2).
7. L3 = link(A2, T1).

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, tag_code="supplier", limit=2)`.

**Then**
1. returns: `sorted(ids(result)) == [A1.id, A2.id]`.

### ACC-IW-43 — a trailing space is trimmed: "ltd " finds "Acme Ltd"
- **Rules:** `get_accounts_in_workspace` R2 [BUG-637]
- **Kind:** bug
- **Expect:** xfail BUG-637
- **Fails today on:** Then 1 (the untrimmed text matches nothing: `[]`)

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.

**When**
- `result = dao.get_accounts_in_workspace(db, workspace_id=W1.id, name="ltd ")`.

**Then**
1. returns: `ids(result) == [A1.id]`.

## `AccountDAO.count_active_accounts`

### ACC-CNT-01 — counts only live, active accounts of the workspace
- **Rules:** `count_active_accounts` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.
3. AI = account, `name "Idle"`, but `is_active False`.
4. AC = account, `name "Gone"`, but closed.
5. AH = account, `name "Half"`, but half-closed.
6. Z1 = account, `name "Far"`, but `workspace_id W2.id`.

**When**
- `result = dao.count_active_accounts(db, workspace_id=W1.id)`.

**Then**
1. returns: `type(result) is int`.
2. returns: `result == 2`.

### ACC-CNT-02 — no cap: 107 live accounts count 107
- **Rules:** `count_active_accounts` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(107).

**When**
- `result = dao.count_active_accounts(db, workspace_id=W1.id)`.

**Then**
1. returns: `result == 107`.

### ACC-CNT-03 — an unknown workspace counts 0
- **Rules:** `count_active_accounts` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.

**When**
- `result = dao.count_active_accounts(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == 0`.

## `AccountDAO.get_accounts_by_tag_id`

### ACC-BT-01 — returns the live, active accounts linked to the tag in the workspace
- **Rules:** `get_accounts_by_tag_id` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. T2 = tag, `name "Client"`, `tag_code "client"`.
3. A1 = account, `name "Acme Ltd"`.
4. A2 = account, `name "Beta Co"`.
5. A3 = account, `name "Gamma"`.
6. L1 = link(A1, T1).
7. L2 = link(A2, T1).
8. L3 = link(A3, T2).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `sorted(ids(result)) == [A1.id, A2.id]`.
3. returns: `isinstance(result[0], Account)`.

### ACC-BT-02 — an inactive account is left out
- **Rules:** `get_accounts_by_tag_id` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. AI = account, `name "Idle"`, but `is_active False`.
3. A1 = account, `name "Acme Ltd"`.
4. LI = link(AI, T1).
5. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-BT-03 — a deleted account still marked active is left out
- **Rules:** `get_accounts_by_tag_id` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. AH = account, `name "Half"`, but half-closed.
3. A1 = account, `name "Acme Ltd"`.
4. LH = link(AH, T1).
5. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-BT-04 — a link recorded under another workspace does not count
- **Rules:** `get_accounts_by_tag_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1), but `workspace_id W2.id`.

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `result == []`.

### ACC-BT-05 — asking with another workspace returns an empty list
- **Rules:** `get_accounts_by_tag_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W2.id, tag_id=T1.id)`.

**Then**
1. returns: `result == []`.

### ACC-BT-06 — an unknown tag returns an empty list
- **Rules:** `get_accounts_by_tag_id` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=MISSING)`.

**Then**
1. returns: `result == []`.

### ACC-BT-07 — a deleted tag gives an empty list; its links stay
- **Rules:** `get_accounts_by_tag_id` R3 [BUG-1481]
- **Kind:** bug
- **Expect:** xfail BUG-1481
- **Fails today on:** Then 2 (the tag is not looked at: `[A1.id]`)

**Given**
1. TD = tag, `name "Old"`, `tag_code "old"`, but `is_active False`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, TD).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=TD.id)`.

**Then**
1. count: `account_tag_assignments` rows with `tag_id == TD.id`: exactly 1.
2. returns: `result == []`.

### ACC-BT-08 — ordered by name case-insensitive, then id
- **Rules:** `get_accounts_by_tag_id` R4 [BUG-1480]
- **Kind:** bug
- **Expect:** xfail BUG-1480 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; plan order)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Zulu"`.
3. A2 = account, `name "apple"`.
4. A3 = account, `name "Banana"`.
5. L1 = link(A1, T1).
6. L2 = link(A2, T1).
7. L3 = link(A3, T1).
8. seqscan.
9. bumpA(A2).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### ACC-BT-09 — the query orders by name case-insensitive, then id
- **Rules:** `get_accounts_by_tag_id` R4 [BUG-1480]
- **Kind:** bug
- **Expect:** xfail BUG-1480
- **Fails today on:** Then 2 (the query has no `ORDER BY`)

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"lower(accounts.name)" in order_part`.
4. statement: `"accounts.id" in order_part`.
5. statement: `"DESC" not in order_part.upper()`.

### ACC-BT-10 — the default limit is 100: 101 linked accounts give 100
- **Rules:** `get_accounts_by_tag_id` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. bulk(101).
3. For each Nk, `db.add(AccountTagAssignment(workspace_id=W1.id, account_id=Nk.id, tag_id=T1.id))`, then `db.flush()`.

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `len(result) == 100`.

### ACC-BT-11 — limit=1000 returns all 101, each once
- **Rules:** `get_accounts_by_tag_id` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. bulk(101).
3. For each Nk, `db.add(AccountTagAssignment(workspace_id=W1.id, account_id=Nk.id, tag_id=T1.id))`, then `db.flush()`.

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `len(set(ids(result))) == 101`.

### ACC-BT-12 — limit=0 returns an empty list
- **Rules:** `get_accounts_by_tag_id` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### ACC-BT-13 — a negative limit raises DataError 2201W
- **Rules:** `get_accounts_by_tag_id` R5, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201W"`.
2. nothing written: nothing written.

### ACC-BT-14 — a negative skip raises DataError 2201X
- **Rules:** `get_accounts_by_tag_id` R5, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.

**When**
- `dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `exc.value.orig.pgcode == "2201X"`.
2. nothing written: nothing written.

### ACC-BT-15 — filters run before paging: a hidden account does not take the one place
- **Rules:** `get_accounts_by_tag_id` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. AI = account, `name "Aaa"`, but `is_active False`.
3. A1 = account, `name "Acme Ltd"`.
4. LI = link(AI, T1).
5. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-BT-16 — the read writes nothing and keeps the caller's pending changes
- **Rules:** `get_accounts_by_tag_id` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. A2 = account, `name "Beta Co"`.
4. L1 = link(A1, T1).
5. `A2.name = "Beta Edited"` (not flushed).
6. `P = AccountTagAssignment(workspace_id=W1.id, account_id=A2.id, tag_id=T1.id)`, then `db.add(P)` (not flushed).
7. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. pending: `A2 in db.dirty`.
5. pending: `len(db.dirty) == 1`.
6. statement: `written == []`.

### ACC-BT-17 — another workspace's account linked under this workspace is left out
- **Rules:** `get_accounts_by_tag_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. Z1 = account, `name "Far"`, but `workspace_id W2.id`.
3. A1 = account, `name "Acme Ltd"`.
4. LZ = link(Z1, T1). (Recorded in W1.)
5. L1 = link(A1, T1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=T1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

### ACC-BT-18 — from W2: neither a W1 account with a W2 link nor a W2 account with a W1 link counts
- **Rules:** `get_accounts_by_tag_id` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. Z1 = account, `name "Far"`, but `workspace_id W2.id`.
4. L1 = link(A1, T1), but `workspace_id W2.id`.
5. LZ = link(Z1, T1). (Recorded in W1.)

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W2.id, tag_id=T1.id)`.

**Then**
1. returns: `result == []`.

### ACC-BT-19 — the tag's own workspace is not compared: a W1 link to a W2 tag counts
- **Rules:** `get_accounts_by_tag_id` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z1 = tag, `name "Supplier"`, `tag_code "supplier"`, but `workspace_id W2.id`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, Z1).

**When**
- `result = dao.get_accounts_by_tag_id(db, workspace_id=W1.id, tag_id=Z1.id)`.

**Then**
1. returns: `ids(result) == [A1.id]`.

## Inherited `BaseDAO` methods on `Account`

### ACC-INH-01 — create with a dict stores an account with the defaults
- **Rules:** inherited R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. No account exists.

**When**
- `result = dao.create(db, obj_in={"workspace_id": W1.id, "name": "Acme Ltd"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read result: `workspace_id == W1.id`, `name == "Acme Ltd"`.
3. re-read result: `allow_invoices is True`, `is_active is True`, `is_deleted is False`.
4. re-read result: `created_at is not None`.
5. re-read result: `account_code is None`, `city is None`, `created_by is None`, `deleted_at is None`.

### ACC-INH-02 — create with an AccountCreate raises TypeError and adds nothing
- **Rules:** inherited R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No account exists.

**When**
- `dao.create(db, obj_in=AccountCreate(name="Acme Ltd", tag_ids=[]))` inside `with pytest.raises(TypeError) as exc:`.

**Then**
1. raises: `"tag_ids" in str(exc.value)`.
2. pending: `len(db.new) == 0`.
3. nothing written: nothing written.

### ACC-INH-03 — update with a dict sets the column; the database sets updated_at
- **Rules:** inherited R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.

**When**
- `result = dao.update(db, db_obj=A1, obj_in={"name": "Acme Limited", "city": "Dhaka"})`.

**Then**
1. returns: `result.id == A1.id`.
2. re-read A1: `name == "Acme Limited"`, `city == "Dhaka"`.
3. re-read A1: `updated_at is not None`.

### ACC-INH-04 — get returns a closed account of any workspace
- **Rules:** inherited R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Z1 = account, `name "Far"`, but `workspace_id W2.id`, closed.

**When**
- `result = dao.get(db, Z1.id)`.

**Then**
1. returns: `result.id == Z1.id`.
2. returns: `result.is_deleted is True`.

### ACC-INH-05 — get_by_id_and_workspace returns a closed account
- **Rules:** inherited R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. AC = account, `name "Gone"`, but closed.

**When**
- `result = dao.get_by_id_and_workspace(db, id=AC.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == AC.id`.

### ACC-INH-06 — get_by_id_and_workspace returns None for another workspace's account
- **Rules:** inherited R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. Z1 = account, `name "Far"`, but `workspace_id W2.id`.
3. A2 = account, `name "Beta Co"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### ACC-INH-07 — remove of an account referenced by an invoice raises 23502 and deletes nothing
- **Rules:** inherited R5 (c)
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. I1 = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="payable", invoice_amount=100, invoice_date=date(2026, 3, 1))`.
3. `a1_id = A1.id`

**When**
- `dao.remove(db, id=a1_id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. count: `accounts` rows with `id == a1_id`: exactly 1.
3. count: `account_invoices` rows with `account_id == a1_id`: exactly 1.

### ACC-INH-08 — remove of an account with a tag link raises 23502 and deletes nothing
- **Rules:** inherited R5 (b)
- **Kind:** error
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).
4. `a1_id = A1.id`

**When**
- `dao.remove(db, id=a1_id)`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23502"`.
2. count: `accounts` rows with `id == a1_id`: exactly 1.
3. count: `account_tag_assignments` rows with `account_id == a1_id`: exactly 1.

### ACC-INH-09 — a SQL DELETE of an account an invoice references is refused with 23001
- **Rules:** inherited R5 (database side)
- **Kind:** error
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. I1 = `AccountInvoice(workspace_id=W1.id, account_id=A1.id, invoice_type="payable", invoice_amount=100, invoice_date=date(2026, 3, 1))`.
3. `a1_id = A1.id`

**When**
- `db.execute(text("DELETE FROM accounts WHERE id = :i"), {"i": a1_id})`, inside the wrap of `raises: IntegrityError`.

**Then**
1. raises: `exc.value.orig.pgcode == "23001"`.
2. count: `accounts` rows with `id == a1_id`: exactly 1.

### ACC-INH-10 — a SQL DELETE of an account with only tag links cascades to the links
- **Rules:** inherited R5 (database side)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = tag, `name "Supplier"`, `tag_code "supplier"`.
2. A1 = account, `name "Acme Ltd"`.
3. L1 = link(A1, T1).
4. `a1_id = A1.id`

**When**
- `db.execute(text("DELETE FROM accounts WHERE id = :i"), {"i": a1_id})`.

**Then**
1. count: `accounts` rows with `id == a1_id`: exactly 0.
2. count: `account_tag_assignments` rows with `account_id == a1_id`: exactly 0.
3. count: `account_tags` rows with `id == T1.id`: exactly 1.

### ACC-INH-11 — remove of an account with no references deletes it and returns it
- **Rules:** inherited R5 (a)
- **Kind:** happy
- **Expect:** pass

**Given**
1. A1 = account, `name "Acme Ltd"`.
2. A2 = account, `name "Beta Co"`.
3. `a1_id = A1.id`

**When**
- `result = dao.remove(db, id=a1_id)`.

**Then**
1. returns: `result.id == a1_id`.
2. count: `accounts` rows with `id == a1_id`: exactly 0.
3. count: `accounts` rows with `id == A2.id`: exactly 1.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 (a) — `GET /accounts/by-tag/{tag_id}/` answers 404 for a deleted tag | `AccountService.get_accounts_by_tag_id` | Here the DAO returns `[]` once BUG-1481 is fixed (ACC-BT-07). |
| FU-1 (b), BUG-867 — `limit` has no lower bound on both account list endpoints (HR-7) | accounts endpoint / `AccountManager.search_accounts` | Here a negative `limit` raises `DataError` (ACC-IW-33, BT-13). |
| FU-1 (c) — each returned account reads its tags one by one (BUG-865, BUG-1486) | account service; `account_tag_assignment.cases.md` | No card here. |
| FU-2 — the work order manager accepts a soft-deleted account | work order manager spec | Here the raw lookup returns it (ACC-INH-05). |
| FU-3 — a future hard delete needs `passive_deletes=True` on the `tag_assignments` / `invoices` backrefs, or a translated refusal listing blockers | account model / any future hard-delete caller | Here today's ORM behaviour (23502) is pinned (ACC-INH-07, INH-08); those two cards change with that fix. |
| P3 — `search_by_name_in_workspace` is dead code | `docs/testing/dead-code-removal-checklist.md` | No card. |
| inherited R4 [BUG-100] — `get_by_workspace` / `get_multi` ordered by `id` | `tests/unit/dao/base.cases.md` | Fix in `app/dao/base.py`; not repeated. |
| Inherited generic behavior (paging, missing ids) | `tests/unit/dao/base.cases.md` | Only what `Account` changes has cards. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | inherited R1 (`AccountCreate`) | The schema's module and its required fields are not given. | Conventions assume `app.schemas.account`; ACC-INH-02 builds `AccountCreate(name="Acme Ltd", tag_ids=[])`. |
| 2 | inherited R5 ("referenced by invoices … refused") | No recipe for a referencing row in this spec. | ACC-INH-07 uses the `AccountInvoice(...)` recipe of `invoice_event.spec.md` (Notes), module assumed `app.models.account_invoice`. |
| 3 | `get_accounts_in_workspace` R5 [BUG-861] ("compared trimmed and case-insensitively") | Only argument-side examples; the stored side is not stated. | ACC-IW-19 reads it as both sides (stored `Supplier` found by `supplier`). Drop the card if only the argument is meant. |
| 4 | R8, `get_accounts_by_tag_id` R4 ("name case-insensitive") | How the case-insensitive key is written in SQL is not stated (and `DISTINCT` must go, per the BUG-866 note). | The strict recorders ACC-IW-28, BT-09 assert `lower(accounts.name)`; change with the fix if another form is used. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_accounts_in_workspace` | Returns | ACC-IW-01 |
| `get_accounts_in_workspace` | R1 | ACC-IW-01, ACC-IW-02, ACC-IW-03, ACC-IW-04, ACC-IW-05, ACC-IW-37 |
| `get_accounts_in_workspace` | R1a [BUG-878] | ACC-IW-06 |
| `get_accounts_in_workspace` | R2 | ACC-IW-01, ACC-IW-07 |
| `get_accounts_in_workspace` | R2 [BUG-637] | ACC-IW-08, ACC-IW-09, ACC-IW-43 |
| `get_accounts_in_workspace` | R3 | ACC-IW-10 |
| `get_accounts_in_workspace` | R3 [BUG-868] | ACC-IW-11, ACC-IW-12, ACC-IW-13 |
| `get_accounts_in_workspace` | R4 | ACC-IW-01, ACC-IW-14 |
| `get_accounts_in_workspace` | R5 | ACC-IW-15, ACC-IW-16, ACC-IW-20, ACC-IW-21, ACC-IW-38, ACC-IW-39, ACC-IW-40, ACC-IW-41 |
| `get_accounts_in_workspace` | R5 [BUG-861] | ACC-IW-17, ACC-IW-18, ACC-IW-19 |
| `get_accounts_in_workspace` | R6 [BUG-864] | ACC-IW-22; ACC-IW-23 (pass companion) |
| `get_accounts_in_workspace` | R7 | ACC-IW-23, ACC-IW-24, ACC-IW-25, ACC-IW-42 |
| `get_accounts_in_workspace` | R8 [BUG-866] | ACC-IW-27, ACC-IW-28 |
| `get_accounts_in_workspace` | R9 | ACC-IW-26 |
| `get_accounts_in_workspace` | R10 | ACC-IW-29, ACC-IW-30, ACC-IW-31, ACC-IW-32, ACC-IW-33, ACC-IW-34, ACC-IW-35, ACC-IW-42 |
| `get_accounts_in_workspace` | Errors row 1 | ACC-IW-33 |
| `get_accounts_in_workspace` | Errors row 2 | ACC-IW-34 |
| `get_accounts_in_workspace` | Side effects | ACC-IW-36 |
| `count_active_accounts` | Returns | ACC-CNT-01 |
| `count_active_accounts` | R1 | ACC-CNT-01 |
| `count_active_accounts` | R2 | ACC-CNT-02 |
| `count_active_accounts` | R3 | ACC-CNT-03 |
| `get_accounts_by_tag_id` | Returns | ACC-BT-01 |
| `get_accounts_by_tag_id` | R1 | ACC-BT-01, ACC-BT-02, ACC-BT-03, ACC-BT-04, ACC-BT-17, ACC-BT-18 |
| `get_accounts_by_tag_id` | R2 | ACC-BT-05, ACC-BT-06, ACC-BT-19 |
| `get_accounts_by_tag_id` | R3 [BUG-1481] | ACC-BT-07 |
| `get_accounts_by_tag_id` | R4 [BUG-1480] | ACC-BT-08, ACC-BT-09 |
| `get_accounts_by_tag_id` | R5 | ACC-BT-10, ACC-BT-11, ACC-BT-12, ACC-BT-13, ACC-BT-14, ACC-BT-15 |
| `get_accounts_by_tag_id` | Errors row 1 | ACC-BT-13 |
| `get_accounts_by_tag_id` | Errors row 2 | ACC-BT-14 |
| `get_accounts_by_tag_id` | Side effects | ACC-BT-16 |
| inherited | R1 | ACC-INH-01, ACC-INH-02 |
| inherited | R2 | ACC-INH-03 |
| inherited | R3 | ACC-INH-04, ACC-INH-05, ACC-INH-06 |
| inherited | R4 [BUG-100] | Deferred (`base.cases.md`) |
| inherited | R5 | ACC-INH-07, ACC-INH-08, ACC-INH-09, ACC-INH-10, ACC-INH-11 |
