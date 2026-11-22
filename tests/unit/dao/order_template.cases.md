# Test cases — `app/dao/order_template.py`

> **Spec:** `tests/unit/dao/order_template.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open). Q1 was decided by Claude under the reviewer's delegation; O1 is the owner's answer.
> **Revision:** 1 — the spec did not change. Additive, from `order_template.verify.md` (case-missing Findings 1 … 4; recipes R-1 … R-4): Finding 1 → OTP-GW-34 … GW-38; Finding 2 → OTP-GW-39; Finding 3 → OTP-GI-08, II-08; Finding 4 → OTP-GW-40, GI-09, GT-16, II-09. Conventions gain the `session:` line. Spec gap 6 now names GW-38. No existing Given, When, Then or ID changed, none retired.
> **Counts:** 74 cases · 67 expected-to-pass · 7 expected-to-fail (bugs) · 10 deferred

## Reviewer summary
- **Per callable:** `OrderTemplateDAO.get_by_workspace` 40 (4 bug) · `OrderTemplateDAO.get_by_id_and_workspace` 9 · `OrderTemplateItemDAO.get_by_template` 16 (3 bug) · `OrderTemplateItemDAO.get_by_id_and_workspace` 9.
- **Depth:** lighter target (skill step 1a). Four plain filtered reads: nothing here writes stock, money or order state. Line prices are only read back, and BUG-1226, the money bug the spec found, is the manager's, so a Deferred entry.
- **Expected-to-fail:** BUG-1210 4: GW-17, GW-18, GW-19 non-strict, GW-20 strict (the SQL recorder). BUG-1211 3: GT-08, GT-09 non-strict, GT-10 strict.
- **Commit spies:** none. All four only read, and no writer has code here.
- **Notable design choices:**
  - **Sort keys.** The tie cards GW-18 and GT-09 give name, flag, category, quantity and price values that are neither rising nor falling with `id`, so a second key placed before `id` cannot pass. GW-14 mixes stamp, id and name the same way. GW-20 and GT-10 also count the terms of `ORDER BY`.
  - GW-16 and GT-07 are the passing companions: both tied rows come back, in the right place between the others.
  - GW-19 is the one card with a repeated call in its When, one list comprehension: "no repeats, no gaps" cannot be seen in one window.
  - **Filters before the page:** GW-22, GW-23 put the hidden row inside the skipped part, so a filter in Python after paging gives another row.
  - **Real states:** a "deleted" template is `is_active False` and nothing else, as `delete_template` leaves it.
  - GT-12, GT-13 build the invalid row of R4 on purpose, because the rule states what the raw read does with it.
  - "Writes nothing": each list one card, each by-id read a miss and a hit, all with `len(db.new)`, and one card per reader with an edited row in the session.
  - No `Author:` lines, non-strict cards included: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `OTP` = `app/dao/order_template.py`. `GW` `OrderTemplateDAO.get_by_workspace` · `GI` `OrderTemplateDAO.get_by_id_and_workspace` · `GT` `OrderTemplateItemDAO.get_by_template` · `II` `OrderTemplateItemDAO.get_by_id_and_workspace`.

**Actors and fixed values.**
- `dao` = the singleton `order_template_dao`, `idao` = the singleton `order_template_item_dao` (both from `app.dao.order_template`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `OrderTemplate` = `app.models.order_template.OrderTemplate`. `OrderTemplateItem` = `app.models.order_template_item.OrderTemplateItem`. `Decimal` = `decimal.Decimal`. `datetime`, `timedelta` = the `datetime` module's classes.
- MISSING = `999999999`: an id that no row of any table has. T9, T10, T11, T12 = `datetime(2026, 3, 4, 9, 0, 0)` … `datetime(2026, 3, 4, 12, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from the defaults below. A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending.
- W1, W2 = two `workspaces` rows from `make_workspace`; they exist in every test and need no Given line. No template exists unless the card's Given lists it.
- **template** = `OrderTemplate(workspace_id=W1.id, template_name="Rent", requires_approval=True, auto_approve=False)`; `is_active` is left to its default, `True`; `expense_category` is not passed. The card always gives `created_at`; after the word "but" it lists every other column that differs.
- **line on T** = `OrderTemplateItem(workspace_id=W1.id, order_template_id=T.id, description="Line", quantity=Decimal("1"))`; the card always gives `line_number`; after the word "but" it lists every other column that differs.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line). **unchanged(X) except `c`, …** = the same, leaving out the columns named.
- **nothing written** = the numbers of `order_templates` and of `order_template_items` rows stored (all workspaces) equal their values before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P after the call, on the object itself. `pending: len(db.new) == 1` checks that P is the only object waiting in the session.
- A `session:` line is a check on the session object.
- `raises: DataError` = `sqlalchemy.exc.DataError`. Wrap the When: `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the When; keep using `db` afterwards. Further `raises:` lines are assertions on `exc.value`, written after the `with` block, one `assert` per line.

**xfail cards.** Write the call and the checks exactly as shown; add `pytest.mark.xfail(strict=True, reason="BUG-NNN")`, or `strict=False` on a card whose Expect line says `(non-strict)`. The assertion of a non-strict card is never weakened.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` sent; `order_part` = the text of `sql` after its first `ORDER BY` and before any `LIMIT` (`""` when there is no `ORDER BY`); `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `OrderTemplateDAO.get_by_workspace`

### OTP-GW-01 — with the defaults: a list of the workspace's rows, active and inactive, newest first
- **Rules:** `OrderTemplateDAO.get_by_workspace` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Lease"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `isinstance(result[0], OrderTemplate)`.

### OTP-GW-02 — a newer row of another workspace is not returned
- **Rules:** `OrderTemplateDAO.get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. Z = template, `created_at T12`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### OTP-GW-03 — an unknown workspace returns an empty list
- **Rules:** `OrderTemplateDAO.get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### OTP-GW-04 — a workspace with no templates returns an empty list
- **Rules:** `OrderTemplateDAO.get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### OTP-GW-05 — is_active=None returns active and inactive rows
- **Rules:** `OrderTemplateDAO.get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Lease"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=None)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### OTP-GW-06 — is_active=True returns the active rows only
- **Rules:** `OrderTemplateDAO.get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Lease"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=True)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### OTP-GW-07 — is_active=False returns the inactive rows only
- **Rules:** `OrderTemplateDAO.get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Lease"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=False)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### OTP-GW-08 — a category keeps the rows equal to it exactly, case-sensitive
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Lease"`, `expense_category "Factory"`.
3. C = template, `created_at T12`, but `template_name "Power"`, `expense_category "department"`.
4. D = template, `created_at T9`, but `template_name "Misc"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="factory")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### OTP-GW-09 — a category is not trimmed
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="factory ")`.

