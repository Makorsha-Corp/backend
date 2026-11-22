# Test cases — `app/dao/project_member.py`

> **Spec:** `tests/unit/dao/project_member.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-02; nothing open).
> **Revision:** 1 — the spec did not change. Additive, from `project_member.verify.md` (case-missing Findings 1, 2; recipes R-1, R-2): R-1 → PMB-G-18, PMB-GU-10; R-2 → PMB-G-19, PMB-GU-11. New Then lines are numbered last, so no existing Then number moved. No ID retired.
> **Counts:** 30 cases · 27 expected-to-pass · 3 expected-to-fail (bugs) · 4 deferred

## Reviewer summary
- **Per callable:** `get_by_project` 19 (3 bug) · `get_by_project_and_user` 11.
- **Depth:** lighter target (skill step 1a): two thin raw reads; the module writes no stock, money or order state.
- **Expected-to-fail:** BUG-1274 3: PMB-G-11, PMB-G-12 non-strict, PMB-G-13 strict (the SQL recorder). PMB-G-10 is the passing companion.
- **Commit spies:** none. Both methods only read, and the inherited writers have no caller here.
- **Notable design choices:** BUG-1280 is deferred, because its rule is the workspace manager's and these reads stay raw. The writes-nothing cards forbid `projects` and `workspace_members` in the statement, so a filter on a closed project or a person who left fails. No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Revision 1:** PMB-G-18, PMB-GU-10 (a W2 row asked for in W1, on both reads); PMB-G-19, PMB-GU-11 (an unflushed edit stays unflushed).
- **Needs a decision:** None blocking.

## Conventions for this module

**IDs.** `PMB` = `app/dao/project_member.py`. `G` get_by_project · `GU` get_by_project_and_user.

**Actors and fixed values.**
- `dao` = the singleton `project_member_dao` (`from app.dao.project_member import project_member_dao`). `db` = the test's real database session, always the first argument; every other argument is passed by keyword. `result` = what the When call returns.
- `ProjectMember` = `app.models.project_member.ProjectMember`. `Factory` = `app.models.factory.Factory`. `Project` = `app.models.project.Project`. `WorkspaceMember` = `app.models.workspace_member.WorkspaceMember`. `datetime`, `timedelta` = the `datetime` module's classes. `text` = `sqlalchemy.text`.
- MISSING = `999999999`: an id that no row of any table has.
- T9 = `datetime(2026, 3, 4, 9, 0, 0)`, T10 = `datetime(2026, 3, 4, 10, 0, 0)`, T11 = `datetime(2026, 3, 4, 11, 0, 0)`, T12 = `datetime(2026, 3, 4, 12, 0, 0)`.

**Externals.** None. Nothing is mocked. No method reads the clock.

**Given rows.** Rows are inserted directly into the tables (never through `dao`) and flushed one at a time in the order written, so ids rise in that order. The session does not autoflush. A card names, by column name, every column that differs from these defaults.
- These rows exist in every test and need no Given line (workspaces and the profile from `make_workspace`, `make_profile`; the rest built directly, add + flush):
  - W1, W2 = two `workspaces` rows. U1 = a `profiles` row.
  - F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`.
  - PJ1 = `Project(workspace_id=W1.id, factory_id=F1.id, name="Project One", description="Main")`. PJ2 = the same, but `name "Project Two"`. PJD = the same, but `name "Project Three"`, `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`.
  - U2, U3 = two more `profiles` rows.
- **member** = `project_members` row built with `ProjectMember`: `workspace_id W1.id`, `project_id PJ1.id`, `user_id U1.id`; `assigned_by` is not passed. The card always gives `assigned_at`; after the word "but" it lists every other column that differs.
- **left U** = a `WorkspaceMember(workspace_id=W1.id, user_id=U.id, role="member", status="inactive")` row: the membership of someone removed from W1.
- No `project_members` row exists unless the card's Given lists it.
- A Given line written as code is a step to run exactly as written, at that place in the order. `db.add(...)` without `db.flush()` leaves the row pending. "it is a standing row" means that row is not inserted again; the line only says what it holds.

