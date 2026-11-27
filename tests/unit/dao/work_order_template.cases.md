# Test cases — `app/dao/work_order_template.py`

> **Spec:** `tests/unit/dao/work_order_template.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-06; fill-gaps 2026-11-07, nothing open). No owner question touches this module, so there is no pending section.
> **Revision:** 2 (2026-11-07) — spec fill-gaps G1–G4. G1: Conventions import the line and approver models from `app.models.work_order_template_item` / `app.models.work_order_template_approver`. G2: the base `create` signature is now stated; M-02, M-03 keep their direct `db.add`, which the spec says proves the rule the same way. G3: keyword-only calls stay a note, no card. G4: new WOTP-RD-19 (`factory_id=0` is a filter, R5b); RD-11 now also cites R5b. No card retired.
> **Revision:** 3 (2026-11-09) — wording only, `work_order_template.verify.md` finding 1: WOTP-M-02's "Fails today on" text now says the Dhaka value is later than `after`. No Given, When or Then changed.
> **Counts:** 96 cases · 85 expected-to-pass · 11 expected-to-fail (bugs) · 8 deferred

## Reviewer summary
- **Per callable:** `WorkOrderTemplateDAO.get_by_workspace` 32 (4 bug) · `list_recurring_due` 19 (2 bug) · `WorkOrderTemplateDAO.get_by_id_and_workspace` 8 · `WorkOrderTemplateItemDAO.get_by_template` 11 · `WorkOrderTemplateItemDAO.get_by_id_and_workspace` 7 · `WorkOrderTemplateApproverDAO.get_by_template` 11 (3 bug) · `delete_all_for_template` 5 · Model facts M1 3 (2 bug).
- **Depth:** lighter target (skill step 1a). Six plain filtered reads and one bulk delete of default-approver rows; nothing here writes stock, money or order state. Scheduling (`list_recurring_due`) still gets every date boundary on both sides, because the manager's recurring run rests on it.
- **Expected-to-fail:** BUG-2330 4 (GW-15, GW-16, GW-17 non-strict, GW-18 strict SQL recorder) · BUG-2331 3 (AG-08, AG-09 non-strict, AG-10 strict recorder) · BUG-2332 2 (RD-13, RD-14, strict: the deleted section's row is returned today, a fixed fact, not row order) · BUG-2333 2 (M-02, M-03, strict, under `Asia/Dhaka`).
- **Notable design choices:**
  - Workspace filters: W0 (built before W1) and W2 (after) both hold rows in every isolation card, so `<=` / `>=` cannot pass. Filtered type, section, factory and template ids sit between a lower and a higher id of the same table.
  - `list_recurring_due` has no order by rule, so all its cards compare sets.
  - AG-08 gives approver rows explicit ids out of insertion order (spec Notes); these are the only explicit ids in the file.
  - `delete_all_for_template` DA-01 counts in the database right after the call with no flush, which is the "executed immediately" part of R1.
  - No `Author:` lines: a Claude executor writes the whole file. Race simulations: none.
- **Needs a decision:** None. Gaps 1–4 of revision 1 are closed by the spec's Gap log (2026-11-07).

## Conventions for this module

**IDs.** `WOTP` = `app/dao/work_order_template.py`. `GW` `WorkOrderTemplateDAO.get_by_workspace` · `RD` `list_recurring_due` · `GI` `WorkOrderTemplateDAO.get_by_id_and_workspace` · `IT` `WorkOrderTemplateItemDAO.get_by_template` · `II` `WorkOrderTemplateItemDAO.get_by_id_and_workspace` · `AG` `WorkOrderTemplateApproverDAO.get_by_template` · `DA` `delete_all_for_template` · `M` model facts M1.

**Actors and fixed values.**
- `dao` = `work_order_template_dao`, `idao` = `work_order_template_item_dao`, `adao` = `work_order_template_approver_dao` (all from `app.dao.work_order_template`). `db` = the test's real session, first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- `WorkOrderTemplate` = `app.models.work_order_template.WorkOrderTemplate`; `WorkOrderTemplateItem` = `app.models.work_order_template_item.WorkOrderTemplateItem`, `WorkOrderTemplateApprover` = `app.models.work_order_template_approver.WorkOrderTemplateApprover` (spec M2, M3). `WorkOrderType`, `Item`, `Factory`, `FactorySection` = `app.models.<snake_case>`. `Decimal`, `date`, `datetime`, `timedelta`, `text`, `select`, `func`, `patch` = the usual ones. `utcnow` = `app.utils.time.utcnow`.
- MISSING = `999999999`. T0 = `datetime(2026, 1, 1, 9, 0, 0)`. T9, T10, T11, T12 = `datetime(2026, 3, 4, 9, 0, 0)` … `datetime(2026, 3, 4, 12, 0, 0)`. DT = `date(2026, 3, 10)` (the target date). DAY = `timedelta(days=1)`.

**Externals.** None. Nothing is mocked.

**Standing rows** (every test, this order, no Given line; each flushed):
1. W0, W1, W2 = `make_workspace(db)` three times. So `W0.id < W1.id < W2.id`.
2. U1, U2, U3 = `make_profile(db)` three times.
3. Types: TY0 = `WorkOrderType(workspace_id=W0.id, name="Oil")`, TA = `(W1, "Oil")`, TB = `(W1, "Belt")`, TC = `(W1, "Filter")`, TY2 = `(W2, "Oil")`.
4. IT1 = `Item(workspace_id=W1.id, name="Oil filter", name_normalized="oil filter", unit="pcs")`.
5. Factories of W1: F1 = `Factory(workspace_id=W1.id, name="Main Plant", abbreviation="MP")`, F2 = `("North Yard", "NY")`, F3 = `("East Yard", "EY")`.
6. Sections of W1, `FactorySection(workspace_id=W1.id, factory_id=…, name=…, created_by=U1.id)`: S1 on F1 `"Line A"`, S2 on F2 `"Line B"`, S3 on F3 `"Line C"`, then SD on F2 `"Old line"` with `is_deleted=True, deleted_at=T0, deleted_by=U1.id` (deleted; `is_active` stays true).

**Given rows.** Inserted directly (never through the DAOs), flushed one at a time in the order written. After "but" a line lists every column that differs. A line written as code is a step to run exactly.
- **template** = `WorkOrderTemplate(workspace_id=W1.id, template_name="Oil change", work_order_type_id=TA.id)`; the card always gives `created_at`. A template "of W0" also has `work_order_type_id TY0.id`; "of W2" has `TY2.id`.
- **recurring** = template, `created_at T10`, but `is_recurring True`, `next_generation_date DT`, and the columns the card lists.
- **line on T** = `WorkOrderTemplateItem(workspace_id=W1.id, work_order_template_id=T.id, item_id=IT1.id, quantity=Decimal("1"))`.
- **approver of T for U** = `WorkOrderTemplateApprover(workspace_id=W1.id, work_order_template_id=T.id, user_id=U.id)`.

**Named checks.**
- **ids(result)** = `[r.id for r in result]`, order part of the check. **idset(result)** = `{r.id for r in result}`.
- **re-read X** = `db.expire_all()`, then SELECT X by id. **unchanged(X)** = after re-read every column of X equals its value before the call.
- **nothing written** = the numbers of `work_order_templates`, `work_order_template_items`, `work_order_template_approvers` rows (all workspaces) equal their values before the call.
- **approvers(T)** = `db.scalar(select(func.count()).select_from(WorkOrderTemplateApprover).where(WorkOrderTemplateApprover.work_order_template_id == T.id))`.
- `pending:` lines check the pending object P after the call. `session:` lines check the session directly after the call, before anything expires it.
- `raises: DataError` = `with pytest.raises(DataError) as exc:` then `with db.begin_nested():` then the When; later `raises:` lines assert on `exc.value`.
- **Statement recorder** = the SQL the session sends during the When is recorded. `sql` = the one `SELECT` sent; `order_part` = text of `sql` after its first `ORDER BY`, before any `LIMIT` (`""` if none); `written` = every recorded `INSERT`, `UPDATE`, `DELETE`.
- **commit spy** = `sp = db.begin_nested()` directly before the call, `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; after it `sp.rollback()`, then the later lines.
- **Dhaka** = `db.execute(text("SET LOCAL TimeZone = 'Asia/Dhaka'"))` as the first Given step.

