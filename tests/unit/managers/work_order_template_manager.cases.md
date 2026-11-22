# Test cases — `app/managers/work_order_template_manager.py`

> **Spec:** `tests/unit/managers/work_order_template_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-07; nothing open). The owner answered OQ-19 (bug → BUG-2345), OQ-20 (intended) and OQ-21 (bug → BUG-2346) on 2026-11-07.
> **Revision:** 2 (2026-11-07). Two causes: the owner's answers, and the spec's fill-gaps G1–G13.
> - **Owner's answers.**
>   - Q19-01 … Q19-04 are now strict xfail BUG-2345. New Q19-05 and Q19-06 pass.
>   - Q20-01 … Q20-04 are plain passing cards (R10 ✅).
>   - Q21-01, Q21-02, Q21-04 and Q21-05 are now strict xfail BUG-2346. Q21-03 is now R6a.
>   - New: Q21-07 … Q21-13. Q21-07 is the pass card for an old template that is renamed without touching either field. Q21-08 is xfail BUG-2335 and Q21-12 is xfail BUG-2346.
>   - Q21-06 is retired.
> - **Gap fills.**
>   - G1, G6: model modules, `wom`, and `patch.object(wom, …)` in Conventions and GD-43.
>   - G2: exact 404 words in 14 cards. New CT-50 … CT-54 test the check order (R10).
>   - G3: exact 422 details in UT-45, UT-46, UT-48, UT-49, UT-50, UT-53, UT-54, UT-55.
>   - G5: new CT-49 and UT-77.
>   - G7 (BUG-2350): the three-decimal money cards CT-36 … CT-39, UT-72, UT-73, AI-18 … AI-21, AI-23, UI-19 and UI-21 become strict xfail schema refusals. They kept their IDs. New overflow cards CT-47, UT-76, AI-26, UI-23. New two-decimal pass cards CT-48, AI-27.
>   - G8: CT-34 gains the session check and "nothing written"; new UT-78.
>   - G9: UI-07 wording; new UI-24.
>   - G10: new AR-25.
>   - G11: AR-20 and AR-21 check the date on the passed object.
>   - G12: new RI-07.
>   - G13: new GD-49.
>   - G4: no change; AR-22 and GD-42 already record the SQL.
>   - GD-39 is noted as a guard no input reaches after BUG-2345.
> **Revision:** 3 (2026-11-09) — executor DISCREPANCY-1: CT-26 and CT-27 expected three-decimal line quantities to be stored rounded, which `create_template` R9 (BUG-2350) refuses. Both become strict xfail BUG-2350 schema refusals, like the 13 converted rounding cards (CT-26 builds 0.124, CT-27 builds -1.005). New CT-55 (pass) keeps the part that holds today and after the fix: a zero and a two-decimal negative quantity are stored as sent. No ID retired.
> **Revision:** 4 (2026-11-09) — verifier (`work_order_template_manager.verify.md`), case-designer findings 1–4. F1: new WTMG-Q19-07 (due tomorrow, section run → no draft; strict xfail BUG-2345; kills variant B02). F2: WTMG-GD-44 gains Z9, a W2 template on S9, with Then 4–5 (kills A17). F3: new pass cards WTMG-UT-79, UT-80 (`cost` 9999999999999.99 and 0.01 through `TU`), WTMG-UI-25, UI-26 (`quantity` the same through `IU`); they hold today and after BUG-2350 (kill B12–B15). F4: new WTMG-CT-56 … CT-60, strict xfail BUG-1015, one per unpinned R10 pair: account < section, machine < line item, machine < line rule, line item < its replaced item, line item < its own rule. Finding 5 is the executor's. No ID retired.
> **Revision:** 5 (2026-11-09) — verifier round 2: in WTMG-GD-44 the W2 template Z9 now has `default_machine_id M9.id` (M9 is the standing W2 machine on S9), so a run that ignored the workspace would try to draft for it (a 404 today) instead of drafting nothing either way. The "gets no draft" checks (Then 4–5) are kept. Counts unchanged.
> **Counts:** 349 cases · 213 expected-to-pass · 136 expected-to-fail (bugs) · 9 deferred

## Reviewer summary
- **Per callable:** `_replace_approvers` 13 (7 bug) · `create_template` 60 (40 bug) · `update_template` 80 (47 bug) · `get_template` 7 · `list_templates` 7 · `delete_template` 6 · `restore_template` 8 (1 bug) · `add_item` 27 (13 bug) · `update_item` 26 (13 bug) · `remove_item` 7 · `get_items` 6 · `get_approvers` 5 · `generate_drafts_for_anchored_range` 25 (1 bug) · `generate_drafts` 49 (3 bug) · answered Q19 7 (5 bug) · Q20 4 · Q21 12 (6 bug).
- **Expected-to-fail by bug (all strict):** BUG-1015 32 · BUG-2339 20 · BUG-2350 19 · BUG-2335 11 · BUG-362 6 · BUG-2341 6 · BUG-2346 5 · BUG-2334 5 · BUG-2337 5 · BUG-2345 5 · BUG-363 4 · BUG-2340 4 · BUG-2336 4 · BUG-1228 2 · BUG-2338 2 · BUG-361 2 · BUG-2343 2 · BUG-2342 1 · BUG-2344 1.
- **Depth:** full (skill step 1a). The module writes order state (drafts) and money (`cost`).
  - **Money.** With BUG-2350 the schema refuses `cost` and `quantity` with more than 2 decimals or more than 13 integer digits. So no valid input reaches the column's half-up rounding (HR-15). The cards that used to show it (0.125, 0.124, 2.345, 0.005, 0.004, -1.005) are strict xfail schema refusals now, and no pass card sends a three-decimal value. What passes today and after the fix: 0.01 (the smallest step), 0, and 9999999999999.99 (the largest value) stored exactly. 10000000000000 (14 integer digits) is refused (xfail).
  - **Scheduling:**
    - due on the day versus the day after; end on the day versus the day before;
    - templates never anchored, inactive, or non-recurring;
    - every cadence, month ends, December→January, 29 February 2028 against 28 February 2027;
    - a 184-day range;
    - every shape of open order;
    - the late run of OQ-20 (now intended);
    - a later-date failure in the anchored range (AR-25).
- **Owner's answers in their own sections.** Q19, Q20 and Q21 keep their IDs.
  - **Q19:** a section run before the due date makes nothing (xfail BUG-2345). On the due day it makes one draft per machine, once (pass).
  - **Q21:** create and update refuse "requires approval" with no approver (xfail BUG-2346). Update checks only when the call sends `requires_approval` or `approver_user_ids`, so Q21-07 renames an old template that requires approval and has no approvers (pass). A stored approver who has since been suspended still counts (Q21-10, pass). A suspended approver sent in the call gets BUG-2335's 400 first (Q21-08).
  - No card outside these sections makes a section run over a not-due recurring template, or reaches "requires approval with no approver" through a call that sends either field and is not a refusal card.
- **Notable design choices:**
  - W0 (built before W1) and W2 (after) each carry their own type, factory, section, machine, item and account.
  - Approver refusals cover members who are suspended, invited or inactive, a profile with no membership, and managers of W0 or W2 (grants held elsewhere).
  - UI-05 and RI-05 give templates and lines explicit, crossing ids (770001 / 770002).
  - Every refusal checks the session before any re-read.
  - The BUG-2343 lock is checked by recording the SQL (spec Notes, G4).
  - Three cards are `Author: claude`: GD-43 and AR-25 (patches on `wom`), and RI-07 (a work order line row).
  - No refresh happens here, so there is no `expired_attributes` check.
- **Needs a decision:** none. The spec gaps of revision 1 are closed by the spec's Gap log (G1–G13).

## Conventions for this module

**IDs.** `WTMG` = `app/managers/work_order_template_manager.py`. `RA` _replace_approvers · `CT` create_template · `UT` update_template · `GT` get_template · `LT` list_templates · `DT` delete_template · `RT` restore_template · `AI` add_item · `UI` update_item · `RI` remove_item · `GI` get_items · `GA` get_approvers · `AR` generate_drafts_for_anchored_range · `GD` generate_drafts. Answered owner sections (2026-11-07), kept apart as in revision 1: `Q19` (`generate_drafts` R4, BUG-2345) · `Q20` (`generate_drafts` R10, intended) · `Q21` (`create_template` R6, `update_template` R9, BUG-2346).

**Actors and fixed values.**
- `M` = the singleton `work_order_template_manager` (`from app.managers.work_order_template_manager import work_order_template_manager`). `db` = the test's real session, always the first positional argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush.
- Classes: `WorkOrderTemplate`, `WorkOrderTemplateItem`, `WorkOrderTemplateApprover`, `WorkOrder`, `WorkOrderItem`, `MachineSectionAssignment` (named in the spec's Facts, G1), `WorkOrderType`, `Factory`, `FactorySection`, `Machine`, `WorkspaceMember`, `Item`, `Account` = the model of the same name in `app.models.<snake_case name>`. `WorkOrderPriorityEnum` = `app.models.enums.WorkOrderPriorityEnum`. `wom` = the singleton `work_order_manager` (`from app.managers.work_order_manager import work_order_manager`); a patch of `create_work_order_from_template` is always `patch.object(wom, "create_work_order_from_template", side_effect=…)` (spec Notes, G6). `TC`, `TU`, `IC`, `IU` = `WorkOrderTemplateCreate`, `WorkOrderTemplateUpdate`, `WorkOrderTemplateItemCreate`, `WorkOrderTemplateItemUpdate` (`app.schemas.work_order_template`). `HTTPException` = `fastapi.HTTPException`. `ValidationError` = `pydantic.ValidationError`. `IntegrityError` = `sqlalchemy.exc.IntegrityError`. `Decimal`, `date`, `datetime`, `patch` = the standard ones. `make_workspace`, `make_profile` = `tests/unit/factories.py`.
- MISSING = `999999999`. T0 = `datetime(2026, 3, 1, 9, 0, 0)`. D(n) = `date(2026, 3, n)` (D(2), D(9), D(16), D(23), D(30) are Mondays). Other dates are written as `date(…)`.

**Externals.** None. Nothing is mocked, except in cards marked `Author: claude` that say so. No method reads the clock; every date comes from arguments or rows.

**Standing rows.** In every test, built and flushed one at a time in this order, no Given line:
1. W0, W1, W2 = `make_workspace(db)` ×3, so `W0.id < W1.id < W2.id`.
2. U1 `"Karim"`, U2 `"Rahim"`, U3 `"Sara"`, U4 `"Omar"`, U5 `"Nadia"` = `make_profile(db, name=…)`, in that order.
3. Memberships `WorkspaceMember(workspace_id, user_id, role, status)`: (W1, U1, `"manager"`, `"active"`), (W1, U2, `"member"`, `"active"`), (W1, U4, `"member"`, `"suspended"`), (W0, U5, `"manager"`, `"active"`), (W2, U3, `"manager"`, `"active"`). U3 and U5 have no W1 membership.
4. Types `WorkOrderType(workspace_id, name)`: WT0 (W0, `"Service"`), WT1 (W1, `"Service"`), WT2 (W1, `"Repair"`), WT9 (W2, `"Service"`).
5. Factories `Factory(workspace_id, name, abbreviation)`: F0 (W0, `"Plant Zero"`, `"P0"`), F1 (W1, `"Plant One"`, `"P1"`), F2 (W1, `"Plant Two"`, `"P2"`), F9 (W2, `"Plant Nine"`, `"P9"`).
6. Sections `FactorySection(workspace_id, factory_id, name)`: S0 (W0, F0, `"Packing"`), S1 (W1, F1, `"Packing"`), S2 (W1, F1, `"Mixing"`), S3 (W1, F2, `"Boiler"`), S9 (W2, F9, `"Packing"`).
7. Machines `Machine(workspace_id, factory_id, name)`: M0 (W0, F0, `"Press"`), M1 (W1, F1, `"Press"`), M2 (W1, F1, `"Lathe"`), M3 (W1, F2, `"Pump"`), M9 (W2, F9, `"Press"`). Assignments `MachineSectionAssignment(workspace_id, machine_id, factory_section_id)`: M1→S1, M2→S1, M3→S3, M0→S0, M9→S9 (each in its machine's workspace). S2 has no machine.
8. Items `Item(workspace_id, name, name_normalized, unit="pcs")`: I0 (W0, `"Oil filter"`), I1 (W1, `"Oil filter"`), I2 (W1, `"Belt"`), I3 (W1, `"Bearing"`), I9 (W2, `"Oil filter"`); `name_normalized` = the name lower-cased.
9. Accounts `Account(workspace_id, name, is_active=True, is_deleted=False)`: A0 (W0, `"Upkeep"`), A1 (W1, `"Upkeep"`), A9 (W2, `"Upkeep"`).
No template, line, approver row or work order exists unless the Given lists it.

**Given rows.** Inserted directly (never through `M`), flushed one at a time in the order written. After the word "but" a line lists every column that differs. A Given line written as code is a step run exactly as written.
- **template** = `WorkOrderTemplate(workspace_id=W1.id, template_name="Oil change", work_order_type_id=WT1.id, created_by=U1.id)`; every other column left to its default (`is_active True`, flags false, `updated_by None`, `updated_at None`, `cost None`). A template of W0 is always "but `workspace_id W0.id`, `work_order_type_id WT0.id`"; of W2 "but `workspace_id W2.id`, `work_order_type_id WT9.id`".
- **weekly** (after "but") = `is_recurring True`, `recurrence_type "weekly"`, `recurrence_day 0`. **daily** = `is_recurring True`, `recurrence_type "daily"`. **monthly(d)** = `is_recurring True`, `recurrence_type "monthly"`, `recurrence_day d`.
- **line(T, I)** = `WorkOrderTemplateItem(workspace_id=W1.id, work_order_template_id=T.id, item_id=I.id, quantity=Decimal("1"), action_type="CONSUME")`.
- **approver(T, U)** = `WorkOrderTemplateApprover(workspace_id=W1.id, work_order_template_id=T.id, user_id=U.id)`.
- **order N(m, d)** = `WorkOrder(workspace_id=W1.id, work_order_number="WO-N", title="Service", factory_id=F1.id, work_order_type_id=WT1.id, machine_id=m.id, planned_date=d, status="DRAFT")`, N = the row's Given name.
- **gone** (type or section) = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id`. **gone** (machine or account) = the same plus `is_active False`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values.
- **unchanged(X)** = after re-read, every column of X equals its value at the snapshot (taken after the last Given line).
- **nothing written** = the numbers of rows in `work_order_templates`, `work_order_template_items`, `work_order_template_approvers`, `work_orders` (all workspaces) equal their values at the snapshot.
- **approvers(T)** = `db.expire_all()`, then the `user_id` of the `WorkOrderTemplateApprover` rows with `work_order_template_id == T.id` and `workspace_id == W1.id`, ordered by `id`, as a list.
- **lines(T)** = `db.expire_all()`, then the `WorkOrderTemplateItem` rows with `work_order_template_id == T.id`, ordered by `id`, as a list.
- **drafts(T)** = `db.expire_all()`, then `sorted((o.planned_date, o.machine_id) for o in <WorkOrder rows with work_order_template_id == T.id>)`. **pairs(result)** = `sorted((o.planned_date, o.machine_id) for o in result)`.
- `session:` lines check `db.new`, `db.dirty`, `db.deleted` directly after the call, before anything re-reads or expires. **session clean** = three lines: `not db.new`, `not db.dirty`, `not db.deleted`.
- `raises: HTTPException` = plain `with pytest.raises(HTTPException) as exc:` around the call, **no** savepoint; further `raises:` lines assert on `exc.value` after the block.
- `raises: ValidationError` (target `schema`) = `pytest.raises` around building the schema only; `M` is not called.
- **rolled back** = `sp = db.begin_nested()` directly before the call and `with patch.object(db, "commit", wraps=db.commit) as cm:` around it; "inside" checks first, then `sp.rollback()` and the "after" checks.
- **statement recorder** = the SQL statements the session sends during the When are recorded; `locks` = the recorded `SELECT` statements that name `work_order_templates` and contain `FOR UPDATE`; `statement:` lines check `locks`. A `log:` line (only in an `Author: claude` card) checks `caplog`.

**xfail cards.** Write the call and the checks exactly as shown, also when the call fails today with another exception. `xfail BUG-n` = `pytest.mark.xfail(strict=True, reason="BUG-n")`. Every xfail card here is strict.

**Race simulations.** None. (BUG-2343 is checked by the statement recorder, spec Notes, G4.)

## `WorkOrderTemplateManager._replace_approvers`

### WTMG-RA-01 — the old approvers are replaced by the new ones, flushed, slot empty
- **Rules:** `_replace_approvers` R1, R5, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U2).

**When**
- `result = M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U1.id])`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. count: approvers(T) `== [U1.id]`.
4. re-read the one approver row of T: `workspace_id == W1.id`, `work_order_template_id == T.id`, `user_id == U1.id`.
5. re-read the one approver row of T: `approver_slot is None`.

### WTMG-RA-02 — repeated ids count once, rows follow the order of first appearance
- **Rules:** `_replace_approvers` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.

**When**
- `result = M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U2.id, U1.id, U2.id])`.

**Then**
1. returns: `result is None`.
2. count: approvers(T) `== [U2.id, U1.id]`.

### WTMG-RA-03 — an empty list leaves no approvers
- **Rules:** `_replace_approvers` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).
3. approver(T, U2).

**When**
- `result = M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[])`.

**Then**
1. returns: `result is None`.
2. count: approvers(T) `== []`.

### WTMG-RA-04 — the same list as stored is written again without a conflict
- **Rules:** `_replace_approvers` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `result = M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U1.id])`.

**Then**
1. returns: `result is None`.
2. count: approvers(T) `== [U1.id]`.

### WTMG-RA-05 — other templates' approvers and T's rows of another workspace are untouched
- **Rules:** `_replace_approvers` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. S = template, but `template_name "Belt check"`.
2. T = template, but `requires_approval True`.
3. X = approver(S, U2).
4. Y = approver(T, U1).
5. Z = approver(T, U3), but `workspace_id W2.id`.

**When**
- `result = M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U2.id])`.

**Then**
1. returns: `result is None`.
2. count: approvers(T) `== [U2.id]`.
3. unchanged: unchanged(X).
4. unchanged: unchanged(Z).
5. count: `work_order_template_approvers` with `id == Y.id` has exactly 0 rows.