**Named checks.**
- **ids(result)** = `[r.id for r in result]` — the list in the order returned; the order is part of the check.
- **re-read X** = `db.expire_all()`, then SELECT X by id; the listed values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value before the call (snapshot taken after the last Given line).
- **nothing written** = the number of `project_members` rows stored (all workspaces) equals its value before the call. A pending row is not stored, so it does not count.
- `pending:` lines check the row P and the session after the call, before anything expires it: `db.new`, `db.dirty`, `db.deleted` as the session holds them. A card lists them ahead of its `nothing written:` and `unchanged:` lines; keep that order.
- **seqscan** = run, in this order, `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`: transaction-local, gone with the rollback. Today's read then follows physical row order.

**xfail cards.** Write the call and the checks exactly as shown. `Expect: xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `xfail BUG-n (non-strict)` = `strict=False`, for a card comparing an order that rests on physical row order. The assertion of a non-strict card is never weakened. Bugs here: BUG-1274.

**Statement recorder.** The SQL statements the session sends during the When are recorded. `sql` = the text of the one `SELECT` from `project_members`; `order_part` = the text of `sql` after its first `ORDER BY` (`""` when there is none); `selects` = every `SELECT` recorded; `written` = every recorded `INSERT`, `UPDATE` or `DELETE`. A `statement:` line is a check on these.

**Race simulations.** None in this module.

## `ProjectMemberDAO.get_by_project`

### PMB-G-01 — returns a list of the project's members
- **Rules:** `get_by_project` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.
2. B = member, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id]`.
3. returns: `isinstance(result[0], ProjectMember)`.