**xfail cards.** `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`; `(non-strict)` = `strict=False`. Write the call and the checks exactly as shown; never weaken a non-strict assertion.

**Race simulations.** None.

## `WorkOrderTemplateDAO.get_by_workspace`

### WOTP-GW-01 — with the defaults: the workspace's rows, active and inactive, newest first
- **Rules:** `get_by_workspace` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [B.id, A.id]`.
3. returns: `isinstance(result[0], WorkOrderTemplate)`.

### WOTP-GW-02 — newer rows of an earlier and a later workspace are not returned
- **Rules:** `get_by_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = template, `created_at T12`, but `workspace_id W0.id`, `work_order_type_id TY0.id`.
2. A = template, `created_at T10`.
3. Z2 = template, `created_at T12`, but `workspace_id W2.id`, `work_order_type_id TY2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTP-GW-03 — an unknown workspace returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=MISSING)`.

**Then**
1. returns: `result == []`.

### WOTP-GW-04 — a workspace with no templates returns an empty list
- **Rules:** `get_by_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### WOTP-GW-05 — is_active=None returns active and inactive rows
- **Rules:** `get_by_workspace` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=None)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### WOTP-GW-06 — is_active=True returns the active rows only
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=True)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTP-GW-07 — is_active=False returns the inactive rows only
- **Rules:** `get_by_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `is_active False`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=False)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WOTP-GW-08 — a type keeps its own rows, not those of a lower or a higher type id
- **Rules:** `get_by_workspace` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `work_order_type_id TB.id`.
3. C = template, `created_at T12`, but `template_name "Filter swap"`, `work_order_type_id TC.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=TB.id)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WOTP-GW-09 — a type of another workspace returns an empty list
- **Rules:** `get_by_workspace` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. Z2 = template, `created_at T11`, but `workspace_id W2.id`, `work_order_type_id TY2.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=TY2.id)`.

**Then**
1. returns: `result == []`.

### WOTP-GW-10 — work_order_type_id=None applies no filter
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `work_order_type_id TB.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=None)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### WOTP-GW-11 — work_order_type_id=0 applies no filter
- **Rules:** `get_by_workspace` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `work_order_type_id TB.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=0)`.

**Then**
1. returns: `ids(result) == [B.id, A.id]`.

### WOTP-GW-12 — rows come newest first, whatever their ids and names
- **Rules:** `get_by_workspace` R5
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

### WOTP-GW-13 — the order is applied before the page is cut
- **Rules:** `get_by_workspace` R5
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