**Then**
1. returns: `result == []`.

### OTP-GW-10 — a blank category is a filter and finds nothing
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category=" ")`.

**Then**
1. returns: `result == []`.

### OTP-GW-11 — % is no wildcard in a category
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="%")`.

**Then**
1. returns: `result == []`.

### OTP-GW-12 — expense_category=None applies no filter
- **Rules:** `OrderTemplateDAO.get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category=None)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### OTP-GW-13 — expense_category="" applies no filter
- **Rules:** `OrderTemplateDAO.get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="")`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### OTP-GW-14 — rows come newest first, whatever their ids and names
- **Rules:** `OrderTemplateDAO.get_by_workspace` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `template_name "Mid"`.
2. B = template, `created_at T12`, but `template_name "Abe"`.
3. C = template, `created_at T11`, but `template_name "Zed"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.

### OTP-GW-15 — the order is applied before the page is cut
- **Rules:** `OrderTemplateDAO.get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `template_name "Mid"`.
2. B = template, `created_at T12`, but `template_name "Abe"`.
3. C = template, `created_at T11`, but `template_name "Zed"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [C.id]`.

### OTP-GW-16 — on a tie both rows are returned, between the newer and the older
- **Rules:** `OrderTemplateDAO.get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T11`, but `template_name "Lease"`.
3. C = template, `created_at T12`, but `template_name "Power"`.
4. D = template, `created_at T10`, but `template_name "Misc"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### OTP-GW-17 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]
- **Kind:** bug
- **Expect:** xfail BUG-1210 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; the result rests on physical row order, which can match the intended one by accident)

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T11`, but `template_name "Lease"`.
3. C = template, `created_at T11`, but `template_name "Power"`.
4. `A.template_name = "Rent two"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### OTP-GW-18 — on a tie the id decides, when name, flag and category would each sort otherwise
- **Rules:** `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]
- **Kind:** bug
- **Expect:** xfail BUG-1210 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; the result rests on physical row order, which can match the intended one by accident)

**Given**
1. A = template, `created_at T11`, but `template_name "Mid"`, `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Zed"`, `expense_category "other"`, `is_active False`.
3. C = template, `created_at T11`, but `template_name "Abe"`, `expense_category "department"`.
4. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### OTP-GW-19 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]
- **Kind:** bug
- **Expect:** xfail BUG-1210 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; the spec saw one row twice and one never)