### WTMG-RA-06 — a suspended member is refused, the old approvers stay
- **Rules:** `_replace_approvers` R3 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: the id is left out)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U2).

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U1.id, U4.id])`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. count: approvers(T) `== [U2.id]`.

### WTMG-RA-07 — an invited member is refused
- **Rules:** `_replace_approvers` R3 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: the id is left out)

**Given**
1. P1 = `make_profile(db, name="Lina")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=P1.id, role="member", status="invited")`.
3. T = template, but `requires_approval True`.
4. approver(T, U2).

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[P1.id])`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. count: approvers(T) `== [U2.id]`.

### WTMG-RA-08 — a member who left (inactive) is refused
- **Rules:** `_replace_approvers` R3 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: the id is left out)

**Given**
1. P1 = `make_profile(db, name="Lina")`.
2. `WorkspaceMember(workspace_id=W1.id, user_id=P1.id, role="member", status="inactive")`.
3. T = template, but `requires_approval True`.
4. approver(T, U2).

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[P1.id])`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. count: approvers(T) `== [U2.id]`.

### WTMG-RA-09 — a profile with no membership anywhere is refused
- **Rules:** `_replace_approvers` R3 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: the id is left out)

**Given**
1. P1 = `make_profile(db, name="Lina")`.
2. T = template, but `requires_approval True`.
3. approver(T, U2).

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[P1.id])`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. count: approvers(T) `== [U2.id]`.

### WTMG-RA-10 — an active manager of W2 (a later workspace) is refused in W1
- **Rules:** `_replace_approvers` R3 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: the id is left out)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U2).

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U3.id])`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. count: approvers(T) `== [U2.id]`.

### WTMG-RA-11 — an active manager of W0 (an earlier workspace) is refused in W1
- **Rules:** `_replace_approvers` R3 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: the id is left out)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U2).

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U5.id])`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. count: approvers(T) `== [U2.id]`.

### WTMG-RA-12 — an unknown id is refused
- **Rules:** `_replace_approvers` R3 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: the id is left out)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U2).

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U1.id, MISSING])`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. count: approvers(T) `== [U2.id]`.

### WTMG-RA-13 — replacing approvers flushes and never commits
- **Rules:** `_replace_approvers` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.

**When**
- `M._replace_approvers(db, tpl_id=T.id, workspace_id=W1.id, approver_user_ids=[U1.id])`, rolled back.

**Then**
1. count: `work_order_template_approvers` with `work_order_template_id == T.id` has exactly 1 row (inside).
2. mock called: `cm.call_count == 0`.
3. count: `work_order_template_approvers` with `work_order_template_id == T.id` has exactly 0 rows (after the savepoint rollback).

## `WorkOrderTemplateManager.create_template`

> `requires_approval: true` with no approvers (R6, BUG-2346) and approvers with `requires_approval: false` (R6a) are covered in section Q21. Here, a card that sends `requires_approval: true` also sends approvers. Where those approvers include a suspended member, the card is a refusal card for an earlier check.

### WTMG-CT-01 — a minimal create stores an active template of the caller's workspace with the defaults
- **Rules:** `create_template` R1, Returns; R5 (`None`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderTemplate)`, `result.id is not None`.
2. session: `not db.new`.
3. re-read the new template: `workspace_id == W1.id`, `template_name == "Oil change"`, `work_order_type_id == WT1.id`.
4. re-read the new template: `created_by == U1.id`, `updated_by is None`, `is_active is True`.
5. re-read the new template: `priority == "MEDIUM"`, `uses_inventory is False`, `requires_approval is False`, `is_recurring is False`, `auto_generate is False`.
6. re-read the new template: `cost is None`, `account_id is None`, `default_machine_id is None`, `default_factory_section_id is None`, `next_generation_date is None`.
7. count: lines(the new template) `== []`.
8. count: approvers(the new template) `== []`.

### WTMG-CT-02 — every sent field is stored as sent
- **Rules:** `create_template` R5, R7, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Belt check", work_order_type_id=WT2.id, description="Check belts", notes="Use gloves", uses_inventory=True, requires_approval=True, auto_generate=True, account_id=A1.id, cost=Decimal("120.50"), default_factory_section_id=S1.id, default_machine_id=M1.id, is_recurring=True, recurrence_type="weekly", recurrence_day=0, next_generation_date=D(16), recurrence_start_date=D(2), recurrence_end_date=D(30), approver_user_ids=[U2.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `template_name == "Belt check"`, `work_order_type_id == WT2.id`, `description == "Check belts"`, `notes == "Use gloves"`.
3. re-read the new template: `uses_inventory is True`, `requires_approval is True`, `auto_generate is True`.
4. re-read the new template: `account_id == A1.id`, `cost == Decimal("120.50")`.
5. re-read the new template: `default_factory_section_id == S1.id`, `default_machine_id == M1.id`.
6. re-read the new template: `is_recurring is True`, `recurrence_type == "weekly"`, `recurrence_day == 0`.
7. re-read the new template: `next_generation_date == D(16)`, `recurrence_start_date == D(2)`, `recurrence_end_date == D(30)`.
8. count: approvers(the new template) `== [U2.id]`.

### WTMG-CT-03 — a type of W2 (a later workspace) is refused, nothing written
- **Rules:** `create_template` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order type with ID {WT9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. nothing written: nothing written.

### WTMG-CT-04 — a type of W0 (an earlier workspace) is refused
- **Rules:** `create_template` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT0.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order type with ID {WT0.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-05 — an unknown type is refused
- **Rules:** `create_template` R1, Errors row 1
- **Kind:** error
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=MISSING), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order type with ID 999999999 not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-06 — a soft-deleted type of the workspace is refused
- **Rules:** `create_template` R1a [BUG-1228]
- **Kind:** bug
- **Expect:** xfail BUG-1228
- **Fails today on:** Then 1 (no error: the template is created)

**Given**
1. WD = `WorkOrderType(workspace_id=W1.id, name="Old")`, but gone.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WD.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order type with ID {WD.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-07 — a whitespace-only name is rejected by the schema
- **Rules:** `create_template` R2 [BUG-2334]
- **Kind:** bug
- **Expect:** xfail BUG-2334
- **Fails today on:** Then 1 (no error)

**Given**
1. No template exists.

**When**
- build `TC(template_name="  ", work_order_type_id=WT1.id)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### WTMG-CT-08 — an empty name is rejected by the schema
- **Rules:** `create_template` R2 [BUG-2334]
- **Kind:** bug
- **Expect:** xfail BUG-2334
- **Fails today on:** Then 1 (no error)

**Given**
1. No template exists.

**When**
- build `TC(template_name="", work_order_type_id=WT1.id)` (target `schema`).

**Then**
1. raises: `ValidationError`.

### WTMG-CT-09 — a one-letter name with inner spaces and capitals is stored as typed
- **Rules:** `create_template` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="A  Oil Check", work_order_type_id=WT1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `template_name == "A  Oil Check"`.

### WTMG-CT-10 — the name is stored trimmed
- **Rules:** `create_template` R2 [BUG-2334]
- **Kind:** bug
- **Expect:** xfail BUG-2334
- **Fails today on:** Then 2 (stored as sent, with the spaces)

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="  Oil change  ", work_order_type_id=WT1.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `template_name == "Oil change"`.

### WTMG-CT-11 — an account of W2 is refused as not found, nothing written
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, account_id=A9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {A9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-12 — an account of W0 is refused as not found, nothing written
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, account_id=A0.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {A0.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-13 — an unknown account is refused as not found, nothing written
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (the call raises IntegrityError: the id is not checked)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, account_id=MISSING), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Account with ID 999999999 not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-14 — a machine of W2 is refused as not found, nothing written
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_machine_id=M9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-15 — a machine of W0 is refused as not found, nothing written
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_machine_id=M0.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {M0.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-16 — a section of W2 is refused as not found, nothing written
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_factory_section_id=S9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-17 — a section of W0 is refused as not found, nothing written
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_factory_section_id=S0.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory section with ID {S0.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-18 — a line item of W2 is refused, the whole create writes nothing
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I9.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-19 — a line item of W0 is refused, the whole create writes nothing
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I0.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I0.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-20 — an unknown line item is refused, the whole create writes nothing
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (the call raises IntegrityError: the id is not checked)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=MISSING)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-21 — a replaced item of W2 is refused, the whole create writes nothing
- **Rules:** `create_template` R3 [BUG-1015], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I1.id, action_type="REPLACE", replaced_item_id=I9.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-22 — a deleted machine of the workspace is refused as not found
- **Rules:** `create_template` R3a [BUG-2341], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2341
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. MG = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_machine_id=MG.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {MG.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-23 — a deleted section of the workspace is refused as not found
- **Rules:** `create_template` R3a [BUG-2341], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2341
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. SG = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Old line")`, but gone.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_factory_section_id=SG.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory section with ID {SG.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-24 — a closed account of the workspace is refused as not found
- **Rules:** `create_template` R3a [BUG-2341], Errors row 2
- **Kind:** bug
- **Expect:** xfail BUG-2341
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. AG = `Account(workspace_id=W1.id, name="Old upkeep")`, but gone.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, account_id=AG.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {AG.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-25 — the lines are stored in list order with the template's id and workspace
- **Rules:** `create_template` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I2.id, quantity=Decimal("2"), action_type="INSTALL", notes="Left"), IC(item_id=I1.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `len(lines(result)) == 2`.
3. re-read lines(result)[0]: `item_id == I2.id`, `quantity == Decimal("2.00")`, `action_type == "INSTALL"`, `notes == "Left"`, `replaced_item_id is None`.
4. re-read lines(result)[1]: `item_id == I1.id`, `quantity == Decimal("1.00")`, `action_type == "CONSUME"`, `notes is None`.
5. re-read lines(result)[0]: `workspace_id == W1.id`, `work_order_template_id == result.id`.
6. re-read lines(result)[1]: `workspace_id == W1.id`, `work_order_template_id == result.id`.

### WTMG-CT-26 — a line quantity with three decimals (0.124) is refused by the schema
- **Rules:** `create_template` R4, R9 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 0.12)

**Given**
1. No template exists.

**When**
- build `IC(item_id=I1.id, quantity=Decimal("0.124"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-CT-27 — a negative line quantity with three decimals (-1.005) is refused by the schema
- **Rules:** `create_template` R4, R9 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to -1.01)

**Given**
1. No template exists.

**When**
- build `IC(item_id=I2.id, quantity=Decimal("-1.005"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-CT-55 — a zero quantity and a negative two-decimal quantity are stored as sent
- **Rules:** `create_template` R4, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I1.id, quantity=Decimal("0")), IC(item_id=I2.id, quantity=Decimal("-1.01"))]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read: `[l.quantity for l in lines(result)] == [Decimal("0.00"), Decimal("-1.01")]`.

### WTMG-CT-28 — a REPLACE line with its replaced item is stored
- **Rules:** `create_template` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I1.id, action_type="REPLACE", replaced_item_id=I2.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read lines(result)[0]: `action_type == "REPLACE"`, `replaced_item_id == I2.id`.

### WTMG-CT-29 — a REPLACE line with no replaced item refuses the whole create
- **Rules:** `create_template` R4 [BUG-2336], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2336
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I2.id), IC(item_id=I1.id, action_type="REPLACE")]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Select the item being replaced"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-30 — a replaced item on a CONSUME line refuses the create
- **Rules:** `create_template` R4 [BUG-2337], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2337
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I1.id, replaced_item_id=I2.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "replaced_item_id only applies to Replace"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-31 — the same item twice refuses the create with 409
- **Rules:** `create_template` R4 [BUG-2338], Errors row 3
- **Kind:** bug
- **Expect:** xfail BUG-2338
- **Fails today on:** Then 1 (no error: two lines are stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I1.id), IC(item_id=I2.id), IC(item_id=I1.id, quantity=Decimal("3"))]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Oil filter is already on this template"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-32 — approvers are stored in the order sent
- **Rules:** `create_template` R5
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, requires_approval=True, approver_user_ids=[U2.id, U1.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: approvers(result) `== [U2.id, U1.id]`.

### WTMG-CT-33 — an empty approver list stores none
- **Rules:** `create_template` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, approver_user_ids=[]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: approvers(result) `== []`.

### WTMG-CT-34 — a suspended approver refuses the create before anything is written
- **Rules:** `create_template` R5 [BUG-2335], Errors row 4
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: U4 is left out)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, requires_approval=True, uses_inventory=True, items=[IC(item_id=I1.id)], approver_user_ids=[U1.id, U4.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. nothing written: nothing written.

### WTMG-CT-35 — lines are stored even when uses_inventory is false
- **Rules:** `create_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=False, items=[IC(item_id=I1.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `uses_inventory is False`.
3. count: `[l.item_id for l in lines(result)] == [I1.id]`.

### WTMG-CT-36 — cost 0.125 (three decimals) is refused by the schema
- **Rules:** `create_template` R9 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 0.13)

**Given**
1. No template exists.

**When**
- build `TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("0.125"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-CT-37 — cost 0.124 (three decimals) is refused by the schema
- **Rules:** `create_template` R9 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 0.12)

**Given**
1. No template exists.

**When**
- build `TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("0.124"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-CT-38 — cost 2.345 (three decimals) is refused by the schema
- **Rules:** `create_template` R9 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 2.35)

**Given**
1. No template exists.

**When**
- build `TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("2.345"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-CT-39 — cost -1.005 (three decimals) is refused by the schema
- **Rules:** `create_template` R9 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to -1.01)

**Given**
1. No template exists.

**When**
- build `TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("-1.005"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-CT-40 — cost 0 is stored as 0.00 (zero is a value, not missing)
- **Rules:** `create_template` Returns; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("0")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `cost == Decimal("0.00")`.

### WTMG-CT-41 — cost 9999999999999.99 is stored as 9999999999999.99 (the largest value of Numeric(15, 2))
- **Rules:** `create_template` Returns; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("9999999999999.99")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `cost == Decimal("9999999999999.99")`.

### WTMG-CT-42 — a monthly template with no day takes the day of its start date
- **Rules:** `create_template` R7; recurrence R8a [BUG-363]
- **Kind:** bug
- **Expect:** xfail BUG-363
- **Fails today on:** Then 2 (stored `None`)

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, is_recurring=True, recurrence_type="monthly", recurrence_start_date=date(2026, 1, 31), next_generation_date=date(2026, 2, 28)), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `recurrence_day == 31`.

### WTMG-CT-43 — a monthly template with no day and no start takes the day of its next date
- **Rules:** `create_template` R7; recurrence R8a [BUG-363]
- **Kind:** bug
- **Expect:** xfail BUG-363
- **Fails today on:** Then 2 (stored `None`)

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, is_recurring=True, recurrence_type="monthly", next_generation_date=date(2026, 2, 15)), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `recurrence_day == 15`.

### WTMG-CT-44 — a monthly template with no day and no dates keeps no day
- **Rules:** `create_template` R7; recurrence R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, is_recurring=True, recurrence_type="monthly"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `recurrence_day is None`.

### WTMG-CT-45 — an explicit monthly day is kept, not taken from the start date
- **Rules:** `create_template` R7; recurrence R8a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, is_recurring=True, recurrence_type="monthly", recurrence_day=10, recurrence_start_date=date(2026, 1, 31)), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `recurrence_day == 10`.

### WTMG-CT-46 — create flushes and never commits
- **Rules:** `create_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Rolled back", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I1.id)]), workspace_id=W1.id, user_id=U1.id)`, rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: `work_order_templates` with `template_name == "Rolled back"` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `work_order_templates` with `template_name == "Rolled back"` has exactly 0 rows (after the savepoint rollback).

### WTMG-CT-47 — cost 10000000000000 (14 integer digits) is refused by the schema
- **Rules:** `create_template` R9 [BUG-2350]
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; today the flush raises DataError 22003)

**Given**
1. No template exists.