### WOTP-GW-14 — on a tie both rows are returned, between the newer and the older
- **Rules:** `get_by_workspace` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T11`, but `template_name "Belt check"`.
3. C = template, `created_at T12`, but `template_name "Filter swap"`.
4. D = template, `created_at T10`, but `template_name "Misc"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 4`.
2. returns: `result[0].id == C.id`.
3. returns: `{r.id for r in result[1:3]} == {A.id, B.id}`.
4. returns: `result[3].id == D.id`.

### WOTP-GW-15 — on a tie the highest id comes first, when the lowest id was updated
- **Rules:** `get_by_workspace` R5 [BUG-2330]
- **Kind:** bug
- **Expect:** xfail BUG-2330 (non-strict)
- **Fails today on:** Then 2 (no order is requested among tied rows; physical row order decides)

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T11`, but `template_name "Belt check"`.
3. C = template, `created_at T11`, but `template_name "Filter swap"`.
4. `A.template_name = "Oil change two"`, then `db.flush()`.
5. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### WOTP-GW-16 — on a tie the id decides, when name, flag, type and cost would each sort otherwise
- **Rules:** `get_by_workspace` R5 [BUG-2330]
- **Kind:** bug
- **Expect:** xfail BUG-2330 (non-strict)
- **Fails today on:** Then 2 (no order is requested among tied rows; physical row order decides)

**Given**
1. A = template, `created_at T11`, but `template_name "Mid"`, `work_order_type_id TB.id`, `cost Decimal("5.00")`.
2. B = template, `created_at T11`, but `template_name "Zed"`, `is_active False`, `work_order_type_id TC.id`, `cost Decimal("9.00")`.
3. C = template, `created_at T11`, but `template_name "Abe"`, `cost Decimal("1.00")`.
4. `db.expire_all()`

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [C.id, B.id, A.id]`.

### WOTP-GW-17 — tied rows paged one at a time neither repeat nor miss a row
- **Rules:** `get_by_workspace` R5 [BUG-2330]
- **Kind:** bug
- **Expect:** xfail BUG-2330 (non-strict)
- **Fails today on:** Then 2 (no order among tied rows; a row can repeat and another be missed)

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T11`, but `template_name "Belt check"`.
3. C = template, `created_at T11`, but `template_name "Filter swap"`.
4. D = template, `created_at T11`, but `template_name "Misc"`.
5. E = template, `created_at T11`, but `template_name "Grease"`.
6. `A.template_name = "Oil change two"`, then `db.flush()`.
7. `db.expire_all()`

**When**
- `pages = [dao.get_by_workspace(db, workspace_id=W1.id, skip=k, limit=1) for k in range(5)]` (one list comprehension).

**Then**
1. returns: `[len(p) for p in pages] == [1, 1, 1, 1, 1]`.
2. returns: `[p[0].id for p in pages] == [E.id, D.id, C.id, B.id, A.id]`.

### WOTP-GW-18 — the query orders by created_at, then id, both descending
- **Rules:** `get_by_workspace` R5 [BUG-2330]
- **Kind:** bug
- **Expect:** xfail BUG-2330
- **Fails today on:** Then 4 (the query orders by `created_at` alone)

**Given**
1. A = template, `created_at T10`.
2. Statement recorder.

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

### WOTP-GW-19 — filters combine with AND
- **Rules:** `get_by_workspace` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `work_order_type_id TB.id`.
2. B = template, `created_at T11`, but `template_name "Belt check"`, `work_order_type_id TB.id`, `is_active False`.
3. C = template, `created_at T12`, but `template_name "Filter swap"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=True, work_order_type_id=TB.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTP-GW-20 — is_active is applied before the page: a hidden row takes no place in it
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = template, `created_at T12`, but `template_name "Off"`, `is_active False`.
2. A = template, `created_at T11`.
3. B = template, `created_at T10`, but `template_name "Belt check"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, is_active=True, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WOTP-GW-21 — the type is applied before the page: a hidden row takes no place in it
- **Rules:** `get_by_workspace` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. X = template, `created_at T12`, but `template_name "Off"`, `work_order_type_id TC.id`.
2. A = template, `created_at T11`, but `work_order_type_id TB.id`.
3. B = template, `created_at T10`, but `template_name "Belt check"`, `work_order_type_id TB.id`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, work_order_type_id=TB.id, skip=1, limit=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WOTP-GW-22 — skip and limit cut a window
- **Rules:** `get_by_workspace` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = template, `created_at T12`.
2. B = template, `created_at T11`, but `template_name "Belt check"`.
3. C = template, `created_at T10`, but `template_name "Filter swap"`.
4. D = template, `created_at T9`, but `template_name "Misc"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1, limit=2)`.

**Then**
1. returns: `ids(result) == [B.id, C.id]`.

### WOTP-GW-23 — with the defaults 101 rows give the newest 100
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all` then one flush: Ek = template, `created_at` = `T10 + timedelta(minutes=k)`, but `template_name` = `f"Oil {k}"`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `ids(result) == newest[:100]`.

### WOTP-GW-24 — limit=1000 gives all 101
- **Rules:** `get_by_workspace` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all` then one flush: Ek = template, `created_at` = `T10 + timedelta(minutes=k)`, but `template_name` = `f"Oil {k}"`.
2. `newest` = the ids of E101, E100, … E1, in that order.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == newest`.

### WOTP-GW-25 — limit=0 returns an empty list
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Belt check"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=0)`.

**Then**
1. returns: `result == []`.

### WOTP-GW-26 — limit=1 returns one row
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Belt check"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, limit=1)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTP-GW-27 — skip past the end returns an empty list
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Belt check"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=2)`.

**Then**
1. returns: `result == []`.