**Given**
1. A = template, `created_at T11`, but `template_name "Rent"`.
2. B = template, `created_at T11`, but `template_name "Lease"`.
3. C = template, `created_at T11`, but `template_name "Power"`.
4. D = template, `created_at T11`, but `template_name "Misc"`.
5. E = template, `created_at T11`, but `template_name "Water"`.
6. `A.template_name = "Rent two"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `pages = [dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension, as a single window cannot show this).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [E.id, D.id, C.id, B.id, A.id]`.

### OTP-GW-20 — the query orders by created_at, then id, both descending
- **Rules:** `OrderTemplateDAO.get_by_workspace` R5 [BUG-1210]
- **Kind:** bug
- **Expect:** xfail BUG-1210
- **Fails today on:** Then 4 (the query orders by `created_at` alone)

**Given**
1. A = template, `created_at T10`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"created_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("created_at") < order_part.index(".id")`.
6. statement: `order_part.upper().count("DESC") == 2`.
7. statement: `order_part.count(",") == 1`.

### OTP-GW-21 — filters combine with AND
- **Rules:** `OrderTemplateDAO.get_by_workspace` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.
2. B = template, `created_at T11`, but `template_name "Lease"`, `expense_category "factory"`, `is_active False`.
3. C = template, `created_at T12`, but `template_name "Power"`, `expense_category "department"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=True, expense_category="factory")`.

**Then**
1. returns: `ids(result) == [A.id]`.

### OTP-GW-22 — is_active is applied before the page: a hidden row takes no place in it
- **Rules:** `OrderTemplateDAO.get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = template, `created_at T12`, but `template_name "Off"`, `is_active False`.
2. A = template, `created_at T11`.
3. B = template, `created_at T10`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=True, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### OTP-GW-23 — the category is applied before the page: a hidden row takes no place in it
- **Rules:** `OrderTemplateDAO.get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = template, `created_at T12`, but `template_name "Off"`, `expense_category "department"`.
2. A = template, `created_at T11`, but `expense_category "factory"`.
3. B = template, `created_at T10`, but `template_name "Lease"`, `expense_category "factory"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="factory", skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### OTP-GW-24 — skip and limit cut a window
- **Rules:** `OrderTemplateDAO.get_by_workspace` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T12`.
2. B = template, `created_at T11`, but `template_name "Lease"`.
3. C = template, `created_at T10`, but `template_name "Power"`.
4. D = template, `created_at T9`, but `template_name "Misc"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### OTP-GW-25 — with the defaults 101 rows give the newest 100
- **Rules:** `OrderTemplateDAO.get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all`: Ek = template, `created_at` = `T10 + timedelta(minutes=k)`, but `template_name` = `f"Rent {k}"`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### OTP-GW-26 — limit=1000 gives all 101
- **Rules:** `OrderTemplateDAO.get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all`: Ek = template, `created_at` = `T10 + timedelta(minutes=k)`, but `template_name` = `f"Rent {k}"`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### OTP-GW-27 — limit=0 returns an empty list
- **Rules:** `OrderTemplateDAO.get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### OTP-GW-28 — limit=1 returns one row
- **Rules:** `OrderTemplateDAO.get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### OTP-GW-29 — skip past the end returns an empty list
- **Rules:** `OrderTemplateDAO.get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### OTP-GW-30 — skip at the last row returns it
- **Rules:** `OrderTemplateDAO.get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Lease"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### OTP-GW-31 — a negative limit raises
- **Rules:** `OrderTemplateDAO.get_by_workspace` R8, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Lease"`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### OTP-GW-32 — a negative skip raises
- **Rules:** `OrderTemplateDAO.get_by_workspace` R8, Errors row 2
- **Kind:** error
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Lease"`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### OTP-GW-33 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `OrderTemplateDAO.get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. `P = OrderTemplate(workspace_id=W1.id, template_name="Pending", requires_approval=True, auto_approve=False, created_at=T12)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### OTP-GW-34 — a category in capitals does not find a lower-case one
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="FACTORY")`.

**Then**
1. returns: `result == []`.

### OTP-GW-35 — a leading space in the category finds nothing
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category=" factory")`.