### PMB-G-02 — a member of another project of the same workspace is not returned, though it sorts first
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member, `assigned_at T11`, but `user_id U2.id`.
2. B = member, `assigned_at T10`, but `project_id PJ2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PMB-G-03 — the right project under another workspace returns an empty list
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### PMB-G-04 — an unknown workspace returns an empty list
- **Rules:** `get_by_project` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### PMB-G-05 — an unknown project id returns an empty list
- **Rules:** `get_by_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project(db, project_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PMB-G-06 — project id 0 returns an empty list
- **Rules:** `get_by_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project(db, project_id=0, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PMB-G-07 — a project with no rows returns an empty list
- **Rules:** `get_by_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project(db, project_id=PJ2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PMB-G-08 — members are ordered by assigned_at ascending, whatever their ids
- **Rules:** `get_by_project` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member, `assigned_at T12`, but `user_id U3.id`.
2. B = member, `assigned_at T11`, but `user_id U2.id`.
3. C = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [C.id, B.id, A.id]`.

### PMB-G-09 — one microsecond inside one day decides the order, against id
- **Rules:** `get_by_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10 + timedelta(microseconds=1)`.
2. B = member, `assigned_at T10`, but `user_id U2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### PMB-G-10 — on a tie both members are returned, after the earlier one
- **Rules:** `get_by_project` R4, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T11`.
2. B = member, `assigned_at T11`, but `user_id U2.id`.
3. C = member, `assigned_at T10`, but `user_id U3.id`.
4. `A.assigned_by = U3.id`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:]} == {A.id, B.id}`.

### PMB-G-11 — on a tie the lowest id comes first, when the lower id was updated
- **Rules:** `get_by_project` R4 [BUG-1274]
- **Kind:** bug
- **Expect:** xfail BUG-1274 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; the updated lower id comes second, but that rests on physical row order)

**Given**
1. A = member, `assigned_at T11`.
2. B = member, `assigned_at T11`, but `user_id U2.id`.
3. seqscan.
4. `A.assigned_by = U3.id`, then `db.flush()`.
5. `db.expire_all()`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PMB-G-12 — on a tie the lowest id comes first, when the user would sort the other way
- **Rules:** `get_by_project` R4 [BUG-1274]
- **Kind:** bug
- **Expect:** xfail BUG-1274 (non-strict)
- **Fails today on:** Then 2 (no order is requested among the tied rows; physical order usually gives the intended result, which is why this card is non-strict)

**Given**
1. A = member, `assigned_at T11`, but `user_id U2.id`, `assigned_by U3.id`.
2. B = member, `assigned_at T11`, but `assigned_by U1.id`.
3. `db.expire_all()`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `ids(result) == [A.id, B.id]`.

### PMB-G-13 — the query orders by assigned_at, then id ascending
- **Rules:** `get_by_project` R4 [BUG-1274]
- **Kind:** bug
- **Expect:** xfail BUG-1274
- **Fails today on:** Then 4 (the query orders by `assigned_at` alone)

**Given**
1. A = member, `assigned_at T10`.
2. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `"assigned_at" in order_part`.
4. statement: `".id" in order_part`.
5. statement: `order_part.index("assigned_at") < order_part.index(".id")`.
6. statement: `"DESC" not in order_part.upper()`.

### PMB-G-14 — the members of a soft-deleted project are returned
- **Rules:** `get_by_project` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Project PJD has `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`: it is a standing row.
2. A = member, `assigned_at T10`, but `project_id PJD.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJD.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PMB-G-15 — someone who left the workspace is returned
- **Rules:** `get_by_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. A = member, `assigned_at T10`, but `user_id U2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### PMB-G-16 — there is no cap: 101 members give 101 rows
- **Rules:** `get_by_project` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 profiles P1 … P101, each from `make_profile(db)`.
2. 101 members E1 … E101, built with `add_all`: Ek = member, `assigned_at` = `T10 + timedelta(minutes=k)`, but `user_id Pk.id`. `in_order` = the ids of E1, E2, … E101, in that order.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### PMB-G-17 — writes nothing: an earlier pending row stays pending and alone in the session
- **Rules:** `get_by_project` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.
2. `P = ProjectMember(workspace_id=W1.id, project_id=PJ1.id, user_id=U2.id, assigned_at=T9)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

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
10. statement: `"projects" not in sql`.
11. statement: `"workspace_members" not in sql`.
12. nothing written: nothing written.
13. unchanged: unchanged(A).

### PMB-G-18 — a W2 member on a W1 project is not returned for W1
- **Rules:** `get_by_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### PMB-G-19 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_project` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.
2. B = member, `assigned_at T11`, but `project_id PJ2.id`.
3. `B.assigned_by = U2.id` (not flushed).

**When**
- `result = dao.get_by_project(db, project_id=PJ1.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.assigned_by == U2.id`.


## `ProjectMemberDAO.get_by_project_and_user`

### PMB-GU-01 — returns the row of that user, not the project's first row
- **Rules:** `get_by_project_and_user` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.
2. B = member, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.
2. returns: `isinstance(result, ProjectMember)`.

### PMB-GU-02 — returns the row on that project, not the user's first row
- **Rules:** `get_by_project_and_user` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.
2. B = member, `assigned_at T10`, but `project_id PJ2.id`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ2.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == B.id`.

### PMB-GU-03 — a person who is not a member returns None and nothing is created
- **Rules:** `get_by_project_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`, but `project_id PJ2.id`.
2. B = member, `assigned_at T11`, but `user_id U2.id`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.

### PMB-GU-04 — an unknown project returns None
- **Rules:** `get_by_project_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=MISSING, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PMB-GU-05 — an unknown user returns None
- **Rules:** `get_by_project_and_user` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PMB-GU-06 — another workspace returns None
- **Rules:** `get_by_project_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=U1.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### PMB-GU-07 — the row on a soft-deleted project is returned
- **Rules:** `get_by_project_and_user` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. Project PJD has `is_deleted True`, `deleted_at T12`, `deleted_by U1.id`: it is a standing row.
2. A = member, `assigned_at T10`, but `project_id PJD.id`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJD.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PMB-GU-08 — the row of someone who left the workspace is returned
- **Rules:** `get_by_project_and_user` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. left U2.
2. A = member, `assigned_at T10`, but `user_id U2.id`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### PMB-GU-09 — writes nothing: a read that finds its row leaves the session as it was
- **Rules:** `get_by_project_and_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.
2. `P = ProjectMember(workspace_id=W1.id, project_id=PJ1.id, user_id=U2.id, assigned_at=T9)`
3. `db.add(P)` (not flushed).
4. A recorder for the SQL statements the session sends during the When.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. pending: `not db.dirty`.
6. pending: `not db.deleted`.
7. statement: `written == []`.
8. statement: `len(selects) == 1`.
9. statement: `"FOR UPDATE" not in sql.upper()`.
10. statement: `"projects" not in sql`.
11. statement: `"workspace_members" not in sql`.
12. nothing written: nothing written.
13. unchanged: unchanged(A).

### PMB-GU-10 — a W2 row of that project and user is not returned for W1
- **Rules:** `get_by_project_and_user` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`, but `workspace_id W2.id`.

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### PMB-GU-11 — writes nothing: an unflushed edit of another row stays unflushed and is not reloaded
- **Rules:** `get_by_project_and_user` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = member, `assigned_at T10`.
2. B = member, `assigned_at T11`, but `user_id U2.id`.
3. `B.assigned_by = U2.id` (not flushed).

**When**
- `result = dao.get_by_project_and_user(db, project_id=PJ1.id, user_id=U1.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `B in db.dirty`.
3. pending: `len(db.dirty) == 1`.
4. pending: `B.assigned_by == U2.id`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `get_by_project` R5, `get_by_project_and_user` R4 — BUG-1278: `require_project_access` lets a soft-deleted project through | `ProjectManager` (spec FU-1) | The manager's spec carries the rule and the tag. |
| `get_by_project` R6, `get_by_project_and_user` R4 — BUG-1280: removal from the workspace deletes the person's rows, one `member_removed` event per project | `WorkspaceManager.remove_member_from_workspace` (spec FU-2) | The manager's spec carries the rule and the tag. When its new read is added to this DAO, this file gets cards for it. |
| Overview — `add_member` builds the row, `remove_member` deletes it | `ProjectManager` | Inherited writers have no caller here. |
| Module singleton | none (no logic) | Only used as the entry point of every card. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Model facts, Notes | The spec gives class names, not modules. No test imports `ProjectMember` yet: `app.models.project_member` follows the pattern of its neighbours. | Conventions use the path. A wrong one fails at import, in every test. |
| 2 | `get_by_project` R6, `get_by_project_and_user` R4 | The membership row's class and columns are not in this spec. `WorkspaceMember`, `role`, `status` come from `work_order_approver.cases.md`. | The `left` line of Conventions uses them. |
| 3 | Model facts | `uq_project_member_project_user` is not a rule, though Review's HR-6 line rests on it. | No card. It is the schema's, and no Errors row names it. |
| 4 | Review, BUG-1280 | Q1 was decided under delegation, and the rule sits in another spec. Not a money, stock or order item. | Deferred. R6 and R4 stay raw. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `get_by_project` | Returns | PMB-G-01 |
| `get_by_project` | R1 | PMB-G-01, PMB-G-02, PMB-G-03, PMB-G-04, PMB-G-18 |
| `get_by_project` | R2 | PMB-G-05, PMB-G-06, PMB-G-07 |
| `get_by_project` | R3 | PMB-G-08, PMB-G-09, PMB-G-10 |
| `get_by_project` | R4 | PMB-G-10 |
| `get_by_project` | R4 [BUG-1274] | PMB-G-11, PMB-G-12, PMB-G-13 |
| `get_by_project` | R5 | PMB-G-14 |
| `get_by_project` | R6 | PMB-G-15 |
| `get_by_project` | R7 | PMB-G-16 |
| `get_by_project` | Side effects | PMB-G-17, PMB-G-19 |
| `get_by_project_and_user` | Returns | PMB-GU-01 |
| `get_by_project_and_user` | R1 | PMB-GU-01, PMB-GU-02 |
| `get_by_project_and_user` | R2 | PMB-GU-03, PMB-GU-04, PMB-GU-05 |
| `get_by_project_and_user` | R3 | PMB-GU-06, PMB-GU-10 |
| `get_by_project_and_user` | R4 | PMB-GU-07, PMB-GU-08 |
| `get_by_project_and_user` | Side effects | PMB-GU-09, PMB-GU-11 |