### WOTP-GW-28 — skip at the last row returns it
- **Rules:** `get_by_workspace` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.
2. B = template, `created_at T10`, but `template_name "Belt check"`.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id, skip=1)`.

**Then**
1. returns: `ids(result) == [B.id]`.

### WOTP-GW-29 — a negative limit raises
- **Rules:** `get_by_workspace` R8, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, limit=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201W"`.
3. raises: `"LIMIT must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### WOTP-GW-30 — a negative skip raises
- **Rules:** `get_by_workspace` R8, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. A = template, `created_at T11`.

**When**
- `dao.get_by_workspace(db, workspace_id=W1.id, skip=-1)`, inside the wrap of `raises: DataError`.

**Then**
1. raises: `DataError`.
2. raises: `exc.value.orig.pgcode == "2201X"`.
3. raises: `"OFFSET must not be negative" in str(exc.value.orig)`.
4. nothing written: nothing written.

### WOTP-GW-31 — writes nothing: a newer pending row stays pending and is not returned
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. `P = WorkOrderTemplate(workspace_id=W1.id, template_name="Pending", work_order_type_id=TA.id, created_at=T12)`
3. `db.add(P)` (not flushed).
4. Statement recorder.

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. statement: `written == []`.
6. nothing written: nothing written.
7. unchanged: unchanged(A).

### WOTP-GW-32 — writes nothing: a read leaves the caller's unflushed edit alone
- **Rules:** `get_by_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T10`, but `workspace_id W2.id`, `work_order_type_id TY2.id`.
3. `B.template_name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_workspace(db, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## `WorkOrderTemplateDAO.list_recurring_due`

> No order is guaranteed (Returns): every card compares sets.

### WOTP-RD-01 — a recurring template due on the target date is returned
- **Rules:** `list_recurring_due` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = recurring.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id}`.
3. returns: `isinstance(result[0], WorkOrderTemplate)`.

### WOTP-RD-02 — due templates of an earlier and a later workspace are not returned
- **Rules:** `list_recurring_due` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = recurring, but `workspace_id W0.id`, `work_order_type_id TY0.id`.
2. A = recurring.
3. Z2 = recurring, but `workspace_id W2.id`, `work_order_type_id TY2.id`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-RD-03 — an inactive recurring template is not returned
- **Rules:** `list_recurring_due` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring.
2. X = recurring, but `template_name "Off"`, `is_active False`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-RD-04 — a non-recurring template with a due date is not returned
- **Rules:** `list_recurring_due` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring.
2. X = template, `created_at T10`, but `template_name "Once"`, `is_recurring False`, `next_generation_date DT`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-RD-05 — next date equal to the target is due; one day after is not
- **Rules:** `list_recurring_due` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring.
2. X = recurring, but `template_name "Tomorrow"`, `next_generation_date DT + DAY`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-RD-06 — next date one day before the target is due
- **Rules:** `list_recurring_due` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring, but `next_generation_date DT - DAY`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-RD-07 — no next date: never due, and the call does not fail
- **Rules:** `list_recurring_due` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring.
2. X = recurring, but `template_name "Unset"`, `next_generation_date None`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-RD-08 — an overdue template, a year late, is returned
- **Rules:** `list_recurring_due` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring, but `next_generation_date date(2025, 3, 10)`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-RD-09 — the end date: none, equal or later is running; one day before has ended
- **Rules:** `list_recurring_due` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring.
2. B = recurring, but `template_name "Ends today"`, `recurrence_end_date DT`.
3. C = recurring, but `template_name "Ends later"`, `recurrence_end_date DT + DAY`.
4. X = recurring, but `template_name "Ended"`, `recurrence_end_date DT - DAY`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id, B.id, C.id}`.

### WOTP-RD-10 — a section run keeps that section's templates, not a lower or higher section's, nor sectionless ones
- **Rules:** `list_recurring_due` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = recurring, but `default_factory_section_id S1.id`.
2. B = recurring, but `template_name "Line B oil"`, `default_factory_section_id S2.id`.
3. C = recurring, but `template_name "Line C oil"`, `default_factory_section_id S3.id`.
4. N = recurring, but `template_name "Anywhere"`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_section_id=S2.id)`.

**Then**
1. returns: `idset(result) == {B.id}`.

### WOTP-RD-11 — factory_section_id=0 is a filter, and matches nothing
- **Rules:** `list_recurring_due` R4, R5b (Inputs: `0` included)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring, but `default_factory_section_id S1.id`.
2. N = recurring, but `template_name "Anywhere"`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_section_id=0)`.

**Then**
1. returns: `result == []`.

### WOTP-RD-12 — a factory run keeps its sections' templates and the sectionless ones, not a lower or higher factory's
- **Rules:** `list_recurring_due` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = recurring, but `default_factory_section_id S1.id`.
2. B = recurring, but `template_name "Line B oil"`, `default_factory_section_id S2.id`.
3. C = recurring, but `template_name "Line C oil"`, `default_factory_section_id S3.id`.
4. N = recurring, but `template_name "Anywhere"`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_id=F2.id)`.

**Then**
1. returns: `idset(result) == {B.id, N.id}`.

### WOTP-RD-13 — a factory run skips a template whose default section is deleted
- **Rules:** `list_recurring_due` R5a [BUG-2332]
- **Kind:** bug
- **Expect:** xfail BUG-2332
- **Fails today on:** Then 1 (the deleted section SD still belongs to F2, so D is returned)

**Given**
1. B = recurring, but `template_name "Line B oil"`, `default_factory_section_id S2.id`.
2. D = recurring, but `template_name "Old line oil"`, `default_factory_section_id SD.id`.
3. N = recurring, but `template_name "Anywhere"`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_id=F2.id)`.

**Then**
1. returns: `idset(result) == {B.id, N.id}`.

### WOTP-RD-14 — a section run naming a deleted section returns nothing
- **Rules:** `list_recurring_due` R5a [BUG-2332]
- **Kind:** bug
- **Expect:** xfail BUG-2332
- **Fails today on:** Then 1 (the section id still filters, so D is returned)