**Then**
1. returns: `result == []`.

### OTP-GW-36 — the start of a category finds nothing
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="fact")`.

**Then**
1. returns: `result == []`.

### OTP-GW-37 — the end of a category finds nothing
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="tory")`.

**Then**
1. returns: `result == []`.

### OTP-GW-38 — _ is no wildcard in a category
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category "factory"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="f_ctory")`.

**Then**
1. returns: `result == []`.

### OTP-GW-39 — a stored category with a space is not found: the stored side is not trimmed
- **Rules:** `OrderTemplateDAO.get_by_workspace` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `expense_category " factory"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, expense_category="factory")`.

**Then**
1. returns: `result == []`.

### OTP-GW-40 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `OrderTemplateDAO.get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T10`, but `workspace_id W2.id`.
3. `B.expense_category = "other"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## `OrderTemplateDAO.get_by_id_and_workspace`

### OTP-GI-01 — returns the row with that id
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = template, `created_at T10`, but `template_name "Lease"`.
2. A = template, `created_at T11`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, OrderTemplate)`.
2. returns: `result.id == A.id`.
3. returns: `result.template_name == "Rent"`, `result.workspace_id == W1.id`.
4. returns: `result.created_at == T11`.

### OTP-GI-02 — another workspace's id returns None
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. Z = template, `created_at T11`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OTP-GI-03 — the id under another workspace returns None
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### OTP-GI-04 — an unknown id returns None
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OTP-GI-05 — an inactive template is returned
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `is_active False`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_active is False`.

### OTP-GI-06 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. `P = OrderTemplate(workspace_id=W1.id, template_name="Pending", requires_approval=True, auto_approve=False, created_at=T12)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### OTP-GI-07 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. `P = OrderTemplate(workspace_id=W1.id, template_name="Pending", requires_approval=True, auto_approve=False, created_at=T12)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.
5. statement: `written == []`.

### OTP-GI-08 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, `created_at T10`, but `workspace_id W2.id`.
2. A = template, `created_at T11`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OTP-GI-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `OrderTemplateDAO.get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`.
3. `B.expense_category = "other"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## `OrderTemplateItemDAO.get_by_template`

### OTP-GT-01 — returns a list of the template's lines, with their numbers as stored
- **Rules:** `OrderTemplateItemDAO.get_by_template` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`, but `quantity Decimal("2.00")`, `unit_price Decimal("10.00")`, `line_subtotal Decimal("20.00")`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id]`.
3. returns: `isinstance(result[0], OrderTemplateItem)`.
4. returns: `result[0].quantity == Decimal("2.00")`, `result[0].unit_price == Decimal("10.00")`, `result[0].line_subtotal == Decimal("20.00")`.

### OTP-GT-02 — an earlier line of another template is not returned
- **Rules:** `OrderTemplateItemDAO.get_by_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = template, `created_at T9`, but `template_name "Lease"`.
2. T = template, `created_at T10`.
3. B = line on S, `line_number 1`.
4. A = line on T, `line_number 2`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### OTP-GT-03 — a template with no lines returns an empty list
- **Rules:** `OrderTemplateItemDAO.get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = template, `created_at T9`, but `template_name "Lease"`.
2. T = template, `created_at T10`.
3. B = line on S, `line_number 1`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### OTP-GT-04 — an unknown template returns an empty list
- **Rules:** `OrderTemplateItemDAO.get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.