**When**
- build `TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("10000000000000"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-CT-48 — cost 0.01 (two decimals, the smallest step) is accepted and stored exactly
- **Rules:** `create_template` R9; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, cost=Decimal("0.01")), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `cost == Decimal("0.01")`.

### WTMG-CT-49 — priority and the free-text assignee are stored as sent
- **Rules:** `create_template` Returns (spec Facts, G5)
- **Kind:** happy
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, priority=WorkOrderPriorityEnum.HIGH, assigned_to="Karim"), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `priority == "HIGH"`, `assigned_to == "Karim"`.

### WTMG-CT-50 — check order: a bad account is reported before a bad machine
- **Rules:** `create_template` R10, R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: both links are stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, account_id=A9.id, default_machine_id=M9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {A9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-51 — check order: a bad section is reported before a bad machine
- **Rules:** `create_template` R10, R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: both links are stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_factory_section_id=S9.id, default_machine_id=M9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-52 — check order: a bad type is reported before a bad account
- **Rules:** `create_template` R10, R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT9.id, account_id=A9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order type with ID {WT9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-53 — check order: a bad line item is reported before a suspended approver
- **Rules:** `create_template` R10, R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored and U4 is left out)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, requires_approval=True, uses_inventory=True, items=[IC(item_id=I9.id)], approver_user_ids=[U4.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-54 — check order: the first line's rule is reported before the second line's item
- **Rules:** `create_template` R10, R4 [BUG-2336]
- **Kind:** bug
- **Expect:** xfail BUG-2336
- **Fails today on:** Then 1 (no error: both lines are stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I1.id, action_type="REPLACE"), IC(item_id=I9.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Select the item being replaced"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-56 — check order: a bad account is reported before a bad section
- **Rules:** `create_template` R10, R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: both links are stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, account_id=A9.id, default_factory_section_id=S9.id), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {A9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-57 — check order: a bad machine is reported before a bad line item
- **Rules:** `create_template` R10, R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the machine and the line are stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_machine_id=M9.id, uses_inventory=True, items=[IC(item_id=I9.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-58 — check order: a bad machine is reported before a line's own rule
- **Rules:** `create_template` R10, R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the machine and the REPLACE line are stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, default_machine_id=M9.id, uses_inventory=True, items=[IC(item_id=I1.id, action_type="REPLACE")]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-59 — check order: a line's item is reported before its replaced item
- **Rules:** `create_template` R10, R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored with both items)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I9.id, action_type="REPLACE", replaced_item_id=I0.id)]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-CT-60 — check order: a line's item is reported before its own line rule
- **Rules:** `create_template` R10, R3, R4 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the REPLACE line with W2's item is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Oil change", work_order_type_id=WT1.id, uses_inventory=True, items=[IC(item_id=I9.id, action_type="REPLACE")]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. nothing written: nothing written.

## `WorkOrderTemplateManager.update_template`

> Leaving `requires_approval` true with no approvers (`update_template` R9, BUG-2346) is covered in section Q21. Cards that set approvers use a template with `requires_approval True`; cards that remove them use one with `requires_approval False`.

### WTMG-UT-01 — a sent field is changed and the template is stamped
- **Rules:** `update_template` R5, R10, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `description "Old"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(description="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `description == "New"`, `template_name == "Oil change"`.
3. re-read T: `updated_by == U2.id`, `updated_at is not None`, `created_by == U1.id`.

### WTMG-UT-02 — an unknown id is refused, nothing changes
- **Rules:** `update_template` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=MISSING, data=TU(description="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order template with ID 999999999 not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-03 — a template of W2 (a later row) is refused in W1
- **Rules:** `update_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.

**When**
- `M.update_template(db, tpl_id=Z.id, data=TU(description="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(Z).

### WTMG-UT-04 — a template of W0 (an earlier row) is refused in W1
- **Rules:** `update_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. T = template.

**When**
- `M.update_template(db, tpl_id=Z.id, data=TU(description="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(Z).

### WTMG-UT-05 — an inactive template can be updated and stays inactive
- **Rules:** `update_template` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(notes="Checked"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `notes == "Checked"`, `is_active is False`.

### WTMG-UT-06 — is_active true restores an inactive template
- **Rules:** `update_template` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(is_active=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_active is True`, `updated_by == U2.id`.

### WTMG-UT-07 — is_active false deactivates an active template
- **Rules:** `update_template` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(is_active=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_active is False`, `updated_by == U2.id`.

### WTMG-UT-08 — another type of the workspace is stored
- **Rules:** `update_template` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(work_order_type_id=WT2.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `work_order_type_id == WT2.id`.

### WTMG-UT-09 — a type of W2 is refused, nothing changes
- **Rules:** `update_template` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(work_order_type_id=WT9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order type with ID {WT9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-10 — a type of W0 is refused, nothing changes
- **Rules:** `update_template` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(work_order_type_id=WT0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order type with ID {WT0.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-11 — an unknown type is refused
- **Rules:** `update_template` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(work_order_type_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order type with ID 999999999 not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-12 — a soft-deleted type that is not the current one is refused
- **Rules:** `update_template` R3 [BUG-1228]
- **Kind:** bug
- **Expect:** xfail BUG-1228
- **Fails today on:** Then 1 (no error: the type is stored)

**Given**
1. WD = `WorkOrderType(workspace_id=W1.id, name="Old")`, but gone.
2. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(work_order_type_id=WD.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order type with ID {WD.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-13 — the current type, deleted meanwhile, is accepted when re-sent
- **Rules:** `update_template` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WD = `WorkOrderType(workspace_id=W1.id, name="Old")`, but gone.
2. T = template, but `work_order_type_id WD.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(work_order_type_id=WD.id, notes="Kept"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `work_order_type_id == WD.id`, `notes == "Kept"`.

### WTMG-UT-14 — the name is stored trimmed
- **Rules:** `update_template` R4 [BUG-2334]
- **Kind:** bug
- **Expect:** xfail BUG-2334
- **Fails today on:** Then 2 (stored with the spaces)

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(template_name="  Pump check  "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == "Pump check"`.

### WTMG-UT-15 — a whitespace-only name is rejected by the schema
- **Rules:** `update_template` R4 [BUG-2334]
- **Kind:** bug
- **Expect:** xfail BUG-2334
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(template_name="  ")` (target `schema`).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-16 — fields not sent are left as they are
- **Rules:** `update_template` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `description "Old"`, `notes "Keep"`, `cost Decimal("5.00")`, `account_id A1.id`, `default_machine_id M1.id`, `priority "MEDIUM"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(description="New"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `description == "New"`.
3. re-read T: `notes == "Keep"`, `cost == Decimal("5.00")`, `account_id == A1.id`, `default_machine_id == M1.id`, `priority == "MEDIUM"`, `template_name == "Oil change"`.

### WTMG-UT-17 — an explicit null clears description
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored, the old value stays)

**Given**
1. T = template, but `description "Old"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(description=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `description is None`.

### WTMG-UT-18 — an explicit null clears cost
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored, the old value stays)

**Given**
1. T = template, but `cost Decimal("5.00")`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(cost=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `cost is None`.

### WTMG-UT-19 — an explicit null clears account_id
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored, the old value stays)

**Given**
1. T = template, but `account_id A1.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(account_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `account_id is None`.

### WTMG-UT-20 — an explicit null clears default_machine_id
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored, the old value stays)

**Given**
1. T = template, but `default_machine_id M1.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(default_machine_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `default_machine_id is None`.

### WTMG-UT-21 — an explicit null clears next_generation_date
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored, the old value stays)

**Given**
1. T = template, but `next_generation_date D(16)`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(next_generation_date=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `next_generation_date is None`.

### WTMG-UT-22 — explicit nulls clear notes, the range dates and the section
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the nulls are ignored)

**Given**
1. T = template, but `notes "Keep"`, `recurrence_start_date D(2)`, `recurrence_end_date D(30)`, `default_factory_section_id S1.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(notes=None, recurrence_start_date=None, recurrence_end_date=None, default_factory_section_id=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `notes is None`, `recurrence_start_date is None`, `recurrence_end_date is None`, `default_factory_section_id is None`.

### WTMG-UT-23 — explicit nulls clear the type and day of a non-recurring template
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the nulls are ignored)

**Given**
1. T = template, but `recurrence_type "daily"`, `recurrence_day 3`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(recurrence_type=None, recurrence_day=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_type is None`, `recurrence_day is None`.

### WTMG-UT-24 — null for template_name is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(template_name=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-25 — null for work_order_type_id is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(work_order_type_id=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-26 — null for priority is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(priority=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-27 — null for uses_inventory is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(uses_inventory=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-28 — null for requires_approval is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(requires_approval=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-29 — null for is_active is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(is_active=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-30 — null for is_recurring is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(is_recurring=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-31 — null for auto_generate is rejected
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `TU(auto_generate=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UT-32 — an account of W2 is refused, nothing changes
- **Rules:** `update_template` R6 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(account_id=A9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {A9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-33 — an account of W0 is refused, nothing changes
- **Rules:** `update_template` R6 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(account_id=A0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {A0.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-34 — a machine of W2 is refused, nothing changes
- **Rules:** `update_template` R6 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(default_machine_id=M9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-35 — a machine of W0 is refused, nothing changes
- **Rules:** `update_template` R6 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(default_machine_id=M0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {M0.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-36 — a section of W2 is refused, nothing changes
- **Rules:** `update_template` R6 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(default_factory_section_id=S9.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory section with ID {S9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-37 — a section of W0 is refused, nothing changes
- **Rules:** `update_template` R6 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(default_factory_section_id=S0.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory section with ID {S0.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-38 — an unknown account is refused, nothing changes
- **Rules:** `update_template` R6 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (the call raises IntegrityError: the id is not checked)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(account_id=MISSING), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Account with ID 999999999 not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-39 — a deleted machine that is not the current one is refused
- **Rules:** `update_template` R6a [BUG-2341]
- **Kind:** bug
- **Expect:** xfail BUG-2341
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. MG = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.
2. T = template, but `default_machine_id M1.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(default_machine_id=MG.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {MG.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-40 — a deleted section that is not the current one is refused
- **Rules:** `update_template` R6a [BUG-2341]
- **Kind:** bug
- **Expect:** xfail BUG-2341
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. SG = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Old line")`, but gone.
2. T = template, but `default_factory_section_id S1.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(default_factory_section_id=SG.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Factory section with ID {SG.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-41 — a closed account that is not the current one is refused
- **Rules:** `update_template` R6a [BUG-2341]
- **Kind:** bug
- **Expect:** xfail BUG-2341
- **Fails today on:** Then 1 (no error: the link is stored)

**Given**
1. AG = `Account(workspace_id=W1.id, name="Old upkeep")`, but gone.
2. T = template, but `account_id A1.id`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(account_id=AG.id), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Account with ID {AG.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-42 — a deleted machine already on the template is accepted when re-sent
- **Rules:** `update_template` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. MG = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.
2. T = template, but `default_machine_id MG.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(default_machine_id=MG.id, notes="Kept"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `default_machine_id == MG.id`, `notes == "Kept"`.

### WTMG-UT-43 — a deleted section already on the template is accepted when re-sent
- **Rules:** `update_template` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. SG = `FactorySection(workspace_id=W1.id, factory_id=F1.id, name="Old line")`, but gone.
2. T = template, but `default_factory_section_id SG.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(default_factory_section_id=SG.id, notes="Kept"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `default_factory_section_id == SG.id`, `notes == "Kept"`.

### WTMG-UT-44 — a closed account already on the template is accepted when re-sent
- **Rules:** `update_template` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AG = `Account(workspace_id=W1.id, name="Old upkeep")`, but gone.
2. T = template, but `account_id AG.id`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(account_id=AG.id, notes="Kept"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `account_id == AG.id`, `notes == "Kept"`.

### WTMG-UT-45 — a weekly day of 7 is refused
- **Rules:** `update_template` R7; recurrence R4a [BUG-362]
- **Kind:** bug
- **Expect:** xfail BUG-362
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=7), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Weekly recurrence day must be between 0 and 6"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-46 — a weekly day of -1 is refused
- **Rules:** `update_template` R7; recurrence R4a [BUG-362]
- **Kind:** bug
- **Expect:** xfail BUG-362
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=-1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Weekly recurrence day must be between 0 and 6"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-47 — a weekly day of 6 is accepted
- **Rules:** `update_template` R7; recurrence R4a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=6), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_day == 6`.

### WTMG-UT-48 — a stored day 9 becomes invalid when the type is changed to weekly (merged state)
- **Rules:** `update_template` R7; recurrence R4a [BUG-362]
- **Kind:** bug
- **Expect:** xfail BUG-362
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template, but daily, `recurrence_day 9`, `next_generation_date D(16)`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(recurrence_type="weekly"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Weekly recurrence day must be between 0 and 6"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-49 — a monthly day of 0 is refused
- **Rules:** `update_template` R7; recurrence R7a [BUG-362]
- **Kind:** bug
- **Expect:** xfail BUG-362
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template, but monthly(15), `next_generation_date D(16)`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=0), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Monthly recurrence day must be between 1 and 31"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-50 — a monthly day of 32 is refused
- **Rules:** `update_template` R7; recurrence R7a [BUG-362]
- **Kind:** bug
- **Expect:** xfail BUG-362
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template, but monthly(15), `next_generation_date D(16)`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=32), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Monthly recurrence day must be between 1 and 31"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-51 — a monthly day of 31 is accepted
- **Rules:** `update_template` R7; recurrence R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(15), `next_generation_date D(16)`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=31), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_day == 31`.

### WTMG-UT-52 — a monthly day of 1 is accepted
- **Rules:** `update_template` R7; recurrence R7a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(15), `next_generation_date D(16)`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_day == 1`.

### WTMG-UT-53 — a stored day 45 becomes invalid when the type is changed to monthly (merged state)
- **Rules:** `update_template` R7; recurrence R7a [BUG-362]
- **Kind:** bug
- **Expect:** xfail BUG-362
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template, but daily, `recurrence_day 45`, `next_generation_date D(16)`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(recurrence_type="monthly"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "Monthly recurrence day must be between 1 and 31"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-54 — turning a template with no type recurring is refused
- **Rules:** `update_template` R7; recurrence R11b [BUG-361]
- **Kind:** bug
- **Expect:** xfail BUG-361
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(is_recurring=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "A recurring template needs a recurrence type"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-55 — clearing the type of a recurring template is refused
- **Rules:** `update_template` R7; recurrence R11b [BUG-361]
- **Kind:** bug
- **Expect:** xfail BUG-361
- **Fails today on:** Then 1 (no error: the value is stored)

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(recurrence_type=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 422`.
2. raises: `exc.value.detail == "A recurring template needs a recurrence type"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. unchanged: unchanged(T).

### WTMG-UT-56 — a non-recurring template keeps a null type on another update
- **Rules:** `update_template` R7; recurrence R11b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(notes="Checked"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_type is None`, `notes == "Checked"`.

### WTMG-UT-57 — a daily template accepts day 45 and keeps it
- **Rules:** `update_template` R7; recurrence R10a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(16)`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=45), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_day == 45`.

### WTMG-UT-58 — a non-recurring untyped template accepts day -1 and keeps it
- **Rules:** `update_template` R7; recurrence R10a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(recurrence_day=-1), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_day == -1`.

### WTMG-UT-59 — a monthly template with no day gets the day of its start date on update
- **Rules:** `update_template` R7; recurrence R8a [BUG-363]
- **Kind:** bug
- **Expect:** xfail BUG-363
- **Fails today on:** Then 2 (stays `None`)

**Given**
1. T = template, but `is_recurring True`, `recurrence_type "monthly"`, `recurrence_start_date date(2026, 1, 31)`, `next_generation_date date(2026, 2, 28)`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(notes="Checked"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_day == 31`.

### WTMG-UT-60 — a daily template changed to monthly with no start takes the day of its next date
- **Rules:** `update_template` R7; recurrence R8a [BUG-363]
- **Kind:** bug
- **Expect:** xfail BUG-363
- **Fails today on:** Then 2 (stays `None`)

**Given**
1. T = template, but daily, `next_generation_date date(2026, 2, 15)`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(recurrence_type="monthly"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `recurrence_day == 15`.

### WTMG-UT-61 — sent approvers replace the old ones, in the order sent
- **Rules:** `update_template` R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=[U2.id, U1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. count: approvers(T) `== [U2.id, U1.id]`.

### WTMG-UT-62 — approvers not sent are untouched
- **Rules:** `update_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. X = approver(T, U1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(notes="Checked"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. count: approvers(T) `== [U1.id]`.
3. unchanged: unchanged(X).

### WTMG-UT-63 — approvers sent as null remove all
- **Rules:** `update_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. approver(T, U1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. count: approvers(T) `== []`.

### WTMG-UT-64 — approvers sent as an empty list remove all
- **Rules:** `update_template` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. approver(T, U1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. count: approvers(T) `== []`.

### WTMG-UT-65 — a suspended approver is refused and the old approvers stay
- **Rules:** `update_template` R8 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: U4 is left out)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=[U4.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. count: approvers(T) `== [U1.id]`.

### WTMG-UT-66 — an empty update returns the template and changes no field
- **Rules:** `update_template` R5, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `description "Old"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `description == "Old"`, `template_name == "Oil change"`, `is_active is True`.

### WTMG-UT-67 — an empty update writes no stamp
- **Rules:** `update_template` R10 [BUG-2340]
- **Kind:** bug
- **Expect:** xfail BUG-2340
- **Fails today on:** Then 2 (`updated_by == U2.id`)

**Given**
1. T = template, but `description "Old"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `updated_by is None`, `updated_at is None`.

### WTMG-UT-68 — re-sending the stored value writes no stamp
- **Rules:** `update_template` R10 [BUG-2340]
- **Kind:** bug
- **Expect:** xfail BUG-2340
- **Fails today on:** Then 2 (`updated_by == U2.id`)

**Given**
1. T = template, but `description "Old"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(description="Old"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `updated_by is None`, `updated_at is None`.

### WTMG-UT-69 — re-sending the same approver set writes no stamp
- **Rules:** `update_template` R10 [BUG-2340]
- **Kind:** bug
- **Expect:** xfail BUG-2340
- **Fails today on:** Then 2 (`updated_by == U2.id`)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=[U1.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `updated_by is None`, `updated_at is None`.

### WTMG-UT-70 — a change of the approver set alone stamps the template
- **Rules:** `update_template` R10
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=[U2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `updated_by == U2.id`.
3. count: approvers(T) `== [U2.id]`.

### WTMG-UT-71 — the template's lines are not touched
- **Rules:** `update_template` R11
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `uses_inventory True`.
2. L = line(T, I1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(uses_inventory=False), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `uses_inventory is False`.
3. unchanged: unchanged(L).

### WTMG-UT-72 — a sent cost 0.125 (three decimals) is refused by the schema
- **Rules:** `update_template` R5a [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 0.13)

**Given**
1. T = template, but `cost Decimal("5.00")`.

**When**
- build `TU(cost=Decimal("0.125"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-UT-73 — a sent cost 2.345 (three decimals) is refused by the schema
- **Rules:** `update_template` R5a [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 2.35)

**Given**
1. T = template, but `cost Decimal("5.00")`.

**When**
- build `TU(cost=Decimal("2.345"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-UT-74 — cost 0 is stored as 0.00 (zero is a value and replaces 5.00)
- **Rules:** `update_template` R5; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `cost Decimal("5.00")`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(cost=Decimal("0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `cost == Decimal("0.00")`.

### WTMG-UT-75 — update flushes and never commits
- **Rules:** `update_template` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `description "Old"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(description="New"), workspace_id=W1.id, user_id=U2.id)`, rolled back.

**Then**
1. returns: `result.id == T.id` (inside).
2. count: `work_order_templates` with `id == T.id` and `description == "New"` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `work_order_templates` with `id == T.id` and `description == "New"` has exactly 0 rows (after the savepoint rollback).

### WTMG-UT-76 — a sent cost 10000000000000 (14 integer digits) is refused by the schema
- **Rules:** `update_template` R5a [BUG-2350]
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; today the flush raises DataError 22003)

**Given**
1. T = template, but `cost Decimal("5.00")`.

**When**
- build `TU(cost=Decimal("10000000000000"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-UT-77 — an explicit null clears the free-text assignee
- **Rules:** `update_template` R5 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored: "Karim" stays)

**Given**
1. T = template, but `assigned_to "Karim"`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(assigned_to=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `assigned_to is None`.

### WTMG-UT-78 — a suspended approver is refused before any field is written
- **Rules:** `update_template` R8 [BUG-2335]
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: U4 is left out and the name is written)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(template_name="Belt check", approver_user_ids=[U1.id, U4.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.dirty`.
4. session: `not db.new`.
5. returns: on T itself, before any re-read: `T.template_name == "Oil change"`, `T.updated_by is None`.
6. unchanged: unchanged(T).
7. count: approvers(T) `== [U1.id]`.

### WTMG-UT-79 — the largest cost, 9999999999999.99, is stored exactly
- **Rules:** `update_template` R5a (BUG-2350 bounds, accepted)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `cost Decimal("5.00")`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(cost=Decimal("9999999999999.99")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `cost == Decimal("9999999999999.99")`.

### WTMG-UT-80 — the smallest cost step, 0.01, is stored exactly
- **Rules:** `update_template` R5a (BUG-2350 bounds, accepted)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `cost Decimal("5.00")`.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(cost=Decimal("0.01")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `cost == Decimal("0.01")`.

## `WorkOrderTemplateManager.get_template`

### WTMG-GT-01 — returns the workspace's template
- **Rules:** `get_template` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = template, but `template_name "Belt check"`.
2. T = template.

**When**
- `result = M.get_template(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderTemplate)`, `result.id == T.id`, `result.template_name == "Oil change"`.

### WTMG-GT-02 — an inactive template is returned
- **Rules:** `get_template` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `result = M.get_template(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`, `result.is_active is False`.

### WTMG-GT-03 — an unknown id is 404
- **Rules:** `get_template` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.get_template(db, tpl_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order template with ID 999999999 not found"`.

### WTMG-GT-04 — a template of W2 (a later row) is 404 in W1
- **Rules:** `get_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.

**When**
- `M.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.

### WTMG-GT-05 — a template of W0 (an earlier row) is 404 in W1
- **Rules:** `get_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. T = template.

**When**
- `M.get_template(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.

### WTMG-GT-06 — W1's template asked for under W2 is 404
- **Rules:** `get_template` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.get_template(db, tpl_id=T.id, workspace_id=W2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {T.id} not found"`.

### WTMG-GT-07 — writes nothing: a pending row and an unflushed edit stay as they were
- **Rules:** `get_template` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. S = template, but `template_name "Belt check"`.
3. `S.notes = "Edited"` (not flushed).
4. `P = WorkOrderTemplate(workspace_id=W1.id, template_name="Pending", work_order_type_id=WT1.id)`, then `db.add(P)` (not flushed).

**When**
- `result = M.get_template(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == T.id`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `S in db.dirty`.
5. session: `len(db.dirty) == 1`.

## `WorkOrderTemplateManager.list_templates`

> Pass-through to `WorkOrderTemplateDAO.get_by_workspace` (DAO R1–R8, tested in the DAO's cases). Every Given template here gets an explicit, distinct `created_at`, so the order is not tied (BUG-2330 is the DAO's).

### WTMG-LT-01 — with the defaults: the workspace's templates newest first, active and inactive
- **Rules:** `list_templates` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Z0 = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`, `created_at datetime(2026, 3, 9, 9, 0, 0)`.
2. T1 = template, but `created_at datetime(2026, 3, 2, 9, 0, 0)`.
3. T2 = template, but `created_at datetime(2026, 3, 4, 9, 0, 0)`, `is_active False`.
4. T3 = template, but `created_at datetime(2026, 3, 3, 9, 0, 0)`.
5. Z9 = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `created_at datetime(2026, 3, 9, 9, 0, 0)`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `[t.id for t in result] == [T2.id, T3.id, T1.id]`.

### WTMG-LT-02 — is_active is passed through
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = template, but `created_at datetime(2026, 3, 2, 9, 0, 0)`.
2. T2 = template, but `created_at datetime(2026, 3, 4, 9, 0, 0)`, `is_active False`.
3. T3 = template, but `created_at datetime(2026, 3, 3, 9, 0, 0)`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id, is_active=False)`.

**Then**
1. returns: `[t.id for t in result] == [T2.id]`.

### WTMG-LT-03 — work_order_type_id is passed through
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = template, but `created_at datetime(2026, 3, 2, 9, 0, 0)`.
2. T2 = template, but `created_at datetime(2026, 3, 4, 9, 0, 0)`, `work_order_type_id WT2.id`.
3. T3 = template, but `created_at datetime(2026, 3, 3, 9, 0, 0)`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id, work_order_type_id=WT2.id)`.

**Then**
1. returns: `[t.id for t in result] == [T2.id]`.

### WTMG-LT-04 — skip and limit are passed through
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T1 = template, but `created_at datetime(2026, 3, 2, 9, 0, 0)`.
2. T2 = template, but `created_at datetime(2026, 3, 4, 9, 0, 0)`.
3. T3 = template, but `created_at datetime(2026, 3, 3, 9, 0, 0)`.

**When**
- `result = M.list_templates(db, workspace_id=W1.id, skip=1, limit=1)`.

**Then**
1. returns: `[t.id for t in result] == [T3.id]`.

### WTMG-LT-05 — the default limit is 100
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all`: Ek = template, but `created_at datetime(2026, 3, 1, 9, 0, 0) + timedelta(minutes=k)`, `template_name f"Check {k}"` (`timedelta` from `datetime`).

**When**
- `result = M.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 100`.
2. returns: `E1.id not in {t.id for t in result}`.

### WTMG-LT-06 — limit=1000 gives all 101
- **Rules:** `list_templates` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. 101 templates E1 … E101, built with `add_all`: Ek = template, but `created_at datetime(2026, 3, 1, 9, 0, 0) + timedelta(minutes=k)`, `template_name f"Check {k}"` (`timedelta` from `datetime`).

**When**
- `result = M.list_templates(db, workspace_id=W1.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### WTMG-LT-07 — writes nothing: a pending row and an unflushed edit stay as they were
- **Rules:** `list_templates` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T1 = template, but `created_at datetime(2026, 3, 2, 9, 0, 0)`.
2. T2 = template, but `created_at datetime(2026, 3, 3, 9, 0, 0)`.
3. `T2.notes = "Edited"` (not flushed).
4. `P = WorkOrderTemplate(workspace_id=W1.id, template_name="Pending", work_order_type_id=WT1.id)`, then `db.add(P)` (not flushed).

**When**
- `result = M.list_templates(db, workspace_id=W1.id)`.

**Then**
1. returns: `T1.id in {t.id for t in result}`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `T2 in db.dirty`.
5. session: `len(db.dirty) == 1`.

## `WorkOrderTemplateManager.delete_template`

### WTMG-DT-01 — an active template is deactivated and stamped; lines, approvers and orders untouched
- **Rules:** `delete_template` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. L = line(T, I1).
3. X = approver(T, U1).
4. O = order O(M1, D(16)), but `work_order_template_id T.id`.

**When**
- `result = M.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. re-read T: `is_active is False`, `updated_by == U2.id`.
4. unchanged: unchanged(L).
5. unchanged: unchanged(X).
6. unchanged: unchanged(O).

### WTMG-DT-02 — an unknown id is 404, nothing changes
- **Rules:** `delete_template` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.delete_template(db, tpl_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order template with ID 999999999 not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(T).

### WTMG-DT-03 — a template of W2 (a later row) is 404 in W1
- **Rules:** `delete_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.

**When**
- `M.delete_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(Z).

### WTMG-DT-04 — a template of W0 (an earlier row) is 404 in W1
- **Rules:** `delete_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. T = template.

**When**
- `M.delete_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(Z).

### WTMG-DT-05 — an inactive template: no error, no stamp, nothing written
- **Rules:** `delete_template` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `result = M.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.dirty`.
3. unchanged: unchanged(T).
4. re-read T: `updated_by is None`.

### WTMG-DT-06 — delete flushes and never commits
- **Rules:** `delete_template` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.delete_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`, rolled back.

**Then**
1. count: `work_order_templates` with `id == T.id` and `is_active == False` has exactly 1 row (inside).
2. mock called: `cm.call_count == 0`.
3. count: `work_order_templates` with `id == T.id` and `is_active == False` has exactly 0 rows (after the savepoint rollback).

## `WorkOrderTemplateManager.restore_template`

### WTMG-RT-01 — an inactive template is restored and stamped
- **Rules:** `restore_template` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `result = M.restore_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_active is True`, `updated_by == U2.id`.

### WTMG-RT-02 — an unknown id is 404, nothing changes
- **Rules:** `restore_template` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `M.restore_template(db, tpl_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order template with ID 999999999 not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(T).

### WTMG-RT-03 — a template of W2 (a later row) is 404 in W1
- **Rules:** `restore_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `is_active False`.

**When**
- `M.restore_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(Z).

### WTMG-RT-04 — a template of W0 (an earlier row) is 404 in W1
- **Rules:** `restore_template` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`, `is_active False`.
2. T = template, but `is_active False`.

**When**
- `M.restore_template(db, tpl_id=Z.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Work order template with ID {Z.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(Z).

### WTMG-RT-05 — an already active template is returned and stays active
- **Rules:** `restore_template` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.restore_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_active is True`.

### WTMG-RT-06 — an already active template gets no stamp
- **Rules:** `restore_template` R2 [BUG-2340]
- **Kind:** bug
- **Expect:** xfail BUG-2340
- **Fails today on:** Then 2 (`updated_by == U2.id`)

**Given**
1. T = template.

**When**
- `result = M.restore_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `updated_by is None`, `updated_at is None`.

### WTMG-RT-07 — a type and machine deleted meanwhile are kept on restore
- **Rules:** `restore_template` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. WD = `WorkOrderType(workspace_id=W1.id, name="Old")`, but gone.
2. MG = `Machine(workspace_id=W1.id, factory_id=F1.id, name="Old press")`, but gone.
3. T = template, but `work_order_type_id WD.id`, `default_machine_id MG.id`, `is_active False`.

**When**
- `result = M.restore_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `is_active is True`, `work_order_type_id == WD.id`, `default_machine_id == MG.id`.

### WTMG-RT-08 — restore flushes and never commits
- **Rules:** `restore_template` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `result = M.restore_template(db, tpl_id=T.id, workspace_id=W1.id, user_id=U2.id)`, rolled back.

**Then**
1. returns: `result.id == T.id` (inside).
2. count: `work_order_templates` with `id == T.id` and `is_active == True` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `work_order_templates` with `id == T.id` and `is_active == True` has exactly 0 rows (after the savepoint rollback).

## `WorkOrderTemplateManager.add_item`

### WTMG-AI-01 — a line is stored with the template's id, the workspace and every field sent
- **Rules:** `add_item` R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, quantity=Decimal("2.5"), action_type="INSTALL", notes="Left side"), workspace_id=W1.id)`.

**Then**
1. returns: `isinstance(result, WorkOrderTemplateItem)`, `result.id is not None`.
2. session: `not db.new`.
3. re-read the returned line: `workspace_id == W1.id`, `work_order_template_id == T.id`, `item_id == I1.id`.
4. re-read the returned line: `quantity == Decimal("2.50")`, `action_type == "INSTALL"`, `notes == "Left side"`, `replaced_item_id is None`.

### WTMG-AI-02 — defaults: quantity 1, action CONSUME
- **Rules:** `add_item` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `quantity == Decimal("1.00")`, `action_type == "CONSUME"`.

### WTMG-AI-03 — an unknown template is 404, nothing written
- **Rules:** `add_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=MISSING, data=IC(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order template not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. nothing written: nothing written.

### WTMG-AI-04 — a template of W2 (a later row) is 404 in W1
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.

**When**
- `M.add_item(db, tpl_id=Z.id, data=IC(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order template not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. nothing written: nothing written.

### WTMG-AI-05 — a template of W0 (an earlier row) is 404 in W1
- **Rules:** `add_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. T = template.

**When**
- `M.add_item(db, tpl_id=Z.id, data=IC(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Work order template not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. nothing written: nothing written.

### WTMG-AI-06 — an inactive template accepts lines
- **Rules:** `add_item` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `[l.item_id for l in lines(T)] == [I1.id]`.

### WTMG-AI-07 — REPLACE with no replaced item is refused, nothing written
- **Rules:** `add_item` R2, Errors
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, action_type="REPLACE"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Select the item being replaced"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows.

### WTMG-AI-08 — REPLACE with a replaced item is stored
- **Rules:** `add_item` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, action_type="REPLACE", replaced_item_id=I2.id), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `action_type == "REPLACE"`, `replaced_item_id == I2.id`.

### WTMG-AI-09 — a replaced item on a CONSUME line is refused
- **Rules:** `add_item` R2a [BUG-2337]
- **Kind:** bug
- **Expect:** xfail BUG-2337
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, action_type="CONSUME", replaced_item_id=I2.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "replaced_item_id only applies to Replace"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows.

### WTMG-AI-10 — a replaced item on a BORROW line is refused
- **Rules:** `add_item` R2a [BUG-2337]
- **Kind:** bug
- **Expect:** xfail BUG-2337
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, action_type="BORROW", replaced_item_id=I2.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "replaced_item_id only applies to Replace"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows.

### WTMG-AI-11 — an item already on the template is refused with 409
- **Rules:** `add_item` R2b [BUG-2338]
- **Kind:** bug
- **Expect:** xfail BUG-2338
- **Fails today on:** Then 1 (no error: a second line is stored)

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, quantity=Decimal("2")), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 409`.
2. raises: `exc.value.detail == "Oil filter is already on this template"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `[l.id for l in lines(T)] == [L.id]`.

### WTMG-AI-12 — an item on another template does not block
- **Rules:** `add_item` R2b
- **Kind:** boundary
- **Expect:** pass

**Given**
1. S = template, but `template_name "Belt check"`.
2. line(S, I1).
3. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `[l.item_id for l in lines(T)] == [I1.id]`.

### WTMG-AI-13 — an item of W2 is refused as not found
- **Rules:** `add_item` R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=I9.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows.

### WTMG-AI-14 — an item of W0 is refused as not found
- **Rules:** `add_item` R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=I0.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I0.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows.

### WTMG-AI-15 — an unknown item is refused as not found
- **Rules:** `add_item` R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (the call raises IntegrityError: the id is not checked)

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=MISSING), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows.

### WTMG-AI-16 — a replaced item of W2 is refused as not found
- **Rules:** `add_item` R3 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: the line is stored)

**Given**
1. T = template.

**When**
- `M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, action_type="REPLACE", replaced_item_id=I9.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows.

### WTMG-AI-17 — adding a line writes no stamp on the template
- **Rules:** `add_item` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read T: `updated_by is None`, `updated_at is None`.

### WTMG-AI-18 — quantity 0.005 (three decimals) is refused by the schema
- **Rules:** `add_item` R5 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 0.01)

**Given**
1. T = template.

**When**
- build `IC(item_id=I1.id, quantity=Decimal("0.005"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-AI-19 — quantity 0.004 (three decimals) is refused by the schema
- **Rules:** `add_item` R5 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 0.00)

**Given**
1. T = template.

**When**
- build `IC(item_id=I1.id, quantity=Decimal("0.004"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-AI-20 — quantity 0.125 (three decimals) is refused by the schema
- **Rules:** `add_item` R5 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 0.13)

**Given**
1. T = template.

**When**
- build `IC(item_id=I1.id, quantity=Decimal("0.125"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-AI-21 — quantity 2.345 (three decimals) is refused by the schema
- **Rules:** `add_item` R5 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 2.35)

**Given**
1. T = template.

**When**
- build `IC(item_id=I1.id, quantity=Decimal("2.345"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-AI-22 — quantity 0 is stored as 0.00 (zero is accepted)
- **Rules:** `add_item` R4; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, quantity=Decimal("0")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `quantity == Decimal("0.00")`.

### WTMG-AI-23 — quantity -1.005 (three decimals) is refused by the schema
- **Rules:** `add_item` R5 [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to -1.01)

**Given**
1. T = template.

**When**
- build `IC(item_id=I1.id, quantity=Decimal("-1.005"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-AI-24 — quantity 9999999999999.99 is stored as 9999999999999.99 (the largest value of Numeric(15, 2))
- **Rules:** `add_item` R4; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, quantity=Decimal("9999999999999.99")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `quantity == Decimal("9999999999999.99")`.

### WTMG-AI-25 — add_item flushes and never commits
- **Rules:** `add_item` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id), workspace_id=W1.id)`, rolled back.

**Then**
1. returns: `result.id is not None` (inside).
2. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `work_order_template_items` with `work_order_template_id == T.id` has exactly 0 rows (after the savepoint rollback).

### WTMG-AI-26 — quantity 10000000000000 (14 integer digits) is refused by the schema
- **Rules:** `add_item` R5 [BUG-2350]
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; today the flush raises DataError 22003)

**Given**
1. T = template.

**When**
- build `IC(item_id=I1.id, quantity=Decimal("10000000000000"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-AI-27 — quantity 0.01 (two decimals, the smallest step) is accepted and stored exactly
- **Rules:** `add_item` R5, R4; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.add_item(db, tpl_id=T.id, data=IC(item_id=I1.id, quantity=Decimal("0.01")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned line: `quantity == Decimal("0.01")`.

## `WorkOrderTemplateManager.update_item`

### WTMG-UI-01 — sent fields are changed, the rest kept
- **Rules:** `update_item` R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(quantity=Decimal("3"), notes="Torque 40"), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. session: `not db.dirty`.
3. re-read L: `quantity == Decimal("3.00")`, `notes == "Torque 40"`.
4. re-read L: `item_id == I1.id`, `action_type == "CONSUME"`, `work_order_template_id == T.id`.

### WTMG-UI-02 — an unknown line is 404
- **Rules:** `update_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.update_item(db, item_id=MISSING, data=IU(notes="x"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Template item not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(L).

### WTMG-UI-03 — a line of W2 (a later row) is 404 in W1
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).
3. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.
4. K = line(Z, I9), but `workspace_id W2.id`.

**When**
- `M.update_item(db, item_id=K.id, data=IU(notes="x"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Template item not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(K).

### WTMG-UI-04 — a line of W0 (an earlier row) is 404 in W1
- **Rules:** `update_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. K = line(Z, I0), but `workspace_id W0.id`.
3. T = template.
4. L = line(T, I1).

**When**
- `M.update_item(db, item_id=K.id, data=IU(notes="x"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Template item not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(K).

### WTMG-UI-05 — item_id names a line, not a template: a template id with no such line is 404
- **Rules:** `update_item` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `id 770001`.
2. S = template, but `id 770002`, `template_name "Belt check"`.
3. L = line(S, I1), but `id 770002`.

**When**
- `M.update_item(db, item_id=770001, data=IU(notes="x"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Template item not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(L).

### WTMG-UI-06 — switching to REPLACE with no replaced item is refused
- **Rules:** `update_item` R2 [BUG-2336]
- **Kind:** bug
- **Expect:** xfail BUG-2336
- **Fails today on:** Then 1 (no error: the action is stored)

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.update_item(db, item_id=L.id, data=IU(action_type="REPLACE"), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Select the item being replaced"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(L).

### WTMG-UI-07 — clearing the replaced item of a REPLACE line is refused
- **Rules:** `update_item` R2, R3 (a REPLACE line keeps its item, spec G9) [BUG-2336]
- **Kind:** bug
- **Expect:** xfail BUG-2336
- **Fails today on:** Then 1 (no error: the null is ignored)

**Given**
1. T = template.
2. L = line(T, I1), but `action_type "REPLACE"`, `replaced_item_id I2.id`.

**When**
- `M.update_item(db, item_id=L.id, data=IU(replaced_item_id=None), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Select the item being replaced"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(L).

### WTMG-UI-08 — switching to REPLACE with a replaced item is stored
- **Rules:** `update_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(action_type="REPLACE", replaced_item_id=I2.id), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `action_type == "REPLACE"`, `replaced_item_id == I2.id`.

### WTMG-UI-09 — a REPLACE line keeps its stored replaced item on a quantity change
- **Rules:** `update_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1), but `action_type "REPLACE"`, `replaced_item_id I2.id`.

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(quantity=Decimal("2")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("2.00")`, `action_type == "REPLACE"`, `replaced_item_id == I2.id`.

### WTMG-UI-10 — switching away from REPLACE clears the replaced item
- **Rules:** `update_item` R2a [BUG-2337]
- **Kind:** bug
- **Expect:** xfail BUG-2337
- **Fails today on:** Then 3 (the replaced item is kept)

**Given**
1. T = template.
2. L = line(T, I1), but `action_type "REPLACE"`, `replaced_item_id I2.id`.

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(action_type="INSTALL"), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `action_type == "INSTALL"`.
3. re-read L: `replaced_item_id is None`.

### WTMG-UI-11 — switching away from REPLACE: the new action is stored
- **Rules:** `update_item` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1), but `action_type "REPLACE"`, `replaced_item_id I2.id`.

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(action_type="INSTALL"), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `action_type == "INSTALL"`, `item_id == I1.id`.

### WTMG-UI-12 — a replaced item sent on a CONSUME line is refused
- **Rules:** `update_item` R2a [BUG-2337]
- **Kind:** bug
- **Expect:** xfail BUG-2337
- **Fails today on:** Then 1 (no error: stored)

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.update_item(db, item_id=L.id, data=IU(replaced_item_id=I2.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "replaced_item_id only applies to Replace"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(L).

### WTMG-UI-13 — an explicit null clears the notes
- **Rules:** `update_item` R3 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored)

**Given**
1. T = template.
2. L = line(T, I1), but `notes "Torque 40"`.

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(notes=None), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `notes is None`.

### WTMG-UI-14 — null for quantity is rejected
- **Rules:** `update_item` R3 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `IU(quantity=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UI-15 — null for action_type is rejected
- **Rules:** `update_item` R3 [BUG-2339]
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 1 (no error)

**Given**
1. T = template.

**When**
- build `IU(action_type=None)` (target `schema`: a value wrong on its own is the schema's, spec G3).

**Then**
1. raises: `ValidationError`.

### WTMG-UI-16 — a replaced item of W2 is refused as not found
- **Rules:** `update_item` R4 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (no error: stored)

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.update_item(db, item_id=L.id, data=IU(action_type="REPLACE", replaced_item_id=I9.id), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Item with ID {I9.id} not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(L).

### WTMG-UI-17 — an unknown replaced item is refused as not found
- **Rules:** `update_item` R4 [BUG-1015]
- **Kind:** bug
- **Expect:** xfail BUG-1015
- **Fails today on:** Then 1 (the call raises IntegrityError: the id is not checked)

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.update_item(db, item_id=L.id, data=IU(action_type="REPLACE", replaced_item_id=MISSING), workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Item with ID 999999999 not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. unchanged: unchanged(L).

### WTMG-UI-18 — a line of an inactive template can be updated
- **Rules:** `update_item` R5
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.
2. L = line(T, I1).

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(notes="x"), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `notes == "x"`.

### WTMG-UI-19 — a sent quantity 2.345 (three decimals) is refused by the schema
- **Rules:** `update_item` R3a [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to 2.35)

**Given**
1. T = template.
2. L = line(T, I1), but `quantity Decimal("1")`.

**When**
- build `IU(quantity=Decimal("2.345"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-UI-20 — quantity 0 is stored as 0.00 (zero replaces 3.00)
- **Rules:** `update_item` R3; HR-15
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1), but `quantity Decimal("3")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(quantity=Decimal("0")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("0.00")`.

### WTMG-UI-21 — a sent quantity -1.005 (three decimals) is refused by the schema
- **Rules:** `update_item` R3a [BUG-2350]; HR-15
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; the column would round it to -1.01)

**Given**
1. T = template.
2. L = line(T, I1), but `quantity Decimal("1")`.

**When**
- build `IU(quantity=Decimal("-1.005"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-UI-22 — update_item flushes and never commits
- **Rules:** `update_item` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(notes="Rolled"), workspace_id=W1.id)`, rolled back.

**Then**
1. returns: `result.id == L.id` (inside).
2. count: `work_order_template_items` with `id == L.id` and `notes == "Rolled"` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `work_order_template_items` with `id == L.id` and `notes == "Rolled"` has exactly 0 rows (after the savepoint rollback).

### WTMG-UI-23 — a sent quantity 10000000000000 (14 integer digits) is refused by the schema
- **Rules:** `update_item` R3a [BUG-2350]
- **Kind:** bug
- **Expect:** xfail BUG-2350
- **Fails today on:** Then 1 (no error: the schema takes any Decimal; today the flush raises DataError 22003)

**Given**
1. T = template.
2. L = line(T, I1), but `quantity Decimal("1")`.

**When**
- build `IU(quantity=Decimal("10000000000000"))` (target `schema`; `M` is not called).

**Then**
1. raises: `ValidationError`.
2. nothing written: nothing written.

### WTMG-UI-24 — an explicit null clears the replaced item of a line that is not REPLACE
- **Rules:** `update_item` R3 [BUG-2339] (spec G9)
- **Kind:** bug
- **Expect:** xfail BUG-2339
- **Fails today on:** Then 2 (the null is ignored: I2 stays)

**Given**
1. T = template.
2. L = line(T, I1), but `action_type "INSTALL"`, `replaced_item_id I2.id` (a row stored before BUG-2337).

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(replaced_item_id=None), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `replaced_item_id is None`, `action_type == "INSTALL"`.

### WTMG-UI-25 — the largest quantity, 9999999999999.99, is stored exactly
- **Rules:** `update_item` R3a (BUG-2350 bounds, accepted)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1), but `quantity Decimal("3")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(quantity=Decimal("9999999999999.99")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("9999999999999.99")`.

### WTMG-UI-26 — the smallest quantity step, 0.01, is stored exactly
- **Rules:** `update_item` R3a (BUG-2350 bounds, accepted)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1), but `quantity Decimal("3")`.

**When**
- `result = M.update_item(db, item_id=L.id, data=IU(quantity=Decimal("0.01")), workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. re-read L: `quantity == Decimal("0.01")`.

## `WorkOrderTemplateManager.remove_item`

### WTMG-RI-01 — the line is hard-deleted, the others stay, its values stay readable
- **Rules:** `remove_item` R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1), but `quantity Decimal("2")`.
3. K = line(T, I2).

**When**
- `result = M.remove_item(db, item_id=L.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.item_id == I1.id`, `result.quantity == Decimal("2.00")`.
2. session: `not db.deleted`.
3. count: `work_order_template_items` with `id == L.id` has exactly 0 rows.
4. unchanged: unchanged(K).

### WTMG-RI-02 — an unknown line is 404
- **Rules:** `remove_item` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.remove_item(db, item_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Template item not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. nothing written: nothing written.

### WTMG-RI-03 — a line of W2 (a later row) is 404 in W1
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).
3. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.
4. K = line(Z, I9), but `workspace_id W2.id`.

**When**
- `M.remove_item(db, item_id=K.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Template item not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. nothing written: nothing written.

### WTMG-RI-04 — a line of W0 (an earlier row) is 404 in W1
- **Rules:** `remove_item` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. K = line(Z, I0), but `workspace_id W0.id`.
3. T = template.
4. L = line(T, I1).

**When**
- `M.remove_item(db, item_id=K.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == "Template item not found"`.
3. session: `not db.new`.
4. session: `not db.dirty`.
5. session: `not db.deleted`.
6. nothing written: nothing written.

### WTMG-RI-05 — item_id names a line: the line with that id goes, the template with the same id stays
- **Rules:** `remove_item` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `id 770001`.
2. S = template, but `id 770002`, `template_name "Belt check"`.
3. L = line(T, I1), but `id 770002`.
4. K = line(S, I2), but `id 770001`.

**When**
- `result = M.remove_item(db, item_id=770001, workspace_id=W1.id)`.

**Then**
1. returns: `result.item_id == I2.id`.
2. count: `work_order_template_items` with `id == 770001` has exactly 0 rows.
3. unchanged: unchanged(L).
4. unchanged: unchanged(T).

### WTMG-RI-06 — remove_item flushes and never commits
- **Rules:** `remove_item` R2, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. L = line(T, I1).

**When**
- `M.remove_item(db, item_id=L.id, workspace_id=W1.id)`, rolled back.

**Then**
1. count: `work_order_template_items` with `id == L.id` has exactly 0 rows (inside).
2. mock called: `cm.call_count == 0`.
3. count: `work_order_template_items` with `id == L.id` has exactly 1 row (after the savepoint rollback).

### WTMG-RI-07 — a work order made earlier keeps its copied line when the template line is removed
- **Rules:** `remove_item` R2 (spec G12)
- **Kind:** side-effect
- **Expect:** pass
- **Author:** claude

**Given**
1. T = template, but `uses_inventory True`.
2. L = line(T, I1), but `quantity Decimal("2")`.
3. O = order O(M1, D(16)), but `work_order_template_id T.id`.
4. WI = `WorkOrderItem(work_order_id=O.id, item_id=I1.id, quantity=Decimal("2"), action_type="CONSUME", replaced_item_id=None)` (the columns the spec names; add any other NOT NULL column the model requires, e.g. a workspace id, with W1's value).

**When**
- `result = M.remove_item(db, item_id=L.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == L.id`.
2. count: lines(T) `== []`.
3. unchanged: unchanged(WI).
4. re-read WI: `item_id == I1.id`, `quantity == Decimal("2.00")`, `action_type == "CONSUME"`.

## `WorkOrderTemplateManager.get_items`

### WTMG-GI-01 — all lines of the template in id order
- **Rules:** `get_items` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = template, but `template_name "Belt check"`.
2. T = template.
3. A = line(T, I2).
4. X = line(S, I1).
5. B = line(T, I1).

**When**
- `result = M.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [A.id, B.id]`.

### WTMG-GI-02 — an unknown template gives an empty list
- **Rules:** `get_items` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. line(T, I1).

**When**
- `result = M.get_items(db, tpl_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WTMG-GI-03 — a template of W2 asked for in W1 gives an empty list
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.
3. line(Z, I9), but `workspace_id W2.id`.

**When**
- `result = M.get_items(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WTMG-GI-04 — a template of W0 asked for in W1 gives an empty list
- **Rules:** `get_items` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. line(Z, I0), but `workspace_id W0.id`.
3. T = template.

**When**
- `result = M.get_items(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WTMG-GI-05 — the lines of an inactive template are returned
- **Rules:** `get_items` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but `is_active False`.
2. A = line(T, I1).

**When**
- `result = M.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [A.id]`.

### WTMG-GI-06 — writes nothing: a pending row and an unflushed edit stay
- **Rules:** `get_items` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template.
2. A = line(T, I1).
3. `A.notes = "Edited"` (not flushed).
4. `P = WorkOrderTemplate(workspace_id=W1.id, template_name="Pending", work_order_type_id=WT1.id)`, then `db.add(P)` (not flushed).

**When**
- `result = M.get_items(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `[l.id for l in result] == [A.id]`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `A in db.dirty`.
5. session: `len(db.dirty) == 1`.

## `WorkOrderTemplateManager.get_approvers`

> The order of the rows is the DAO's (BUG-2331, DAO cases); these cards compare sets.

### WTMG-GA-01 — the template's approver rows
- **Rules:** `get_approvers` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. S = template, but `template_name "Belt check"`.
2. T = template, but `requires_approval True`.
3. approver(T, U2).
4. approver(S, U4).
5. approver(T, U1).

**When**
- `result = M.get_approvers(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `len(result) == 2`.
2. returns: `{a.user_id for a in result} == {U1.id, U2.id}`.

### WTMG-GA-02 — an unknown template gives an empty list
- **Rules:** `get_approvers` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. approver(T, U1).

**When**
- `result = M.get_approvers(db, tpl_id=MISSING, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WTMG-GA-03 — a template of W2 asked for in W1 gives an empty list
- **Rules:** `get_approvers` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template.
2. Z = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`.
3. approver(Z, U3), but `workspace_id W2.id`.

**When**
- `result = M.get_approvers(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WTMG-GA-04 — a template of W0 asked for in W1 gives an empty list
- **Rules:** `get_approvers` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`.
2. approver(Z, U5), but `workspace_id W0.id`.
3. T = template.

**When**
- `result = M.get_approvers(db, tpl_id=Z.id, workspace_id=W1.id)`.

**Then**
1. returns: `result == []`.

### WTMG-GA-05 — writes nothing: a pending row and an unflushed edit stay
- **Rules:** `get_approvers` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. X = approver(T, U1).
3. `T.notes = "Edited"` (not flushed).
4. `P = WorkOrderTemplate(workspace_id=W1.id, template_name="Pending", work_order_type_id=WT1.id)`, then `db.add(P)` (not flushed).

**When**
- `result = M.get_approvers(db, tpl_id=T.id, workspace_id=W1.id)`.

**Then**
1. returns: `{a.user_id for a in result} == {U1.id}`.
2. session: `P in db.new`.
3. session: `len(db.new) == 1`.
4. session: `T in db.dirty`.
5. session: `len(db.dirty) == 1`.

## `WorkOrderTemplateManager.generate_drafts_for_anchored_range`

> `next_generation_date` is read back twice: on the object passed in (the caller's object is changed) and after `db.expire_all()` (which drops unflushed changes, so it proves the flush).

### WTMG-AR-01 — daily: one draft per date up to the end, in date order; next date is the day after the end
- **Rules:** anchored R2, R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(3), D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. session: `not db.new`.
5. re-read T: `next_generation_date == D(5)`.
6. count: drafts(T) `== [(D(2), M1.id), (D(3), M1.id), (D(4), M1.id)]`.
7. re-read result[0]: `status == "DRAFT"`, `work_order_template_id == T.id`, `work_order_type_id == WT1.id`, `workspace_id == W1.id`.

### WTMG-AR-02 — weekly on Mondays: every Monday up to an end that is a Monday
- **Rules:** anchored R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(2)`, `recurrence_end_date D(23)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(9), D(16), D(23)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(30)`.
4. re-read T: `next_generation_date == D(30)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(9), M1.id), (D(16), M1.id), (D(23), M1.id)]`.

### WTMG-AR-03 — weekly: an end one day before a cadence date leaves that date out
- **Rules:** anchored R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(2)`, `recurrence_end_date D(22)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(9), D(16)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(23)`.
4. re-read T: `next_generation_date == D(23)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(9), M1.id), (D(16), M1.id)]`.

### WTMG-AR-04 — weekly with no day: every 7 days from the next date
- **Rules:** anchored R2, R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but `is_recurring True`, `recurrence_type "weekly"`, `next_generation_date D(4)`, `recurrence_end_date D(18)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(4), D(11), D(18)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(25)`.
4. re-read T: `next_generation_date == D(25)`.
5. count: drafts(T) `== [(D(4), M1.id), (D(11), M1.id), (D(18), M1.id)]`.

### WTMG-AR-05 — monthly on the 31st: capped to each month's last day
- **Rules:** anchored R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(31), `next_generation_date date(2026, 1, 31)`, `recurrence_end_date date(2026, 4, 30)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == date(2026, 5, 31)`.
4. re-read T: `next_generation_date == date(2026, 5, 31)`.
5. count: drafts(T) `== [(date(2026, 1, 31), M1.id), (date(2026, 2, 28), M1.id), (date(2026, 3, 31), M1.id), (date(2026, 4, 30), M1.id)]`.

### WTMG-AR-06 — monthly on the 29th in a leap year includes 29 February
- **Rules:** anchored R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(29), `next_generation_date date(2028, 1, 29)`, `recurrence_end_date date(2028, 3, 29)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [date(2028, 1, 29), date(2028, 2, 29), date(2028, 3, 29)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == date(2028, 4, 29)`.
4. re-read T: `next_generation_date == date(2028, 4, 29)`.
5. count: drafts(T) `== [(date(2028, 1, 29), M1.id), (date(2028, 2, 29), M1.id), (date(2028, 3, 29), M1.id)]`.

### WTMG-AR-07 — monthly on the 31st in a leap year: 29 February, then back to the 31st
- **Rules:** anchored R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(31), `next_generation_date date(2028, 1, 31)`, `recurrence_end_date date(2028, 2, 29)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [date(2028, 1, 31), date(2028, 2, 29)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == date(2028, 3, 31)`.
4. re-read T: `next_generation_date == date(2028, 3, 31)`.
5. count: drafts(T) `== [(date(2028, 1, 31), M1.id), (date(2028, 2, 29), M1.id)]`.

### WTMG-AR-08 — daily across the year end
- **Rules:** anchored R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date date(2026, 12, 30)`, `recurrence_end_date date(2027, 1, 1)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [date(2026, 12, 30), date(2026, 12, 31), date(2027, 1, 1)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == date(2027, 1, 2)`.
4. re-read T: `next_generation_date == date(2027, 1, 2)`.
5. count: drafts(T) `== [(date(2026, 12, 30), M1.id), (date(2026, 12, 31), M1.id), (date(2027, 1, 1), M1.id)]`.

### WTMG-AR-09 — a next date equal to the end gives exactly one draft
- **Rules:** anchored R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(4)`, `recurrence_end_date D(4)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. re-read T: `next_generation_date == D(5)`.
5. count: drafts(T) `== [(D(4), M1.id)]`.

### WTMG-AR-10 — a non-recurring template gives nothing and is not changed
- **Rules:** anchored R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `recurrence_type "daily"`, `next_generation_date D(2)`, `recurrence_end_date D(4)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result == []`.
2. session: `not db.new`.
3. unchanged: unchanged(T).
4. count: drafts(T) `== []`.

### WTMG-AR-11 — a template with no end date gives nothing and is not changed
- **Rules:** anchored R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result == []`.
2. session: `not db.new`.
3. unchanged: unchanged(T).
4. count: drafts(T) `== []`.

### WTMG-AR-12 — a template never anchored (no next date) gives nothing
- **Rules:** anchored R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `recurrence_end_date D(4)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result == []`.
2. session: `not db.new`.
3. unchanged: unchanged(T).
4. count: drafts(T) `== []`.

### WTMG-AR-13 — a next date after the end gives nothing and is not moved
- **Rules:** anchored R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(5)`, `recurrence_end_date D(4)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result == []`.
2. session: `not db.new`.
3. unchanged: unchanged(T).
4. count: drafts(T) `== []`.

### WTMG-AR-14 — an open order of any source on the machine, day and type blocks that date only
- **Rules:** anchored R2; Facts (open order)
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.
2. O = order O(M1, D(3)).

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. re-read T: `next_generation_date == D(5)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(4), M1.id)]`.
6. unchanged: unchanged(O).

### WTMG-AR-15 — a COMPLETED order also blocks its date
- **Rules:** anchored R2; Facts (open order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.
2. O = order O(M1, D(3)), but `status "COMPLETED"`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. re-read T: `next_generation_date == D(5)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(4), M1.id)]`.
6. unchanged: unchanged(O).

### WTMG-AR-16 — a VOIDED order does not block
- **Rules:** anchored R2; Facts (open order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.
2. O = order O(M1, D(3)), but `status "VOIDED"`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(3), D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. re-read T: `next_generation_date == D(5)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(3), M1.id), (D(4), M1.id)]`.
6. unchanged: unchanged(O).

### WTMG-AR-17 — a soft-deleted order does not block
- **Rules:** anchored R2; Facts (open order)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.
2. O = order O(M1, D(3)), but `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(3), D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. re-read T: `next_generation_date == D(5)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(3), M1.id), (D(4), M1.id)]`.
6. unchanged: unchanged(O).

### WTMG-AR-18 — an order of another type does not block
- **Rules:** anchored R2; Facts (open order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.
2. O = order O(M1, D(3)), but `work_order_type_id WT2.id`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(3), D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. re-read T: `next_generation_date == D(5)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(3), M1.id), (D(4), M1.id)]`.
6. unchanged: unchanged(O).

### WTMG-AR-19 — an order on another machine does not block
- **Rules:** anchored R2; Facts (open order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.
2. O = order O(M2, D(3)).

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2), D(3), D(4)]`.
2. returns: `{o.machine_id for o in result} == {M1.id}`.
3. returns: `T.next_generation_date == D(5)`.
4. re-read T: `next_generation_date == D(5)`.
5. count: drafts(T) `== [(D(2), M1.id), (D(3), M1.id), (D(4), M1.id)]`.
6. unchanged: unchanged(O).

### WTMG-AR-20 — an inactive template is refused on the first draft, nothing made
- **Rules:** anchored R4 (the date stays, spec G11)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`, `is_active False`.

**When**
- `M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "Template is inactive"`.
3. returns: on the passed object, before any re-read: `T.next_generation_date == D(2)`.
4. count: drafts(T) `== []`.

### WTMG-AR-21 — a machine of another workspace: the 404 reaches the caller, nothing made
- **Rules:** anchored R5 (the date stays at the failing date)
- **Kind:** error
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.

**When**
- `M.generate_drafts_for_anchored_range(db, template=T, machine_id=M9.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 404`.
2. raises: `exc.value.detail == f"Machine with ID {M9.id} not found"`.
3. returns: on the passed object, before any re-read: `T.next_generation_date == D(2)`.
4. count: drafts(T) `== []`.

### WTMG-AR-22 — the template row is locked before the dates are read
- **Rules:** anchored R6 [BUG-2343]
- **Kind:** bug
- **Expect:** xfail BUG-2343
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(2)`.
2. statement recorder.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `[o.planned_date for o in result] == [D(2)]`.
2. statement: `len(locks) >= 1`.

### WTMG-AR-23 — the span is not limited: 184 daily dates give 184 drafts
- **Rules:** anchored R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date date(2026, 1, 1)`, `recurrence_end_date date(2026, 7, 3)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `len(result) == 184`.
2. returns: `T.next_generation_date == date(2026, 7, 4)`.
3. re-read T: `next_generation_date == date(2026, 7, 4)`.
4. count: `len(drafts(T)) == 184`.

### WTMG-AR-24 — anchored generation flushes and never commits
- **Rules:** anchored R3, Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(3)`.

**When**
- `result = M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`, rolled back.

**Then**
1. returns: `len(result) == 2` (inside).
2. count: `work_orders` with `work_order_template_id == T.id` has exactly 2 rows (inside).
3. mock called: `cm.call_count == 0`.
4. count: `work_orders` with `work_order_template_id == T.id` has exactly 0 rows (after the savepoint rollback).

### WTMG-AR-25 — a failure on a later date keeps the drafts already made; the date stays at the failing date
- **Rules:** anchored R5 (spec G10)
- **Kind:** error
- **Expect:** pass
- **Author:** claude

**Given**
1. T = template, but daily, `next_generation_date D(2)`, `recurrence_end_date D(4)`.
2. `real = wom.create_work_order_from_template`, taken before patching; `calls = []`; `f(*a, **k)` appends to `calls`, returns `real(*a, **k)` on the first call and raises `HTTPException(status_code=400, detail="boom")` on the second. `patch.object(wom, "create_work_order_from_template", side_effect=f)` around the When.

**When**
- `M.generate_drafts_for_anchored_range(db, template=T, machine_id=M1.id, workspace_id=W1.id, user_id=U1.id)`, inside `with pytest.raises(HTTPException) as exc:`.

**Then**
1. raises: `exc.value.detail == "boom"`.
2. mock called: `len(calls) == 2`.
3. returns: on the passed object, before any re-read: `T.next_generation_date == D(3)`.
4. count: after `db.flush()`, drafts(T) `== [(D(2), M1.id)]`.

## `WorkOrderTemplateManager.generate_drafts`

> A section run over a recurring template of that section that is not due (BUG-2345) is covered in section Q19, and a late run (R10, intended) in section Q20. Every due template here has `next_generation_date == target_date`, where stepping from either date gives the same result. Lists come back in no stated order: compare with pairs(result).

### WTMG-GD-01 — a template due on the day gets one draft on its machine and moves one week
- **Rules:** `generate_drafts` R1, R6, R7, R9, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `pairs(result) == [(D(16), M1.id)]`.
3. session: `not db.new`.
4. re-read T: `next_generation_date == D(23)`.
5. re-read result[0]: `status == "DRAFT"`, `work_order_template_id == T.id`, `work_order_type_id == WT1.id`, `workspace_id == W1.id`.

### WTMG-GD-02 — a template due tomorrow gets nothing and is not moved (unscoped run)
- **Rules:** `generate_drafts` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(17)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. count: drafts(T) `== []`.

### WTMG-GD-03 — a recurring template never anchored gets nothing
- **Rules:** `generate_drafts` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. count: drafts(T) `== []`.

### WTMG-GD-04 — an end date equal to the day still gives a draft, and the date moves past the end
- **Rules:** `generate_drafts` R1, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`, `recurrence_end_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. re-read T: `next_generation_date == D(23)`.

### WTMG-GD-05 — an end date the day before gives nothing
- **Rules:** `generate_drafts` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`, `recurrence_end_date D(15)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. count: drafts(T) `== []`.

### WTMG-GD-06 — an inactive due template gets nothing
- **Rules:** `generate_drafts` R1; `delete_template` R4
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`, `is_active False`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. count: drafts(T) `== []`.

### WTMG-GD-07 — without a section, a non-recurring template gets nothing, even with a machine and a date
- **Rules:** `generate_drafts` R2, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. count: drafts(T) `== []`.

### WTMG-GD-08 — due templates of W0 and W2 get nothing in a run for W1
- **Rules:** `generate_drafts` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Z0 = template, but `workspace_id W0.id`, `work_order_type_id WT0.id`, weekly, `default_machine_id M0.id`, `next_generation_date D(16)`.
2. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
3. Z9 = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`, weekly, `default_machine_id M9.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. unchanged: unchanged(Z0).
3. unchanged: unchanged(Z9).
4. count: drafts(Z0) `== []`.
5. count: drafts(Z9) `== []`.

### WTMG-GD-09 — a workspace with no templates gives an empty list
- **Rules:** `generate_drafts` R1, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists in W1.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. count: `work_orders` has exactly 0 rows.

### WTMG-GD-10 — daily: the next date is the next day
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. re-read T: `next_generation_date == D(17)`.

### WTMG-GD-11 — weekly with no day: the next date is 7 days later
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `is_recurring True`, `recurrence_type "weekly"`, `default_machine_id M1.id`, `next_generation_date D(18)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(18))`.

**Then**
1. returns: `pairs(result) == [(D(18), M1.id)]`.
2. re-read T: `next_generation_date == D(25)`.

### WTMG-GD-12 — weekly on Fridays run on a Monday: the next date is that Friday
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `is_recurring True`, `recurrence_type "weekly"`, `recurrence_day 4`, `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. re-read T: `next_generation_date == D(20)`.

### WTMG-GD-13 — monthly on the 31st from 31 January: 28 February
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(31), `default_machine_id M1.id`, `next_generation_date date(2026, 1, 31)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2026, 1, 31))`.

**Then**
1. returns: `pairs(result) == [(date(2026, 1, 31), M1.id)]`.
2. re-read T: `next_generation_date == date(2026, 2, 28)`.

### WTMG-GD-14 — monthly on the 31st from 31 March: 30 April
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(31), `default_machine_id M1.id`, `next_generation_date date(2026, 3, 31)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2026, 3, 31))`.

**Then**
1. returns: `pairs(result) == [(date(2026, 3, 31), M1.id)]`.
2. re-read T: `next_generation_date == date(2026, 4, 30)`.

### WTMG-GD-15 — monthly in December: January of the next year
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(15), `default_machine_id M1.id`, `next_generation_date date(2026, 12, 15)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2026, 12, 15))`.

**Then**
1. returns: `pairs(result) == [(date(2026, 12, 15), M1.id)]`.
2. re-read T: `next_generation_date == date(2027, 1, 15)`.

### WTMG-GD-16 — daily on 31 December: 1 January
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `default_machine_id M1.id`, `next_generation_date date(2026, 12, 31)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2026, 12, 31))`.

**Then**
1. returns: `pairs(result) == [(date(2026, 12, 31), M1.id)]`.
2. re-read T: `next_generation_date == date(2027, 1, 1)`.

### WTMG-GD-17 — monthly on the 29th in a leap year: 29 February
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(29), `default_machine_id M1.id`, `next_generation_date date(2028, 1, 29)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2028, 1, 29))`.

**Then**
1. returns: `pairs(result) == [(date(2028, 1, 29), M1.id)]`.
2. re-read T: `next_generation_date == date(2028, 2, 29)`.

### WTMG-GD-18 — monthly on the 31st in a leap year: 29 February
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(31), `default_machine_id M1.id`, `next_generation_date date(2028, 1, 31)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2028, 1, 31))`.

**Then**
1. returns: `pairs(result) == [(date(2028, 1, 31), M1.id)]`.
2. re-read T: `next_generation_date == date(2028, 2, 29)`.

### WTMG-GD-19 — monthly on the 29th in a common year: 28 February
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(29), `default_machine_id M1.id`, `next_generation_date date(2027, 1, 29)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2027, 1, 29))`.

**Then**
1. returns: `pairs(result) == [(date(2027, 1, 29), M1.id)]`.
2. re-read T: `next_generation_date == date(2027, 2, 28)`.

### WTMG-GD-20 — monthly with no day from 31 January: 28 February, the day stays empty
- **Rules:** `generate_drafts` R7, R9; recurrence `advance_next_generation_date`
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `is_recurring True`, `recurrence_type "monthly"`, `default_machine_id M1.id`, `next_generation_date date(2026, 1, 31)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=date(2026, 1, 31))`.

**Then**
1. returns: `pairs(result) == [(date(2026, 1, 31), M1.id)]`.
2. re-read T: `next_generation_date == date(2026, 2, 28)`.
3. re-read T: `recurrence_day is None`.

### WTMG-GD-21 — a template of a section with no default machine: one draft per machine of the section
- **Rules:** `generate_drafts` R6, R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.
2. re-read T: `next_generation_date == D(23)`.

### WTMG-GD-22 — no machine at all: no draft, but the date still moves
- **Rules:** `generate_drafts` R6, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. re-read T: `next_generation_date == D(23)`.
3. count: drafts(T) `== []`.

### WTMG-GD-23 — a factory run: a template with no section and no machine gets the factory's machines
- **Rules:** `generate_drafts` R6
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_id=F1.id)`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.
2. re-read T: `next_generation_date == D(23)`.

### WTMG-GD-24 — a factory run leaves out a due template whose section is in another factory
- **Rules:** `generate_drafts` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.
2. V = template, but weekly, `default_factory_section_id S3.id`, `next_generation_date D(16)`, `template_name "Boiler check"`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_id=F1.id)`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.
2. unchanged: unchanged(V).
3. count: drafts(V) `== []`.

### WTMG-GD-25 — a section run: a due recurring template of the section is handled once
- **Rules:** `generate_drafts` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.
2. re-read T: `next_generation_date == D(23)`.
3. count: `len(drafts(T)) == 2`.

### WTMG-GD-26 — an open order on the machine, day and type: no draft, the date still moves
- **Rules:** `generate_drafts` R7, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. O = order O(M1, D(16)).

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. re-read T: `next_generation_date == D(23)`.
3. count: drafts(T) `== []`.
4. unchanged: unchanged(O).

### WTMG-GD-27 — a VOIDED order does not block
- **Rules:** `generate_drafts` R7; Facts (open order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. O = order O(M1, D(16)), but `status "VOIDED"`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. unchanged: unchanged(O).

### WTMG-GD-28 — a soft-deleted order does not block
- **Rules:** `generate_drafts` R7; Facts (open order)
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. O = order O(M1, D(16)), but `is_deleted True`, `is_active False`, `deleted_at T0`, `deleted_by U1.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. unchanged: unchanged(O).

### WTMG-GD-29 — an order of another type does not block
- **Rules:** `generate_drafts` R7; Facts (open order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. O = order O(M1, D(16)), but `work_order_type_id WT2.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. unchanged: unchanged(O).

### WTMG-GD-30 — a COMPLETED order blocks
- **Rules:** `generate_drafts` R7; Facts (open order)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. O = order O(M1, D(16)), but `status "COMPLETED"`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. count: drafts(T) `== []`.
3. re-read T: `next_generation_date == D(23)`.

### WTMG-GD-31 — an order on another day does not block
- **Rules:** `generate_drafts` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. O = order O(M1, D(15)).

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. unchanged: unchanged(O).

### WTMG-GD-32 — an order on another machine does not block
- **Rules:** `generate_drafts` R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. O = order O(M2, D(16)).

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. unchanged: unchanged(O).

### WTMG-GD-33 — a section template: the machine with an order is skipped, the other gets its draft
- **Rules:** `generate_drafts` R7, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`.
2. O = order O(M1, D(16)).

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M2.id)]`.
2. re-read T: `next_generation_date == D(23)`.

### WTMG-GD-34 — a section run: a non-recurring template of the section gets drafts and its dates do not change
- **Rules:** `generate_drafts` R1, R8
- **Kind:** happy
- **Expect:** pass

**Given**
1. N = template, but `default_factory_section_id S1.id`, `next_generation_date D(10)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.
2. re-read N: `next_generation_date == D(10)`.
3. count: `len(drafts(N)) == 2`.

### WTMG-GD-35 — a section run: a non-recurring template of another section gets nothing
- **Rules:** `generate_drafts` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N = template, but `default_factory_section_id S3.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == []`.
2. count: drafts(N) `== []`.

### WTMG-GD-36 — a section run: a non-recurring template with no section gets nothing
- **Rules:** `generate_drafts` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. N = template, but `default_machine_id M1.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == []`.
2. count: drafts(N) `== []`.

### WTMG-GD-37 — a section run: an inactive non-recurring template of the section gets nothing
- **Rules:** `generate_drafts` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. N = template, but `default_factory_section_id S1.id`, `is_active False`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == []`.
2. count: drafts(N) `== []`.

### WTMG-GD-38 — an unscoped run: a non-recurring template with a section gets nothing
- **Rules:** `generate_drafts` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = template, but `default_factory_section_id S1.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == []`.
2. count: drafts(N) `== []`.

### WTMG-GD-39 — a section run: a recurring template of the section whose program ended is skipped
- **Rules:** `generate_drafts` R5 (after BUG-2345 a guard no input reaches; the outcome is the same either way)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`, `recurrence_end_date D(15)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. count: drafts(T) `== []`.

### WTMG-GD-40 — a section run finds the section's oldest template behind 999 newer active ones
- **Rules:** `generate_drafts` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. N = template, but `template_name "Packing check"`, `default_factory_section_id S1.id`, `created_at datetime(2026, 2, 1, 9, 0, 0)`.
2. E1 … E999, built with `add_all`: Ek = template, but `created_at datetime(2026, 3, 1, 9, 0, 0) + timedelta(minutes=k)`, `template_name f"Check {k}"` (`timedelta` from `datetime`; no section, no machine).

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.

### WTMG-GD-41 — a section run finds the section's oldest template behind 1000 newer active ones
- **Rules:** `generate_drafts` R3 [BUG-2342]
- **Kind:** bug
- **Expect:** xfail BUG-2342
- **Fails today on:** Then 1 (N is cut off by the 1000 cap: no draft)

**Given**
1. N = template, but `template_name "Packing check"`, `default_factory_section_id S1.id`, `created_at datetime(2026, 2, 1, 9, 0, 0)`.
2. E1 … E1000, built with `add_all`: Ek = template, but `created_at datetime(2026, 3, 1, 9, 0, 0) + timedelta(minutes=k)`, `template_name f"Check {k}"` (`timedelta` from `datetime`; no section, no machine).

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.

### WTMG-GD-42 — unscoped run: the template row is locked before its checks
- **Rules:** `generate_drafts` R11 [BUG-2343]
- **Kind:** bug
- **Expect:** xfail BUG-2343
- **Fails today on:** Then 2 (no `FOR UPDATE` is sent)

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. statement recorder.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. statement: `len(locks) >= 1`.

### WTMG-GD-43 — one template's failure is logged and skipped, the other's draft is kept
- **Rules:** `generate_drafts` R12 [BUG-2344]
- **Kind:** bug
- **Expect:** xfail BUG-2344
- **Fails today on:** Then 1 (the call raises RuntimeError: the error leaves the loop)
- **Author:** claude

**Given**
1. T1 = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. T2 = template, but weekly, `default_machine_id M2.id`, `next_generation_date D(16)`, `template_name "Belt check"`.
3. `real = wom.create_work_order_from_template`, taken before patching; `patch.object(wom, "create_work_order_from_template", side_effect=f)` around the When, where `f(*a, **k)` raises `RuntimeError("boom")` when its `template_id` (keyword, else the second positional) `== T1.id` and otherwise returns `real(*a, **k)`. `caplog` at WARNING.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M2.id)]`.
2. count: drafts(T1) `== []`.
3. re-read T1: `next_generation_date == D(16)`.
4. re-read T2: `next_generation_date == D(23)`.
5. log: a WARNING record whose message contains `str(T1.id)` and `"boom"`.

### WTMG-GD-44 — a section of another workspace selects nothing and is not refused, not even that workspace's own template
- **Rules:** `generate_drafts` R13, R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. V = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`, `template_name "Packing check"`.
3. Z9 = template, but `workspace_id W2.id`, `work_order_type_id WT9.id`, `default_factory_section_id S9.id`, `default_machine_id M9.id`, `template_name "Nine check"` (non-recurring).

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S9.id)`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. unchanged: unchanged(V).
4. unchanged: unchanged(Z9).
5. count: drafts(Z9) `== []`.

### WTMG-GD-45 — an unknown section selects nothing and is not refused
- **Rules:** `generate_drafts` R13
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.
2. V = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`, `template_name "Packing check"`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=MISSING)`.

**Then**
1. returns: `pairs(result) == []`.
2. unchanged: unchanged(T).
3. unchanged: unchanged(V).

### WTMG-GD-46 — a factory of another workspace: a template with no section or machine finds no machine, its date still moves
- **Rules:** `generate_drafts` R13, R9
- **Kind:** isolation
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_id=F9.id)`.

**Then**
1. returns: `pairs(result) == []`.
2. re-read T: `next_generation_date == D(23)`.
3. count: drafts(T) `== []`.

### WTMG-GD-47 — an unknown factory: the same, not refused
- **Rules:** `generate_drafts` R13, R9
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_id=MISSING)`.

**Then**
1. returns: `pairs(result) == []`.
2. re-read T: `next_generation_date == D(23)`.
3. count: drafts(T) `== []`.

### WTMG-GD-48 — generate_drafts flushes and never commits
- **Rules:** `generate_drafts` Side effects
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`, rolled back.

**Then**
1. returns: `len(result) == 1` (inside).
2. count: `work_orders` with `work_order_template_id == T.id` has exactly 1 row (inside).
3. mock called: `cm.call_count == 0`.
4. count: `work_orders` with `work_order_template_id == T.id` has exactly 0 rows (after the savepoint rollback).

### WTMG-GD-49 — a draft carries the template's account and cost
- **Rules:** `generate_drafts` R7 (spec Facts, G13)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`, `account_id A1.id`, `cost Decimal("12.50")`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. re-read result[0]: `account_id == A1.id`, `cost == Decimal("12.50")`, `priority == "MEDIUM"`.
3. re-read result[0]: `created_by == U1.id`, `uses_inventory is False`.

## Answered by the owner — OQ-19 → BUG-2345 (`generate_drafts` R1, R4)

> The owner answered on 2026-11-07: in a section run a recurring template gets a draft only when it is due. The four cards of revision 1 now state that and are strict xfail BUG-2345. Q19-05 and Q19-06 hold today and after the fix. No other card gives a section run a recurring template of that section that is not due.

### WTMG-Q19-01 — a recurring template of the section due in six days gets no draft; its date stays
- **Rules:** `generate_drafts` R4 [BUG-2345]
- **Kind:** bug
- **Expect:** xfail BUG-2345
- **Fails today on:** Then 2 (today the section run makes drafts on M1 and M2)

**Given**
1. V = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(10), factory_section_id=S1.id)`.

**Then**
1. re-read V: `next_generation_date == D(16)`.
2. returns: `pairs(result) == []`.
3. count: drafts(V) `== []`.

### WTMG-Q19-02 — with a default machine, the not-due template gets no draft
- **Rules:** `generate_drafts` R4 [BUG-2345]
- **Kind:** bug
- **Expect:** xfail BUG-2345
- **Fails today on:** Then 2 (today one draft is made on M1)

**Given**
1. V = template, but weekly, `default_factory_section_id S1.id`, `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(10), factory_section_id=S1.id)`.

**Then**
1. re-read V: `next_generation_date == D(16)`.
2. returns: `pairs(result) == []`.
3. count: drafts(V) `== []`.

### WTMG-Q19-03 — a recurring template of the section never anchored gets no draft; its date stays empty
- **Rules:** `generate_drafts` R4 [BUG-2345]
- **Kind:** bug
- **Expect:** xfail BUG-2345
- **Fails today on:** Then 2 (today the section run makes drafts on M1 and M2)

**Given**
1. V = template, but weekly, `default_factory_section_id S1.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(10), factory_section_id=S1.id)`.

**Then**
1. re-read V: `next_generation_date is None`.
2. returns: `pairs(result) == []`.
3. count: drafts(V) `== []`.

### WTMG-Q19-04 — planning the section again the next day gives no more drafts
- **Rules:** `generate_drafts` R4 [BUG-2345]
- **Kind:** bug
- **Expect:** xfail BUG-2345
- **Fails today on:** Then 2 (today two more drafts are made for 11 March)

**Given**
1. V = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`.
2. A = order A(M1, D(10)), but `work_order_template_id V.id`.
3. B = order B(M2, D(10)), but `work_order_template_id V.id`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(11), factory_section_id=S1.id)`.

**Then**
1. re-read V: `next_generation_date == D(16)`.
2. returns: `pairs(result) == []`.
3. count: `len(drafts(V)) == 2`.

### WTMG-Q19-05 — a section run before the due date leaves the template's date alone
- **Rules:** `generate_drafts` R4, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. V = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`, `recurrence_end_date D(30)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(10), factory_section_id=S1.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. re-read V: `next_generation_date == D(16)`, `recurrence_end_date == D(30)`.

### WTMG-Q19-06 — on its due day a recurring template of the section gets one draft per machine, once, and moves
- **Rules:** `generate_drafts` R1, R4, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. V = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id), (D(16), M2.id)]`.
2. count: drafts(V) `== [(D(16), M1.id), (D(16), M2.id)]`.
3. re-read V: `next_generation_date == D(23)`.

### WTMG-Q19-07 — a recurring template of the section due tomorrow gets no draft; its date stays
- **Rules:** `generate_drafts` R4 [BUG-2345]
- **Kind:** bug
- **Expect:** xfail BUG-2345
- **Fails today on:** Then 2 (today the section run makes drafts on M1 and M2)

**Given**
1. V = template, but weekly, `default_factory_section_id S1.id`, `next_generation_date D(17)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16), factory_section_id=S1.id)`.

**Then**
1. re-read V: `next_generation_date == D(17)`.
2. returns: `pairs(result) == []`.
3. count: drafts(V) `== []`.

## Answered by the owner — OQ-20 ✅ intended (`generate_drafts` R10)

> The owner answered on 2026-11-07: intended. A late run plans the day asked for, missed dates are skipped, and the next date steps from the run's day. These are ordinary passing cards. Outside this section every due template has `next_generation_date == target_date`.

### WTMG-Q20-01 — weekly due 16 March, run 30 March: one draft for the 30th, next date 6 April
- **Rules:** `generate_drafts` R10 ✅ (owner, OQ-20)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(30))`.

**Then**
1. returns: `pairs(result) == [(D(30), M1.id)]`.
2. count: drafts(T) `== [(D(30), M1.id)]`.
3. re-read T: `next_generation_date == date(2026, 4, 6)`.

### WTMG-Q20-02 — daily due 10 March, run 16 March: one draft, next date 17 March
- **Rules:** `generate_drafts` R10 ✅ (owner, OQ-20)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but daily, `default_machine_id M1.id`, `next_generation_date D(10)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(16))`.

**Then**
1. returns: `pairs(result) == [(D(16), M1.id)]`.
2. count: drafts(T) `== [(D(16), M1.id)]`.
3. re-read T: `next_generation_date == D(17)`.

### WTMG-Q20-03 — monthly on the 15th due 15 January, run 20 March: next date 15 April
- **Rules:** `generate_drafts` R10 ✅ (owner, OQ-20)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but monthly(15), `default_machine_id M1.id`, `next_generation_date date(2026, 1, 15)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(20))`.

**Then**
1. returns: `pairs(result) == [(D(20), M1.id)]`.
2. re-read T: `next_generation_date == date(2026, 4, 15)`.

### WTMG-Q20-04 — weekly due Monday 16 March, run Wednesday 18 March: next date Monday 23 March
- **Rules:** `generate_drafts` R10 ✅ (owner, OQ-20)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but weekly, `default_machine_id M1.id`, `next_generation_date D(16)`.

**When**
- `result = M.generate_drafts(db, workspace_id=W1.id, user_id=U1.id, target_date=D(18))`.

**Then**
1. returns: `pairs(result) == [(D(18), M1.id)]`.
2. re-read T: `next_generation_date == D(23)`.

## Answered by the owner — OQ-21 → BUG-2346 (`create_template` R6, `update_template` R9)

> The owner answered on 2026-11-07: a template that requires approval must have at least one approver. Create and update refuse otherwise with 400, and nothing is saved. Update checks only when it sends `requires_approval` or `approver_user_ids`. Q21-01, Q21-02, Q21-04, Q21-05 and Q21-12 are strict xfail BUG-2346. Q21-08 is strict xfail BUG-2335, the approver refusal that comes first. Q21-03, Q21-07, Q21-09, Q21-10, Q21-11 and Q21-13 hold today and after the fix. Q21-06 is retired (see Retired IDs).

### WTMG-Q21-01 — create: requires approval with no approvers given is refused, nothing written
- **Rules:** `create_template` R6 [BUG-2346], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-2346
- **Fails today on:** Then 1 (no error: the template is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=WT1.id, requires_approval=True), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == 'Choose at least one approver, or turn off "requires approval"'`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-Q21-02 — create: requires approval with an empty approver list is refused, nothing written
- **Rules:** `create_template` R6 [BUG-2346], Errors row 5
- **Kind:** bug
- **Expect:** xfail BUG-2346
- **Fails today on:** Then 1 (no error: the template is stored)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=WT1.id, requires_approval=True, uses_inventory=True, items=[IC(item_id=I1.id)], approver_user_ids=[]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == 'Choose at least one approver, or turn off "requires approval"'`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-Q21-03 — create: approvers given without requires approval are stored
- **Rules:** `create_template` R6a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=WT1.id, requires_approval=False, approver_user_ids=[U1.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `requires_approval is False`.
3. count: approvers(result) `== [U1.id]`.

### WTMG-Q21-04 — update: removing every approver while requires approval stays true is refused
- **Rules:** `update_template` R9 [BUG-2346]
- **Kind:** bug
- **Expect:** xfail BUG-2346
- **Fails today on:** Then 1 (no error: the approvers are removed)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == 'Choose at least one approver, or turn off "requires approval"'`.
3. session: `not db.new`.
4. session: `not db.deleted`.
5. unchanged: unchanged(T).
6. count: approvers(T) `== [U1.id]`.

### WTMG-Q21-05 — update: turning requires approval on with no approvers is refused
- **Rules:** `update_template` R9 [BUG-2346]
- **Kind:** bug
- **Expect:** xfail BUG-2346
- **Fails today on:** Then 1 (no error: the flag is stored)

**Given**
1. T = template.

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(requires_approval=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == 'Choose at least one approver, or turn off "requires approval"'`.
3. session: `not db.dirty`.
4. unchanged: unchanged(T).
5. re-read T: `requires_approval is False`, `updated_by is None`.

### WTMG-Q21-07 — an old template that requires approval with no approvers can still be renamed
- **Rules:** `update_template` R9 (a request sending neither field is not checked)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True` (stored before the fix; no approver rows).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(template_name="Boiler check", notes="Yearly"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `template_name == "Boiler check"`, `notes == "Yearly"`, `requires_approval is True`.
3. count: approvers(T) `== []`.

### WTMG-Q21-08 — create: requires approval with only a suspended approver gets the approver refusal first
- **Rules:** `create_template` R5 [BUG-2335], R10; R6
- **Kind:** bug
- **Expect:** xfail BUG-2335
- **Fails today on:** Then 1 (no error: U4 is left out and the template is stored with no approver)

**Given**
1. No template exists.

**When**
- `M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=WT1.id, requires_approval=True, approver_user_ids=[U4.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == "User is not an active member of this workspace"`.
3. session: `not db.new`.
4. nothing written: nothing written.

### WTMG-Q21-09 — create: requires approval with one active approver is accepted
- **Rules:** `create_template` R6, R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No template exists.

**When**
- `result = M.create_template(db, data=TC(template_name="Boiler shutdown", work_order_type_id=WT1.id, requires_approval=True, approver_user_ids=[U2.id]), workspace_id=W1.id, user_id=U1.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the new template: `requires_approval is True`.
3. count: approvers(result) `== [U2.id]`.

### WTMG-Q21-10 — update: turning requires approval on counts a stored approver who has since been suspended
- **Rules:** `update_template` R9 (stored approvers count whatever their membership is now)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.
2. approver(T, U4).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(requires_approval=True), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `requires_approval is True`.
3. count: approvers(T) `== [U4.id]`.

### WTMG-Q21-11 — update: turning requires approval off and removing every approver together is accepted
- **Rules:** `update_template` R9, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(requires_approval=False, approver_user_ids=[]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `requires_approval is False`.
3. count: approvers(T) `== []`.

### WTMG-Q21-12 — update: approvers sent as null on a template that requires approval is refused
- **Rules:** `update_template` R9 [BUG-2346], R8
- **Kind:** bug
- **Expect:** xfail BUG-2346
- **Fails today on:** Then 1 (no error: the approvers are removed)

**Given**
1. T = template, but `requires_approval True`.
2. approver(T, U1).

**When**
- `M.update_template(db, tpl_id=T.id, data=TU(approver_user_ids=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`, `exc.value.status_code == 400`.
2. raises: `exc.value.detail == 'Choose at least one approver, or turn off "requires approval"'`.
3. session: `not db.deleted`.
4. count: approvers(T) `== [U1.id]`.

### WTMG-Q21-13 — update: turning requires approval on together with one active approver is accepted
- **Rules:** `update_template` R9, R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. T = template.

**When**
- `result = M.update_template(db, tpl_id=T.id, data=TU(requires_approval=True, approver_user_ids=[U2.id]), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == T.id`.
2. re-read T: `requires_approval is True`.
3. count: approvers(T) `== [U2.id]`.

## Retired IDs
- WTMG-Q21-06 — "a draft from a template that requires approval but has no approvers is approved at once". What such an order carries is now `WorkOrderManager`'s FU-1 (a), still to be decided there. With BUG-2346 the template can no longer be made through this manager. Moved to Deferred.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `create_template` R7 / `update_template` R7 — schema-level recurrence checks (BUG-360 type whitelist, BUG-361 recurring without type, BUG-362 day range on create) | `tests/unit/utils/work_order_recurrence.cases.md` (schema cards) | Already there. The update-side merged-state checks and R8a, which that file defers here, are WTMG-UT-45 … UT-60 and WTMG-CT-42 … CT-45. |
| anchored R3 — an unrecognised `recurrence_type` steps daily today (BUG-360) | `work_order_recurrence` (`advance_next_generation_date` R11) | The helper raises `ValueError` once fixed; no stored template can reach it after the schema fix. |
| `generate_drafts` R6 — which machines a template reaches (BUG-340 … BUG-343) | `tests/unit/utils/work_order_generation.cases.md` | Default machine, section and factory sources, deleted and foreign machines, run scope. |
| What a draft carries (type, priority, account, cost, lines when `uses_inventory`, approvers when `requires_approval`), `Template is inactive`, FU-1 (a) (b) (c) | `WorkOrderManager.create_work_order_from_template` (no spec yet) | Here only status, template, type, workspace, machine and date are checked. |
| `list_templates` order and paging (BUG-2330); `get_approvers` order (BUG-2331); deleted section in a factory run (BUG-2332); `created_at` clock (BUG-2333) | `tests/unit/dao/work_order_template.spec.md` | DAO rules; the manager cards use distinct `created_at` values and set checks. |
| Commit, rollback and refresh around every writer; `POST /generate-drafts/` declared before `GET /{tpl_id}/`; `1 <= limit <= 1000` | `WorkOrderTemplateService` / `app/api/v1/endpoints/work_order_templates.py` | Service transaction contract and endpoint rules. |
| FU-2 — a removed member stays a template's default approver | `WorkspaceManager.remove_member_from_workspace` | Precedents BUG-1201 / BUG-1883. |
| Permission checks (none today) | `docs/future/permissions.md` | Any active member may do everything here. |
| FU-1 (a) — an order made from a template that requires approval but has no active approver left (retired WTMG-Q21-06) | `WorkOrderManager.create_work_order_from_template` (no spec yet) | Whether it is approved at once; the owner's OQ-21 answer suggests not. |

## Spec gaps
None open. Gaps 1–13 of revision 1 are closed by the spec's Gap log (2026-11-07):
- **G1** model modules (Conventions).
- **G2** 404 words and check order (14 detail lines; CT-50 … CT-54).
- **G3** schema `ValidationError` versus the manager's 422 details (UT-45 … UT-55).
- **G4** lock check by recorded SQL (unchanged).
- **G5** `assigned_to` and priority values (CT-49, UT-77).
- **G6** patch target `wom` (GD-43, AR-25).
- **G7** BUG-2350 (17 cards).
- **G8** approver refusal before any write (CT-34, UT-78).
- **G9** a REPLACE line keeps its item (UI-07, UI-24).
- **G10** two-call patch (AR-25).
- **G11** date stays when the first draft fails (AR-20).
- **G12** `work_order_items` columns (RI-07).
- **G13** draft columns (GD-49).

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_replace_approvers` | R1 | WTMG-RA-01, WTMG-RA-04, WTMG-RA-05 |
| `_replace_approvers` | R2 | WTMG-RA-02 |
| `_replace_approvers` | R3 [BUG-2335] | WTMG-RA-06, WTMG-RA-07, WTMG-RA-08, WTMG-RA-09, WTMG-RA-10, WTMG-RA-11, WTMG-RA-12 |
| `_replace_approvers` | R4 | WTMG-RA-03 |
| `_replace_approvers` | R5 | WTMG-RA-01 |
| `_replace_approvers` | Returns | WTMG-RA-01 |
| `_replace_approvers` | Side effects | WTMG-RA-13 |
| `create_template` | R1 | WTMG-CT-01, WTMG-CT-03, WTMG-CT-04, WTMG-CT-05, WTMG-CT-52 |
| `create_template` | R1a [BUG-1228] | WTMG-CT-06 |
| `create_template` | R2 | WTMG-CT-09 |
| `create_template` | R2 [BUG-2334] | WTMG-CT-07, WTMG-CT-08, WTMG-CT-10 |
| `create_template` | R3 [BUG-1015] | WTMG-CT-11, WTMG-CT-12, WTMG-CT-13, WTMG-CT-14, WTMG-CT-15, WTMG-CT-16, WTMG-CT-17, WTMG-CT-18, WTMG-CT-19, WTMG-CT-20, WTMG-CT-21, WTMG-CT-50, WTMG-CT-51, WTMG-CT-53 |
| `create_template` | R3a [BUG-2341] | WTMG-CT-22, WTMG-CT-23, WTMG-CT-24 |
| `create_template` | R4 | WTMG-CT-25, WTMG-CT-26, WTMG-CT-27, WTMG-CT-28, WTMG-CT-55 |
| `create_template` | R4 [BUG-2336] | WTMG-CT-29, WTMG-CT-54 |
| `create_template` | R4 [BUG-2337] | WTMG-CT-30 |
| `create_template` | R4 [BUG-2338] | WTMG-CT-31 |
| `create_template` | R5 | WTMG-CT-01, WTMG-CT-02, WTMG-CT-32, WTMG-CT-33 |
| `create_template` | R5 [BUG-2335] | WTMG-CT-34, WTMG-Q21-08 |
| `create_template` | R6 [BUG-2346] | WTMG-Q21-01, WTMG-Q21-02 |
| `create_template` | R6 | WTMG-Q21-09 |
| `create_template` | R6a | WTMG-Q21-03 |
| `create_template` | R7 | WTMG-CT-02, WTMG-CT-42, WTMG-CT-43, WTMG-CT-44, WTMG-CT-45 |
| `create_template` | R8 | WTMG-CT-35 |
| `create_template` | R9 | WTMG-CT-40, WTMG-CT-41, WTMG-CT-48, WTMG-CT-55 |
| `create_template` | R9 [BUG-2350] | WTMG-CT-26, WTMG-CT-27, WTMG-CT-36, WTMG-CT-37, WTMG-CT-38, WTMG-CT-39, WTMG-CT-47 |
| `create_template` | R10 (check order) | WTMG-CT-50, WTMG-CT-51, WTMG-CT-52, WTMG-CT-53, WTMG-CT-54, WTMG-CT-56, WTMG-CT-57, WTMG-CT-58, WTMG-CT-59, WTMG-CT-60, WTMG-Q21-08 |
| `create_template` | Errors row 1 | WTMG-CT-03, WTMG-CT-04, WTMG-CT-05, WTMG-CT-52 |
| `create_template` | Errors row 2 | WTMG-CT-11, WTMG-CT-12, WTMG-CT-13, WTMG-CT-14, WTMG-CT-15, WTMG-CT-16, WTMG-CT-17, WTMG-CT-18, WTMG-CT-19, WTMG-CT-20, WTMG-CT-21, WTMG-CT-22, WTMG-CT-23, WTMG-CT-24 |
| `create_template` | Errors row 3 | WTMG-CT-29, WTMG-CT-30, WTMG-CT-31 |
| `create_template` | Errors row 4 | WTMG-CT-34, WTMG-Q21-08 |
| `create_template` | Errors row 5 [BUG-2346] | WTMG-Q21-01, WTMG-Q21-02 |
| `create_template` | Errors row 6 [BUG-2350] | WTMG-CT-26, WTMG-CT-27, WTMG-CT-36, WTMG-CT-37, WTMG-CT-38, WTMG-CT-39, WTMG-CT-47 |
| `create_template` | HR-15 (money rounds half up; unreachable once BUG-2350 is fixed) | WTMG-CT-36, WTMG-CT-37, WTMG-CT-38, WTMG-CT-39, WTMG-CT-40, WTMG-CT-41, WTMG-CT-48 |
| `create_template` | Returns | WTMG-CT-01, WTMG-CT-02, WTMG-CT-40, WTMG-CT-41, WTMG-CT-48, WTMG-CT-49 |
| `create_template` | Side effects | WTMG-CT-46 |
| recurrence spec, via create_template | R8a | WTMG-CT-44, WTMG-CT-45 |
| recurrence spec, via create_template | R8a [BUG-363] | WTMG-CT-42, WTMG-CT-43 |
| `update_template` | R1 | WTMG-UT-02, WTMG-UT-03, WTMG-UT-04 |
| `update_template` | R2 | WTMG-UT-05, WTMG-UT-06, WTMG-UT-07 |
| `update_template` | R3 | WTMG-UT-08, WTMG-UT-09, WTMG-UT-10, WTMG-UT-11, WTMG-UT-13 |
| `update_template` | R3 [BUG-1228] | WTMG-UT-12 |
| `update_template` | R4 [BUG-2334] | WTMG-UT-14, WTMG-UT-15 |
| `update_template` | R5 | WTMG-UT-01, WTMG-UT-16, WTMG-UT-66, WTMG-UT-72, WTMG-UT-73, WTMG-UT-74 |
| `update_template` | R5 [BUG-2339] | WTMG-UT-17, WTMG-UT-18, WTMG-UT-19, WTMG-UT-20, WTMG-UT-21, WTMG-UT-22, WTMG-UT-23, WTMG-UT-24, WTMG-UT-25, WTMG-UT-26, WTMG-UT-27, WTMG-UT-28, WTMG-UT-29, WTMG-UT-30, WTMG-UT-31, WTMG-UT-77 |
| `update_template` | R5a [BUG-2350] | WTMG-UT-72, WTMG-UT-73, WTMG-UT-76 |
| `update_template` | R5a (bounds accepted) | WTMG-UT-79, WTMG-UT-80 |
| `update_template` | R6 [BUG-1015] | WTMG-UT-32, WTMG-UT-33, WTMG-UT-34, WTMG-UT-35, WTMG-UT-36, WTMG-UT-37, WTMG-UT-38 |
| `update_template` | R6a | WTMG-UT-42, WTMG-UT-43, WTMG-UT-44 |
| `update_template` | R6a [BUG-2341] | WTMG-UT-39, WTMG-UT-40, WTMG-UT-41 |
| `update_template` | R7 (exact 422 details, G3) | WTMG-UT-45, WTMG-UT-46, WTMG-UT-47, WTMG-UT-48, WTMG-UT-49, WTMG-UT-50, WTMG-UT-51, WTMG-UT-52, WTMG-UT-53, WTMG-UT-54, WTMG-UT-55, WTMG-UT-56, WTMG-UT-57, WTMG-UT-58, WTMG-UT-59, WTMG-UT-60 |
| `update_template` | R8 | WTMG-UT-61, WTMG-UT-62, WTMG-UT-63, WTMG-UT-64, WTMG-Q21-11, WTMG-Q21-13 |
| `update_template` | R8 [BUG-2335] | WTMG-UT-65, WTMG-UT-78 |
| `update_template` | R9 [BUG-2346] | WTMG-Q21-04, WTMG-Q21-05, WTMG-Q21-12 |
| `update_template` | R9 | WTMG-Q21-07, WTMG-Q21-10, WTMG-Q21-11, WTMG-Q21-13 |
| `update_template` | R10 | WTMG-UT-01, WTMG-UT-70 |
| `update_template` | R10 [BUG-2340] | WTMG-UT-67, WTMG-UT-68, WTMG-UT-69 |
| `update_template` | R11 | WTMG-UT-71 |
| `update_template` | HR-15 (money rounds half up; unreachable once BUG-2350 is fixed) | WTMG-UT-72, WTMG-UT-73, WTMG-UT-74 |
| `update_template` | Returns | WTMG-UT-01, WTMG-UT-66 |
| `update_template` | Side effects | WTMG-UT-75 |
| recurrence spec, via update_template | R4a | WTMG-UT-47 |
| recurrence spec, via update_template | R4a [BUG-362] | WTMG-UT-45, WTMG-UT-46, WTMG-UT-48 |
| recurrence spec, via update_template | R7a | WTMG-UT-51, WTMG-UT-52 |
| recurrence spec, via update_template | R7a [BUG-362] | WTMG-UT-49, WTMG-UT-50, WTMG-UT-53 |
| recurrence spec, via update_template | R8a [BUG-363] | WTMG-UT-59, WTMG-UT-60 |
| recurrence spec, via update_template | R10a | WTMG-UT-57, WTMG-UT-58 |
| recurrence spec, via update_template | R11b | WTMG-UT-56 |
| recurrence spec, via update_template | R11b [BUG-361] | WTMG-UT-54, WTMG-UT-55 |
| `get_template` | R1 | WTMG-GT-01, WTMG-GT-02, WTMG-GT-07 |
| `get_template` | R2 | WTMG-GT-03, WTMG-GT-04, WTMG-GT-05, WTMG-GT-06 |
| `list_templates` | R1 | WTMG-LT-01, WTMG-LT-02, WTMG-LT-03, WTMG-LT-04, WTMG-LT-05, WTMG-LT-06, WTMG-LT-07 |
| `delete_template` | R1 | WTMG-DT-02, WTMG-DT-03, WTMG-DT-04 |
| `delete_template` | R2 | WTMG-DT-01, WTMG-DT-06 |
| `delete_template` | R3 | WTMG-DT-05 |
| `delete_template` | R4 | WTMG-GD-06 |
| `delete_template` | Returns | WTMG-DT-01 |
| `delete_template` | Side effects | WTMG-DT-06 |
| `restore_template` | R1 | WTMG-RT-02, WTMG-RT-03, WTMG-RT-04 |
| `restore_template` | R2 | WTMG-RT-01, WTMG-RT-05, WTMG-RT-08 |
| `restore_template` | R2 [BUG-2340] | WTMG-RT-06 |
| `restore_template` | R3 | WTMG-RT-07 |
| `restore_template` | Returns | WTMG-RT-01 |
| `restore_template` | Side effects | WTMG-RT-08 |
| `add_item` | R1 | WTMG-AI-03, WTMG-AI-04, WTMG-AI-05, WTMG-AI-06 |
| `add_item` | R2 | WTMG-AI-07, WTMG-AI-08 |
| `add_item` | R2a [BUG-2337] | WTMG-AI-09, WTMG-AI-10 |
| `add_item` | R2b | WTMG-AI-12 |
| `add_item` | R2b [BUG-2338] | WTMG-AI-11 |
| `add_item` | R3 [BUG-1015] | WTMG-AI-13, WTMG-AI-14, WTMG-AI-15, WTMG-AI-16 |
| `add_item` | R4 | WTMG-AI-01, WTMG-AI-02, WTMG-AI-08, WTMG-AI-17, WTMG-AI-22, WTMG-AI-24, WTMG-AI-27 |
| `add_item` | R5 | WTMG-AI-22, WTMG-AI-24, WTMG-AI-27 |
| `add_item` | R5 [BUG-2350] | WTMG-AI-18, WTMG-AI-19, WTMG-AI-20, WTMG-AI-21, WTMG-AI-23, WTMG-AI-26 |
| `add_item` | Errors | WTMG-AI-07 |
| `add_item` | HR-15 (money rounds half up; unreachable once BUG-2350 is fixed) | WTMG-AI-18, WTMG-AI-19, WTMG-AI-20, WTMG-AI-21, WTMG-AI-22, WTMG-AI-23, WTMG-AI-24, WTMG-AI-27 |
| `add_item` | Returns | WTMG-AI-01 |
| `add_item` | Side effects | WTMG-AI-25 |
| `update_item` | R1 | WTMG-UI-02, WTMG-UI-03, WTMG-UI-04, WTMG-UI-05 |
| `update_item` | R2 | WTMG-UI-07, WTMG-UI-08, WTMG-UI-09 |
| `update_item` | R2 [BUG-2336] | WTMG-UI-06 |
| `update_item` | R2a [BUG-2337] | WTMG-UI-10, WTMG-UI-12 |
| `update_item` | R3 | WTMG-UI-01, WTMG-UI-11, WTMG-UI-20 |
| `update_item` | R3 [BUG-2336] | WTMG-UI-07 |
| `update_item` | R3 [BUG-2339] | WTMG-UI-13, WTMG-UI-14, WTMG-UI-15, WTMG-UI-24 |
| `update_item` | R3a [BUG-2350] | WTMG-UI-19, WTMG-UI-21, WTMG-UI-23 |
| `update_item` | R3a (bounds accepted) | WTMG-UI-25, WTMG-UI-26 |
| `update_item` | R4 [BUG-1015] | WTMG-UI-16, WTMG-UI-17 |
| `update_item` | R5 | WTMG-UI-18 |
| `update_item` | HR-15 (money rounds half up; unreachable once BUG-2350 is fixed) | WTMG-UI-19, WTMG-UI-20, WTMG-UI-21 |
| `update_item` | Returns | WTMG-UI-01 |
| `update_item` | Side effects | WTMG-UI-22 |
| `remove_item` | R1 | WTMG-RI-02, WTMG-RI-03, WTMG-RI-04 |
| `remove_item` | R2 | WTMG-RI-01, WTMG-RI-05, WTMG-RI-06, WTMG-RI-07 |
| `remove_item` | Returns | WTMG-RI-01 |
| `remove_item` | Side effects | WTMG-RI-06 |
| `get_items` | R1 | WTMG-GI-01, WTMG-GI-02, WTMG-GI-03, WTMG-GI-04, WTMG-GI-05, WTMG-GI-06 |
| `get_approvers` | R1 | WTMG-GA-01, WTMG-GA-02, WTMG-GA-03, WTMG-GA-04, WTMG-GA-05 |
| `generate_drafts_for_anchored_range` | R1 | WTMG-AR-10, WTMG-AR-11 |
| `generate_drafts_for_anchored_range` | R2 | WTMG-AR-01, WTMG-AR-02, WTMG-AR-03, WTMG-AR-04, WTMG-AR-05, WTMG-AR-06, WTMG-AR-07, WTMG-AR-08, WTMG-AR-09, WTMG-AR-12, WTMG-AR-13, WTMG-AR-14, WTMG-AR-15, WTMG-AR-16, WTMG-AR-17, WTMG-AR-18, WTMG-AR-19 |
| `generate_drafts_for_anchored_range` | R3 | WTMG-AR-01, WTMG-AR-02, WTMG-AR-03, WTMG-AR-04, WTMG-AR-05, WTMG-AR-06, WTMG-AR-07, WTMG-AR-08, WTMG-AR-09, WTMG-AR-24 |
| `generate_drafts_for_anchored_range` | R4 | WTMG-AR-20 |
| `generate_drafts_for_anchored_range` | R5 | WTMG-AR-21, WTMG-AR-25 |
| `generate_drafts_for_anchored_range` | R6 [BUG-2343] | WTMG-AR-22 |
| `generate_drafts_for_anchored_range` | R7 | WTMG-AR-23 |
| `generate_drafts_for_anchored_range` | Facts (open order) | WTMG-AR-14, WTMG-AR-15, WTMG-AR-16, WTMG-AR-17, WTMG-AR-18, WTMG-AR-19 |
| `generate_drafts_for_anchored_range` | Returns | WTMG-AR-01 |
| `generate_drafts_for_anchored_range` | Side effects | WTMG-AR-24 |
| `generate_drafts` | R1 | WTMG-GD-01, WTMG-GD-02, WTMG-GD-03, WTMG-GD-04, WTMG-GD-05, WTMG-GD-06, WTMG-GD-08, WTMG-GD-09, WTMG-GD-24, WTMG-GD-25, WTMG-GD-34, WTMG-GD-35, WTMG-GD-36, WTMG-GD-37, WTMG-Q19-06 |
| `generate_drafts` | R2 | WTMG-GD-07, WTMG-GD-38 |
| `generate_drafts` | R3 | WTMG-GD-40 |
| `generate_drafts` | R3 [BUG-2342] | WTMG-GD-41 |
| `generate_drafts` | R4 [BUG-2345] | WTMG-Q19-01, WTMG-Q19-02, WTMG-Q19-03, WTMG-Q19-04, WTMG-Q19-07 |
| `generate_drafts` | R4 | WTMG-Q19-05, WTMG-Q19-06 |
| `generate_drafts` | R5 (guard; unreachable after BUG-2345) | WTMG-GD-39 |
| `generate_drafts` | R6 | WTMG-GD-01, WTMG-GD-21, WTMG-GD-22, WTMG-GD-23 |
| `generate_drafts` | R7 | WTMG-GD-01, WTMG-GD-10, WTMG-GD-11, WTMG-GD-12, WTMG-GD-13, WTMG-GD-14, WTMG-GD-15, WTMG-GD-16, WTMG-GD-17, WTMG-GD-18, WTMG-GD-19, WTMG-GD-20, WTMG-GD-21, WTMG-GD-26, WTMG-GD-27, WTMG-GD-28, WTMG-GD-29, WTMG-GD-30, WTMG-GD-31, WTMG-GD-32, WTMG-GD-33, WTMG-GD-49 |
| `generate_drafts` | R8 | WTMG-GD-07, WTMG-GD-34, WTMG-Q19-05 |
| `generate_drafts` | R9 | WTMG-GD-01, WTMG-GD-04, WTMG-GD-10, WTMG-GD-11, WTMG-GD-12, WTMG-GD-13, WTMG-GD-14, WTMG-GD-15, WTMG-GD-16, WTMG-GD-17, WTMG-GD-18, WTMG-GD-19, WTMG-GD-20, WTMG-GD-22, WTMG-GD-26, WTMG-GD-33, WTMG-GD-46, WTMG-GD-47, WTMG-Q19-06 |
| `generate_drafts` | R10 ✅ (owner, OQ-20) | WTMG-Q20-01, WTMG-Q20-02, WTMG-Q20-03, WTMG-Q20-04 |
| `generate_drafts` | R11 [BUG-2343] | WTMG-GD-42 |
| `generate_drafts` | R12 [BUG-2344] | WTMG-GD-43 |
| `generate_drafts` | R13 | WTMG-GD-44, WTMG-GD-45, WTMG-GD-46, WTMG-GD-47 |
| `generate_drafts` | R1 (workspace of the (b) candidates) | WTMG-GD-44 |
| `generate_drafts` | Facts (open order) | WTMG-GD-27, WTMG-GD-28, WTMG-GD-29, WTMG-GD-30 |
| `generate_drafts` | Returns | WTMG-GD-01, WTMG-GD-09 |
| `generate_drafts` | Side effects | WTMG-GD-48, WTMG-GD-49 |
| recurrence spec, via generate_drafts | `advance_next_generation_date` | WTMG-GD-10, WTMG-GD-11, WTMG-GD-12, WTMG-GD-13, WTMG-GD-14, WTMG-GD-15, WTMG-GD-16, WTMG-GD-17, WTMG-GD-18, WTMG-GD-19, WTMG-GD-20 |