**Given**
1. D = recurring, but `template_name "Old line oil"`, `default_factory_section_id SD.id`.
2. N = recurring, but `template_name "Anywhere"`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_section_id=SD.id)`.

**Then**
1. returns: `result == []`.

### WOTP-RD-15 — both scopes apply: a section of another factory gives nothing
- **Rules:** `list_recurring_due` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring, but `default_factory_section_id S1.id`.
2. N = recurring, but `template_name "Anywhere"`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_section_id=S1.id, factory_id=F2.id)`.

**Then**
1. returns: `result == []`.

### WOTP-RD-16 — both scopes apply: section and its own factory give that section's templates
- **Rules:** `list_recurring_due` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. A = recurring, but `default_factory_section_id S1.id`.
2. B = recurring, but `template_name "Line B oil"`, `default_factory_section_id S2.id`.
3. N = recurring, but `template_name "Anywhere"`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_section_id=S2.id, factory_id=F2.id)`.

**Then**
1. returns: `idset(result) == {B.id}`.

### WOTP-RD-17 — no cap: 101 due templates among not-due ones all come back
- **Rules:** `list_recurring_due` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 5 templates X1 … X5, built with `add_all`: Xk = recurring, but `template_name` = `f"Later {k}"`, `next_generation_date DT + DAY`.
2. 101 templates E1 … E101, built with `add_all` then one flush: Ek = recurring, but `template_name` = `f"Due {k}"`.
3. `due` = the set of the ids of E1 … E101.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `idset(result) == due`.

### WOTP-RD-18 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** `list_recurring_due` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = recurring.
2. B = recurring, but `workspace_id W2.id`, `work_order_type_id TY2.id`.
3. `B.template_name = "Edited"` (not flushed).
4. `P = WorkOrderTemplate(workspace_id=W1.id, template_name="Pending", work_order_type_id=TA.id, created_at=T12, is_recurring=True, next_generation_date=DT)`
5. `db.add(P)` (not flushed).
6. Statement recorder.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

### WOTP-RD-19 — factory_id=0 is a filter: only the sectionless due template comes back
- **Rules:** `list_recurring_due` R5b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = recurring, but `default_factory_section_id S1.id`.
2. N = recurring, but `template_name "Anywhere"`.
3. B = recurring, but `template_name "Belt"`, `default_factory_section_id S2.id`.

**When**
- `result = dao.list_recurring_due(db, workspace_id=W1.id, target_date=DT, factory_id=0)`.

**Then**
1. returns: `idset(result) == {N.id}`.

## `WorkOrderTemplateDAO.get_by_id_and_workspace`

### WOTP-GI-01 — returns the row with that id
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. B = template, `created_at T10`, but `template_name "Belt check"`.
2. A = template, `created_at T11`.
3. C = template, `created_at T12`, but `template_name "Filter swap"`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderTemplate)`.
2. returns: `result.id == A.id`.
3. returns: `result.template_name == "Oil change"`, `result.workspace_id == W1.id`, `result.created_at == T11`.

### WOTP-GI-02 — a later workspace's id returns None
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. Z = template, `created_at T11`, but `workspace_id W2.id`, `work_order_type_id TY2.id`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WOTP-GI-03 — an earlier workspace's id, built first, returns None
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, `created_at T10`, but `workspace_id W0.id`, `work_order_type_id TY0.id`.
2. A = template, `created_at T11`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WOTP-GI-04 — the id asked under another workspace returns None
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### WOTP-GI-05 — an unknown id returns None
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WOTP-GI-06 — an inactive template is returned
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. A = template, `created_at T10`, but `is_active False`.

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. returns: `result.is_active is False`.

### WOTP-GI-07 — writes nothing: a miss leaves a pending row pending
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. `P = WorkOrderTemplate(workspace_id=W1.id, template_name="Pending", work_order_type_id=TA.id, created_at=T12)`
3. `db.add(P)` (not flushed).
4. Statement recorder.

**When**
- `result = dao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. pending: `P in db.new`.
3. pending: `P.id is None`.
4. pending: `len(db.new) == 1`.
5. statement: `written == []`.

### WOTP-GI-08 — writes nothing: a hit leaves the caller's unflushed edit alone
- **Rules:** `WorkOrderTemplateDAO.get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = template, `created_at T10`.
2. B = template, `created_at T11`, but `template_name "Belt check"`.
3. `B.template_name = "Edited"` (not flushed).

**When**
- `result = dao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.

## `WorkOrderTemplateItemDAO.get_by_template`

### WOTP-IT-01 — returns the template's lines in the order they were added, whatever their quantities
- **Rules:** item `get_by_template` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, but `quantity Decimal("3.00")`, `action_type "REPLACE"`.
3. B = line on T, but `quantity Decimal("1.00")`, `action_type "BORROW"`.
4. C = line on T, but `quantity Decimal("2.00")`, `action_type "CONSUME"`.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.
3. returns: `isinstance(result[0], WorkOrderTemplateItem)`.
4. returns: `result[0].quantity == Decimal("3.00")`.

### WOTP-IT-02 — lines of a lower and a higher template are not returned
- **Rules:** item `get_by_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = template, `created_at T9`, but `template_name "Belt check"`.
2. T = template, `created_at T10`.
3. R = template, `created_at T11`, but `template_name "Filter swap"`.
4. X = line on S.
5. A = line on T.
6. Y = line on R.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTP-IT-03 — a template with no lines returns an empty list
- **Rules:** item `get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = template, `created_at T9`, but `template_name "Belt check"`.
2. T = template, `created_at T10`.
3. X = line on S.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOTP-IT-04 — no cap: 101 lines give 101 rows, in id order
- **Rules:** item `get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. 101 lines E1 … E101, built with `add_all` then one flush: Ek = line on T, but `quantity` = `Decimal(102 - k)`.
3. `in_order` = the ids of E1 … E101, sorted ascending.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 101`.
2. returns: `ids(result) == in_order`.

### WOTP-IT-05 — the id order holds after the lowest line was updated
- **Rules:** item `get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T.
3. B = line on T.
4. C = line on T.
5. `A.notes = "Updated"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id, C.id]`.