**When**
- `result = idao.get_by_template(db, order_template_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### OTP-GT-05 — there is no cap: 101 lines give 101 rows
- **Rules:** `OrderTemplateItemDAO.get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. 101 lines E1 … E101, built with `add_all`: Ek = line on T, `line_number` = `k`.
3. `in_order` = the ids of E1, E2, … E101, in that order.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### OTP-GT-06 — lines stored out of order come back 1, 2, 3
- **Rules:** `OrderTemplateItemDAO.get_by_template` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 3`, but `quantity Decimal("2")`.
3. B = line on T, `line_number 1`, but `quantity Decimal("3")`.
4. C = line on T, `line_number 2`, but `quantity Decimal("1")`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, C.id, A.id]`.
2. returns: `[r.line_number for r in result] == [1, 2, 3]`.

### OTP-GT-07 — on a tie both lines are returned, between the lower and the higher number
- **Rules:** `OrderTemplateItemDAO.get_by_template` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 2`.
3. B = line on T, `line_number 2`.
4. C = line on T, `line_number 1`.
5. D = line on T, `line_number 3`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### OTP-GT-08 — on a tie the lowest id comes first, when the lowest id was updated
- **Rules:** `OrderTemplateItemDAO.get_by_template` R2 [BUG-1211]
- **Kind:** bug
- **Expect:** xfail BUG-1211 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; the result rests on physical row order, which can match the intended one by accident)

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.
3. B = line on T, `line_number 1`.
4. C = line on T, `line_number 1`.
5. `A.quantity = Decimal("5")`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### OTP-GT-09 — on a tie the id decides, when quantity and price would each sort otherwise
- **Rules:** `OrderTemplateItemDAO.get_by_template` R2 [BUG-1211]
- **Kind:** bug
- **Expect:** xfail BUG-1211 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; with no update physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`, but `quantity Decimal("2")`, `unit_price Decimal("7.00")`.
3. B = line on T, `line_number 1`, but `quantity Decimal("3")`, `unit_price Decimal("9.00")`.
4. C = line on T, `line_number 1`, but `quantity Decimal("1")`, `unit_price Decimal("5.00")`.
5. `db.expire_all()`

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### OTP-GT-10 — the query orders by line_number, then id, ascending
- **Rules:** `OrderTemplateItemDAO.get_by_template` R2 [BUG-1211]
- **Kind:** bug
- **Expect:** xfail BUG-1211
- **Fails today on:** Then 4 (the query orders by `line_number` alone)

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.
3. A recorder for the SQL statements the session sends during the When.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"line_number" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("line_number") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.
7. statement: `order_part.count(",") == 1`.

### OTP-GT-11 — a call with another workspace returns an empty list
- **Rules:** `OrderTemplateItemDAO.get_by_template` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### OTP-GT-12 — a line of workspace W2 on a template of W1 is returned for W2
- **Rules:** `OrderTemplateItemDAO.get_by_template` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### OTP-GT-13 — a line of workspace W2 on a template of W1 is not returned for W1
- **Rules:** `OrderTemplateItemDAO.get_by_template` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### OTP-GT-14 — the lines of an inactive template are returned
- **Rules:** `OrderTemplateItemDAO.get_by_template` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, `created_at T10`, but `is_active False`.
2. A = line on T, `line_number 1`.
3. B = line on T, `line_number 2`.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### OTP-GT-15 — writes nothing: an earlier pending line stays pending and is not returned
- **Rules:** `OrderTemplateItemDAO.get_by_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 2`.
3. `P = OrderTemplateItem(workspace_id=W1.id, order_template_id=T.id, line_number=1, description="Pending", quantity=Decimal("1"))`
4. `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### OTP-GT-16 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `OrderTemplateItemDAO.get_by_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. S = template, `created_at T9`, but `template_name "Lease"`.
3. A = line on T, `line_number 1`.
4. B = line on S, `line_number 1`.
5. `B.description = "Edited"` (not flushed).

**When**
- `result = idao.get_by_template(db, order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## `OrderTemplateItemDAO.get_by_id_and_workspace`

### OTP-II-01 — returns the line with that id, its numbers as stored
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. B = line on T, `line_number 1`.
3. A = line on T, `line_number 2`, but `quantity Decimal("2.00")`, `unit_price Decimal("10.00")`, `line_subtotal Decimal("20.00")`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, OrderTemplateItem)`.
2. returns: `result.id == A.id`.
3. returns: `result.order_template_id == T.id`, `result.workspace_id == W1.id`, `result.line_number == 2`.
4. returns: `result.quantity == Decimal("2.00")`, `result.unit_price == Decimal("10.00")`, `result.line_subtotal == Decimal("20.00")`.