### WOTP-IT-06 — lines of an earlier and a later workspace on the same template are not returned
- **Rules:** item `get_by_template` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. X = line on T, but `workspace_id W0.id`.
3. A = line on T.
4. Y = line on T, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTP-IT-07 — a call with another workspace returns an empty list
- **Rules:** item `get_by_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W2.id)`.

**Then**
1. returns: `result == []`.

### WOTP-IT-08 — a line of W2 on a template of W1 is returned for W2
- **Rules:** item `get_by_template` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W2.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.

### WOTP-IT-09 — the lines of an inactive template are returned
- **Rules:** item `get_by_template` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, `created_at T10`, but `is_active False`.
2. A = line on T.
3. B = line on T.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id, B.id]`.

### WOTP-IT-10 — writes nothing: a pending line stays pending, an unflushed edit stays dirty
- **Rules:** item `get_by_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. S = template, `created_at T9`, but `template_name "Belt check"`.
3. A = line on T.
4. B = line on S.
5. `B.notes = "Edited"` (not flushed).
6. `P = WorkOrderTemplateItem(workspace_id=W1.id, work_order_template_id=T.id, item_id=IT1.id, quantity=Decimal("1"))`
7. `db.add(P)` (not flushed).
8. Statement recorder.

**When**
- `result = idao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

### WOTP-IT-11 — an unknown template returns an empty list
- **Rules:** item `get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T.

**When**
- `result = idao.get_by_template(db, work_order_template_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

## `WorkOrderTemplateItemDAO.get_by_id_and_workspace`

### WOTP-II-01 — returns the line with that id
- **Rules:** item `get_by_id_and_workspace` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. B = line on T.
3. A = line on T, but `quantity Decimal("2.50")`, `action_type "INSTALL"`.
4. C = line on T.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderTemplateItem)`.
2. returns: `result.id == A.id`.
3. returns: `result.work_order_template_id == T.id`, `result.quantity == Decimal("2.50")`, `result.action_type == "INSTALL"`.

### WOTP-II-02 — a later workspace's line id returns None
- **Rules:** item `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T.
3. Z = line on T, but `workspace_id W2.id`.

**When**
- `result = idao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WOTP-II-03 — an earlier workspace's line id, built first, returns None
- **Rules:** item `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. Z = line on T, but `workspace_id W0.id`.
3. A = line on T.

**When**
- `result = idao.get_by_id_and_workspace(db, id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WOTP-II-04 — the id asked under another workspace returns None
- **Rules:** item `get_by_id_and_workspace` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W2.id)`.

**Then**
1. returns: `result is None`.

### WOTP-II-05 — an unknown id returns None
- **Rules:** item `get_by_id_and_workspace` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T.

**When**
- `result = idao.get_by_id_and_workspace(db, id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.

### WOTP-II-06 — a line of an inactive template is returned
- **Rules:** item `get_by_id_and_workspace` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, `created_at T10`, but `is_active False`.
2. A = line on T.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.

### WOTP-II-07 — writes nothing: a pending line stays pending, an unflushed edit stays dirty
- **Rules:** item `get_by_id_and_workspace` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = line on T.
3. B = line on T.
4. `B.notes = "Edited"` (not flushed).
5. `P = WorkOrderTemplateItem(workspace_id=W1.id, work_order_template_id=T.id, item_id=IT1.id, quantity=Decimal("1"))`
6. `db.add(P)` (not flushed).
7. Statement recorder.

**When**
- `result = idao.get_by_id_and_workspace(db, id=A.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == A.id`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `WorkOrderTemplateApproverDAO.get_by_template`

### WOTP-AG-01 — returns the template's approvers
- **Rules:** approver `get_by_template` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U1.
3. B = approver of T for U2.

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {A.id, B.id}`.
3. returns: `len(result) == 2`.
4. returns: `isinstance(result[0], WorkOrderTemplateApprover)`.

### WOTP-AG-02 — approvers of a lower and a higher template are not returned
- **Rules:** approver `get_by_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = template, `created_at T9`, but `template_name "Belt check"`.
2. T = template, `created_at T10`.
3. R = template, `created_at T11`, but `template_name "Filter swap"`.
4. X = approver of S for U1.
5. A = approver of T for U1.
6. Y = approver of R for U1.

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. returns: `len(result) == 1`.

### WOTP-AG-03 — an unknown template returns an empty list
- **Rules:** approver `get_by_template` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U1.

**When**
- `result = adao.get_by_template(db, work_order_template_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WOTP-AG-04 — rows of an earlier and a later workspace on the same template are not returned
- **Rules:** approver `get_by_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. X = approver of T for U1, but `workspace_id W0.id`.
3. A = approver of T for U2.
4. Y = approver of T for U3, but `workspace_id W2.id`.

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. returns: `len(result) == 1`.

### WOTP-AG-05 — a W2 row on a template of W1 is returned for W2, and a call for W2 gets nothing else
- **Rules:** approver `get_by_template` R1 (row's own workspace, M4)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U1.
3. Z = approver of T for U2, but `workspace_id W2.id`.

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W2.id)`.

**Then**
1. returns: `idset(result) == {Z.id}`.
2. returns: `len(result) == 1`.

### WOTP-AG-06 — approvers of an inactive template are returned
- **Rules:** approver `get_by_template` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, `created_at T10`, but `is_active False`.
2. A = approver of T for U1.

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### WOTP-AG-07 — an approver who is no member of the workspace is returned
- **Rules:** approver `get_by_template` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U3 (U3 has no `workspace_members` row in W1).

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. returns: `result[0].user_id == U3.id`.

### WOTP-AG-08 — rows inserted out of id order come back by id, after the lowest was updated
- **Rules:** approver `get_by_template` R2 [BUG-2331]
- **Kind:** bug
- **Expect:** xfail BUG-2331 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical row order decides)

**Given**
1. T = template, `created_at T10`.
2. B = approver of T for U1, but `id 1900000002`.
3. A = approver of T for U2, but `id 1900000001`.
4. C = approver of T for U3, but `id 1900000003`.
5. `A.approver_slot = "first"`, then `db.flush()`.
6. `db.expire_all()`

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [1900000001, 1900000002, 1900000003]`.

### WOTP-AG-09 — on rows built in id order, the order is by id, not by user
- **Rules:** approver `get_by_template` R2 [BUG-2331]
- **Kind:** bug
- **Expect:** xfail BUG-2331 (non-strict)
- **Fails today on:** Then 2 (no `ORDER BY`; physical order usually matches, which is why this card is non-strict)

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U3.
3. B = approver of T for U1.
4. C = approver of T for U2.
5. `db.expire_all()`

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 3`.
2. returns: `ids(result) == [A.id, B.id, C.id]`.

### WOTP-AG-10 — the query orders by id ascending
- **Rules:** approver `get_by_template` R2 [BUG-2331]
- **Kind:** bug
- **Expect:** xfail BUG-2331
- **Fails today on:** Then 2 (no `ORDER BY` is sent)

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U1.
3. Statement recorder.

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `ids(result) == [A.id]`.
2. statement: `"ORDER BY" in sql`.
3. statement: `".id" in order_part`.
4. statement: `"DESC" not in order_part.upper()`.
5. statement: `order_part.count(",") == 0`.

### WOTP-AG-11 — writes nothing: a pending row stays pending, an unflushed edit stays dirty
- **Rules:** approver `get_by_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. S = template, `created_at T9`, but `template_name "Belt check"`.
3. A = approver of T for U1.
4. B = approver of S for U1.
5. `B.approver_slot = "edited"` (not flushed).
6. `P = WorkOrderTemplateApprover(workspace_id=W1.id, work_order_template_id=T.id, user_id=U2.id)`
7. `db.add(P)` (not flushed).
8. Statement recorder.

**When**
- `result = adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. pending: `P in db.new`.
3. pending: `len(db.new) == 1`.
4. session: `B in db.dirty`.
5. session: `len(db.dirty) == 1`.
6. statement: `written == []`.

## `WorkOrderTemplateApproverDAO.delete_all_for_template`

### WOTP-DA-01 — every approver of the template is deleted at once, with no flush
- **Rules:** `delete_all_for_template` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U1.
3. B = approver of T for U2.

**When**
- `result = adao.delete_all_for_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. count: approvers(T) `== 0` (run directly after the call, no `db.flush()` first).
3. returns: `adao.get_by_template(db, work_order_template_id=T.id, workspace_id=W1.id) == []`.

### WOTP-DA-02 — approvers of a lower and a higher template are untouched
- **Rules:** `delete_all_for_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = template, `created_at T9`, but `template_name "Belt check"`.
2. T = template, `created_at T10`.
3. R = template, `created_at T11`, but `template_name "Filter swap"`.
4. X = approver of S for U1.
5. A = approver of T for U1.
6. Y = approver of R for U1.

**When**
- `result = adao.delete_all_for_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. count: approvers(T) `== 0`.
3. count: approvers(S) `== 1`.
4. count: approvers(R) `== 1`.
5. unchanged: unchanged(X).
6. unchanged: unchanged(Y).

### WOTP-DA-03 — rows of that template with an earlier or a later workspace are untouched
- **Rules:** `delete_all_for_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. X = approver of T for U1, but `workspace_id W0.id`.
3. A = approver of T for U2.
4. Y = approver of T for U3, but `workspace_id W2.id`.

**When**
- `result = adao.delete_all_for_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. count: approvers(T) `== 2`.
3. count: `work_order_template_approvers` with `id == A.id` has 0 rows.
4. unchanged: unchanged(X).
5. unchanged: unchanged(Y).

### WOTP-DA-04 — no matching rows: nothing happens, no error
- **Rules:** `delete_all_for_template` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = template, `created_at T9`, but `template_name "Belt check"`.
2. T = template, `created_at T10`.
3. X = approver of S for U1.

**When**
- `result = adao.delete_all_for_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. nothing written: nothing written.
3. unchanged: unchanged(X).

### WOTP-DA-05 — does not commit: a rolled-back savepoint brings the rows back
- **Rules:** `delete_all_for_template` Side effects (nothing committed)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, `created_at T10`.
2. A = approver of T for U1.
3. B = approver of T for U2.

**When**
- commit spy: `result = adao.delete_all_for_template(db, work_order_template_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is None`.
2. mock called: `cm.call_count == 0`.
3. count: approvers(T) `== 2` (after `sp.rollback()` and `db.expire_all()`).

## Model facts M1 (`created_at`, `updated_at`)

### WOTP-M-01 — a new template gets a creation time, and no update time
- **Rules:** M1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `A = WorkOrderTemplate(workspace_id=W1.id, template_name="Oil change", work_order_type_id=TA.id)` (no `created_at`).

**When**
- `db.add(A); db.flush(); db.refresh(A)` (one step).

**Then**
1. re-read A: `created_at is not None`.
2. re-read A: `updated_at is None`.

### WOTP-M-02 — a new template's creation time is naive UTC, whatever the database's time zone
- **Rules:** M1 [BUG-2333]
- **Kind:** bug
- **Expect:** xfail BUG-2333
- **Fails today on:** Then 2 (today `created_at` is the transaction start in `Asia/Dhaka`, six hours ahead, so later than `after`)

**Given**
1. Dhaka.
2. `A = WorkOrderTemplate(workspace_id=W1.id, template_name="Oil change", work_order_type_id=TA.id)` (no `created_at`).
3. `before = utcnow()`.

**When**
- `db.add(A); db.flush(); db.refresh(A); after = utcnow()` (one step).

**Then**
1. re-read A: `A.created_at.tzinfo is None`.
2. re-read A: `before <= A.created_at <= after`.

### WOTP-M-03 — an updated template's update time is naive UTC, whatever the database's time zone
- **Rules:** M1 [BUG-2333]
- **Kind:** bug
- **Expect:** xfail BUG-2333
- **Fails today on:** Then 2 (today `updated_at` is the database `now()` in `Asia/Dhaka`)

**Given**
1. Dhaka.
2. A = template, `created_at T10`.
3. `before = utcnow()`.

**When**
- `A.template_name = "Oil change two"; db.flush(); db.refresh(A); after = utcnow()` (one step).

**Then**
1. re-read A: `A.updated_at is not None`.
2. re-read A: `before <= A.updated_at <= after`.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| FU-1 — BUG-1015, BUG-1228, BUG-360…363, what a template puts into a work order | `WorkOrderTemplateManager` (`work_order_template_manager.spec.md`) | links across workspaces, money fields, generated orders |
| HR-10 locking (BUG-2343) | `WorkOrderTemplateManager` | the manager locks; the DAO does not |
| HR-15 — `cost`, `quantity` `Numeric(15, 2)` round half up | `WorkOrderTemplateManager` | the DAO computes nothing |
| HR-7 — `1 <= limit <= 1000`, `skip >= 0` | `GET /work-order-templates/` | endpoint rule; the DAO's own negatives are GW-29, GW-30 |
| FU-2 — a deleted section's machines | `tests/unit/utils/work_order_generation.spec.md` | `resolve_template_machine_ids` on a deleted section |
| `get_by_workspace` callers pass `is_active=True` / `limit=1000` | `WorkOrderTemplateManager.list_templates`, `generate_drafts` | the arguments sent |
| Inherited `BaseDAO` methods (`create`, `update`, `remove`, `get`, `get_multi`) | `tests/unit/dao/base.cases.md` | generic behaviour |
| Module singletons | none (no logic) | entry point of every card |

## Spec gaps
None open. Gaps 1–4 of revision 1 were closed by the spec's Gap log (2026-11-07):
- G1: model modules named in M2, M3 → Conventions.
- G2: the base `create(db, *, obj_in)` signature is stated; a direct `db.add` proves BUG-2333 the same way, so M-02, M-03 are unchanged.
- G3: keyword-only calls stay a note by design; no card.
- G4: `factory_id = 0` and `factory_section_id = 0` are filters (R5b) → WOTP-RD-19, RD-11.

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `WorkOrderTemplateDAO.get_by_workspace` | Returns | WOTP-GW-01 |
| | R1 | WOTP-GW-01 … GW-04 |
| | R2 | WOTP-GW-01, GW-05, GW-06, GW-07 |
| | R3 | WOTP-GW-08, GW-09 |
| | R4 | WOTP-GW-10, GW-11 |
| | R5 | WOTP-GW-12, GW-13, GW-14 |
| | R5 [BUG-2330] | WOTP-GW-15, GW-16, GW-17, GW-18 |
| | R6 | WOTP-GW-19, GW-20, GW-21 |
| | R7 | WOTP-GW-22, GW-23, GW-24 |
| | R8, Errors | WOTP-GW-25 … GW-30 |
| | Side effects | WOTP-GW-31, GW-32 |
| `list_recurring_due` | R1, Returns | WOTP-RD-01, RD-02, RD-03, RD-04 |
| | R2 | WOTP-RD-05, RD-06, RD-07, RD-08 |
| | R3 | WOTP-RD-09 |
| | R4 | WOTP-RD-10, RD-11 |
| | R5 | WOTP-RD-12 |
| | R5b | WOTP-RD-11, RD-19 |
| | R5a [BUG-2332] | WOTP-RD-13, RD-14 |
| | R6 | WOTP-RD-15, RD-16 |
| | R7 | WOTP-RD-17 |
| | Side effects | WOTP-RD-18 |
| `WorkOrderTemplateDAO.get_by_id_and_workspace` | R1, Returns | WOTP-GI-01 |
| | R2 | WOTP-GI-02 … GI-05, GI-07 |
| | R3 | WOTP-GI-06 |
| | Side effects | WOTP-GI-07, GI-08 |
| item `get_by_template` | R1, Returns | WOTP-IT-01 … IT-05, IT-11 |
| | R2 | WOTP-IT-06, IT-07 |
| | R3 | WOTP-IT-06, IT-08 |
| | R4 | WOTP-IT-09 |
| | Side effects | WOTP-IT-10 |
| item `get_by_id_and_workspace` | R1 | WOTP-II-01 … II-05 |
| | R2 | WOTP-II-06 |
| | Side effects | WOTP-II-07 |
| approver `get_by_template` | R1, Returns | WOTP-AG-01 … AG-05 |
| | R2 [BUG-2331] | WOTP-AG-08, AG-09, AG-10 |
| | R3 | WOTP-AG-06, AG-07 |
| | Side effects | WOTP-AG-11 |
| `delete_all_for_template` | R1, Returns | WOTP-DA-01 |
| | R2 | WOTP-DA-02, DA-03 |
| | R3 | WOTP-DA-04 |
| | Side effects (no commit) | WOTP-DA-05 |
| Model facts | M1 | WOTP-M-01 |
| | M1 [BUG-2333] | WOTP-M-02, M-03 |