### OTP-II-02 — another workspace's id returns None
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.
3. Z = line on T, `line_number 2`, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OTP-II-03 — the id under another workspace returns None
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### OTP-II-04 — an unknown id returns None
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OTP-II-05 — a line of an inactive template is returned
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, `created_at T10`, but `is_active False`.
2. A = line on T, `line_number 1`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### OTP-II-06 — writes nothing: a read that finds nothing leaves the session as it was
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.
3. `P = OrderTemplateItem(workspace_id=W1.id, order_template_id=T.id, line_number=1, description="Pending", quantity=Decimal("1"))`
4. `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. nothing written: nothing written.
6. unchanged: unchanged(A).
7. statement: `written == []`.

### OTP-II-07 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.
3. `P = OrderTemplateItem(workspace_id=W1.id, order_template_id=T.id, line_number=1, description="Pending", quantity=Decimal("1"))`
4. `db.add(P)` (not flushed).
5. A recorder for the SQL statements the session sends during the When.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. nothing written: nothing written.
5. statement: `written == []`.

### OTP-II-08 — another workspace's id returns None, when that row is the earlier one
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. Z = line on T, `line_number 1`, but `workspace_id W2.id`.
3. A = line on T, `line_number 2`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### OTP-II-09 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `OrderTemplateItemDAO.get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, `line_number 1`.
3. B = line on T, `line_number 2`.
4. `B.description = "Edited"` (not flushed).

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| BUG-1226 (O1) — a `unit_price` of 0 gives a subtotal of 0 | `OrderTemplateManager.update_item`, FU-1 (d) | **Money.** The rule is the manager's. The owner's answer: quantity × 0 = 0. |
| BUG-1216 (HR-16) — `cost_center_id`, `default_approver_id` of another workspace refused | `OrderTemplateManager.create_template`, `update_template`, FU-1 (a) | **Money and order.** The expense order made from such a template fails with 404. |
| BUG-1014 — the account of a template | `OrderTemplateManager` | **Money.** Existing bug, FU-1 (a). |
| FU-1 (b) — `expense_category` takes any text | `OrderTemplateManager`, as BUG-360 | R3 here stays an exact compare. |
| FU-1 (c) — `update_template` stamps `updated_by` on every call (HR-9) | `OrderTemplateManager` | Read, not run. |
| FU-1 (e) — `OrderTemplateCreate` has no trim or blank check (HR-1) | `app/schemas/order_template.py` | Schema rule. |
| Q1 — `POST /expense-orders/from-template/{id}/` refuses an inactive template with 400 | `create_expense_order_from_template` | **Order.** This DAO returns the row, by rule. |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0` | `GET /order-templates/` | Endpoint rule; the DAO's own negatives are GW-31, GW-32. |
| Generic behavior of inherited methods; `OrderTemplateItemDAO.get_by_workspace`, `get_multi`, `remove` | `tests/unit/dao/base.spec.md` / `base.cases.md` | No caller on either DAO. |
| Module singletons `order_template_dao`, `order_template_item_dao` | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Notes: keyword-only parameters | Stated as a note, not as a rule. | No card, as in `work_order_approver.cases.md` gap 1. |
| 2 | Model facts | **Money and order.** The spec lists some columns of each table. `description` on a line, and `requires_approval`, `auto_approve` on a template, come from `tests/unit/managers/test_expense_order_manager.py`. The line's module is written `…order_template_item`. | Conventions pass them, and use `app.models.order_template_item`. A wrong one fails in every test of the section. |
| 3 | Model facts, Review HR-15 | **Money.** `Numeric(15, 2)` rounds half away from zero (`3 × 0.125` → `0.38`, verified). A fact of the column, not a rule of this DAO. | No card: nothing here computes a value. GT-01, II-01 read stored values back. |
| 4 | Not specified: `remove` | **Order.** On a template with items it raises `IntegrityError` 23502 (verified). No caller, so no rule. | No card. |
| 5 | `get_by_template` R1 | "all of them" names no number. | OTP-GT-05 uses 101, the same as `get_by_workspace` R7. |
| 6 | `get_by_workspace` R3 | "no wildcards" names `%` only; `_` is not named. | OTP-GW-38 tests it anyway, from the verifier's recipe R-1. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `OrderTemplateDAO.get_by_workspace` | Returns | OTP-GW-01 |
| `OrderTemplateDAO.get_by_workspace` | R1 | OTP-GW-01, OTP-GW-02, OTP-GW-03, OTP-GW-04 |
| `OrderTemplateDAO.get_by_workspace` | R2 | OTP-GW-01, OTP-GW-05, OTP-GW-06, OTP-GW-07 |
| `OrderTemplateDAO.get_by_workspace` | R3 | OTP-GW-08, OTP-GW-09, OTP-GW-10, OTP-GW-11, OTP-GW-34, OTP-GW-35, OTP-GW-36, OTP-GW-37, OTP-GW-38, OTP-GW-39 |
| `OrderTemplateDAO.get_by_workspace` | R4 | OTP-GW-12, OTP-GW-13 |
| `OrderTemplateDAO.get_by_workspace` | R5 | OTP-GW-14, OTP-GW-15, OTP-GW-16 |
| `OrderTemplateDAO.get_by_workspace` | R5 [BUG-1210] | OTP-GW-17, OTP-GW-18, OTP-GW-19, OTP-GW-20 |
| `OrderTemplateDAO.get_by_workspace` | R6 | OTP-GW-21, OTP-GW-22, OTP-GW-23 |
| `OrderTemplateDAO.get_by_workspace` | R7 | OTP-GW-24, OTP-GW-25, OTP-GW-26 |
| `OrderTemplateDAO.get_by_workspace` | R8 | OTP-GW-27, OTP-GW-28, OTP-GW-29, OTP-GW-30, OTP-GW-31, OTP-GW-32 |
| `OrderTemplateDAO.get_by_workspace` | Errors row 1 | OTP-GW-31 |
| `OrderTemplateDAO.get_by_workspace` | Errors row 2 | OTP-GW-32 |
| `OrderTemplateDAO.get_by_workspace` | Side effects | OTP-GW-33, OTP-GW-40 |
| `OrderTemplateDAO.get_by_id_and_workspace` | Returns | OTP-GI-01 |
| `OrderTemplateDAO.get_by_id_and_workspace` | R1 | OTP-GI-01 |
| `OrderTemplateDAO.get_by_id_and_workspace` | R2 | OTP-GI-02, OTP-GI-03, OTP-GI-04, OTP-GI-06, OTP-GI-08 |
| `OrderTemplateDAO.get_by_id_and_workspace` | R3 | OTP-GI-05 |
| `OrderTemplateDAO.get_by_id_and_workspace` | Side effects | OTP-GI-06, OTP-GI-07, OTP-GI-09 |
| `OrderTemplateItemDAO.get_by_template` | Returns | OTP-GT-01 |
| `OrderTemplateItemDAO.get_by_template` | R1 | OTP-GT-01, OTP-GT-02, OTP-GT-03, OTP-GT-04, OTP-GT-05 |
| `OrderTemplateItemDAO.get_by_template` | R2 | OTP-GT-06, OTP-GT-07 |
| `OrderTemplateItemDAO.get_by_template` | R2 [BUG-1211] | OTP-GT-08, OTP-GT-09, OTP-GT-10 |
| `OrderTemplateItemDAO.get_by_template` | R3 | OTP-GT-11 |
| `OrderTemplateItemDAO.get_by_template` | R4 | OTP-GT-12, OTP-GT-13 |
| `OrderTemplateItemDAO.get_by_template` | R5 | OTP-GT-14 |
| `OrderTemplateItemDAO.get_by_template` | Side effects | OTP-GT-15, OTP-GT-16 |
| `OrderTemplateItemDAO.get_by_id_and_workspace` | Returns | OTP-II-01 |
| `OrderTemplateItemDAO.get_by_id_and_workspace` | R1 | OTP-II-01 |
| `OrderTemplateItemDAO.get_by_id_and_workspace` | R2 | OTP-II-02, OTP-II-03, OTP-II-04, OTP-II-06, OTP-II-08 |
| `OrderTemplateItemDAO.get_by_id_and_workspace` | R3 | OTP-II-05 |
| `OrderTemplateItemDAO.get_by_id_and_workspace` | Side effects | OTP-II-06, OTP-II-07, OTP-II-09 |
