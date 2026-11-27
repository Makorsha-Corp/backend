# Test cases — `app/managers/project_manager.py`

> **Spec:** `tests/unit/managers/project_manager.spec.md` (source commit e48a092)
> **Status:** READY — the spec is **APPROVED** (2026-11-04; nothing open). Q1 is the owner's answer (OQ-18: project pages answer 403); Q2 and P1–P7 were decided by Claude under the reviewer's delegation.
> **Revision:** 2 (2026-11-04) — `project_manager.verify.md` Findings 1–5, all `case-missing`. Findings 1–4: a `session:` line, checked before any re-read, added to SV-04, SV-05 (`P not in db.dirty and not db.new`), D-05 (same), AM-12, AM-13 (`not db.new and not db.dirty`), RM-05, RM-06 (`not db.deleted and not db.new`); later Then lines renumbered, nothing else changed. Finding 5: new PRJM-CA-33 (W2 private project, member row under W2, asked with W1 → `False`, pass). The spec did not change; no ID retired.
> **Counts:** 280 cases · 234 expected-to-pass · 46 expected-to-fail (bugs) · 7 deferred

## Reviewer summary
- **Per callable:** `_visibility_value` 5 · `_is_workspace_owner` 7 · `_is_privileged` 18 · `can_access_project` 33 · `_get_project_or_404` 6 · `require_project_access` 7 · `require_component_access` 9 (1 bug) · `_format_field_value` 7 · `_collect_field_changes` 10 · `log_for_component` 9 · `log_event` 10 (4 bug) · `list_events` 8 (1 bug) · `list_members` 6 (2 bug) · `add_member` 18 (1 bug) · `remove_member` 13 (1 bug) · `set_visibility` 8 · `create_project` 27 (7 bug) · `get_project` 7 (2 bug) · `delete_project` 8 · `list_projects` 30 (11 bug) · `update_project` 34 (16 bug).
- **Expected-to-fail by bug:** BUG-1278 4 · BUG-1192 4 · BUG-1964 1 · BUG-1274 1 · BUG-1951 5 · BUG-1952 2 · BUG-1953 8 · BUG-1954 2 · BUG-1955 2 · BUG-1956 1 · BUG-1957 2 · BUG-1958 4 · BUG-1959 1 · BUG-1960 1 · BUG-1962 3 · BUG-1963 5. Three are non-strict (PRJM-LM-03 tie, PRJM-L-09 and L-10: the filtered DAO reads have no order today); all others strict.
- **Depth:** full depth on the private-project rule (shared with discussion and calendar, OQ-5) and on the budget (money, HR-15); lighter on the event log helpers. The access rule is tested directly in `can_access_project` / `_is_privileged` / `_is_workspace_owner` with every grant (workspace owner, active `owner`, active `ground-team-manager`, creator, project member incl. raw membership), every refusal shape of skill step 1b (the same grant on another project, another workspace W0 *and* W2, owner/creator ids below and above the caller's, a membership row filed under W2, no creator), and exact-compare cards on role, status and visibility text. The grants mirror `calendar_service.cases.md` CAL-OQ5-02 … 11 and `discussion_service.cases.md` DSS-C-33 … 37, 46 … 48, 51; here the refusal is 403 on project pages (OQ-18), 404 only for a missing or foreign project.
- **Notable design choices:**
  - BUG-1958: the hidden private rows sort ahead of the visible ones both by id (today) and by name (after BUG-1957), so L-07 (`limit=2` → today `[]`) and L-08 (`skip=1` → today both visible rows) fail strictly whatever the fixed order. The factory and status paths (L-09, L-10) rest on physical order today, so they are non-strict, `Author: claude`.
  - Money: budget boundaries 0, `null`, two decimals, 13 integer digits pass; -5, -0.01, three decimals, 14 integer digits are schema xfails (BUG-1962/1963), on create and update. No card tests today's database rounding of a three-decimal budget: that is the buggy path. U-34 (pass) and U-32 (xfail) split the stored form from the logged form.
  - BUG-1964 counts statements that are not the project read, with five distinct performers, so an identity-map hit cannot make today's code pass.
  - `require_project_access` R3 (deleted → 404) is tested through its callers (`list_members`, `add_member`, `remove_member`, `get_project`, `require_component_access`), never on the method itself: the option the fix adds is not named (Spec gap 4).
  - Cross-table id order: `require_component_access` and `log_for_component` set explicit ids (XID) so a component id can never equal its project id.
  - Commit spies: one per writer (LC-09, LE-10, AM-18, RM-13, SV-08, C-27, D-08, U-33).
- **Needs a decision:** None blocking. Spec gaps 1–7 (module of the schemas, priority enum, `visibility` argument type, deleted-project option, a gone profile, required create fields, factory close columns).

## Conventions for this module

**IDs.** `PRJM` = `app/managers/project_manager.py` (`PRJ` is the project DAO's). `VV` _visibility_value · `WO` _is_workspace_owner · `PV` _is_privileged · `CA` can_access_project · `GN` _get_project_or_404 · `RA` require_project_access · `RC` require_component_access · `FF` _format_field_value · `CF` _collect_field_changes · `LC` log_for_component · `LE` log_event · `EV` list_events · `LM` list_members · `AM` add_member · `RM` remove_member · `SV` set_visibility · `C` create_project · `G` get_project · `L` list_projects · `U` update_project · `D` delete_project.

**Imports.** `from app.managers.project_manager import ProjectManager, project_manager, PRIVILEGED_ROLES, PROJECT_LOG_FIELDS`. Models from `app.models.<module>`: `factory.Factory`, `project.Project`, `project_member.ProjectMember`, `project_event.ProjectEvent`, `project_component.ProjectComponent`, `workspace_member.WorkspaceMember`, `profile.Profile`, `subscription_plan.SubscriptionPlan`. `ProjectStatusEnum`, `ProjectVisibilityEnum` (`app.models.enums`). `ProjectCreate`, `ProjectUpdate` (`app.schemas.project`, Spec gap 1). `HTTPException` (`fastapi`); `ValidationError` (`pydantic`); `DataError`, `IntegrityError` (`sqlalchemy.exc`); `event`, `insert`, `text` (`sqlalchemy`); `Decimal`; `datetime`, `timedelta`; `patch` (`unittest.mock`); `os`.

**Fixed values.** `PM` = `project_manager`. `db` = the test's real session, always the first argument; every other argument by keyword. `result` = what the When returns. The session does not autoflush. MISSING = `999999999` (no row of any table has it). T0 = `datetime(2025, 12, 1, 8, 0, 0)`, T1 = `datetime(2026, 1, 1, 9, 0, 0)`, T2 = `datetime(2026, 1, 1, 10, 0, 0)`, T3 = `datetime(2026, 1, 1, 11, 0, 0)`, NOW = `datetime(2026, 3, 1, 10, 0, 0)` (all naive). **XID(k)** = `800_000_000 + (os.getpid() % 1_000_000) * 10 + k`: an explicit row id no sequence gives; "`id XID(k)`" passes `id=XID(k)` to the builder.

**Externals.** `app.managers.project_manager.utcnow` is patched to return NOW in every test (the test helper does it; no card patches it). Nothing else is mocked. `created_at` and `assigned_at` are asserted `is not None`, or given in the Given.

**Standing rows** (every test, no Given line; built in this order, each flushed):
- W0, W1, W2 = `make_workspace(db)`, in that order (`W0.id < W1.id < W2.id`). No workspace has an `owner_user_id` unless a Given line sets it.
- U1 = `make_profile(db, name="Ana Rahman")`; U2 = `make_profile(db, name="Bilal Khan")`; UG = `make_profile(db, name="Mia Khan")` (so `U1.id < U2.id < UG.id`). U1 is `created_by` of every Given project. Memberships: `member(U1, "ground-team")`, `member(U2, "owner")`, `member(UG, "ground-team")`. U2 is the default acting user (privileged); UG is the plain caller.
- F0 = `Factory(workspace_id=W0.id, name="Factory Zero", abbreviation="F0")`. F1 = `Factory(workspace_id=W1.id, name="Factory One", abbreviation="F1")`. F2 = F1 but `name "Factory Two"`, `abbreviation "F2"`. FI = F1 but `name "Idle Plant"`, `abbreviation "IP"`, `is_active False`. FD = F1 but `name "Old Plant"`, `abbreviation "OP"`, `is_deleted True` (Spec gap 8). F9 = `Factory(workspace_id=W2.id, name="Factory Nine", abbreviation="F9")`.

**Given rows.** Built directly (never through `PM` unless written as code), added and flushed one at a time in the order written, so ids of one table rise in that order. After "but" a line lists every column that differs. A line written as code is a step run exactly as written, at that place.
- **member(U, role, status="active", ws=W1)** = `WorkspaceMember(workspace_id=ws.id, user_id=U.id, role=role, status=status)`.
- **proj** = `Project(workspace_id=W1.id, factory_id=F1.id, name=…, description="Main", created_by=U1.id)`; the card gives `name`. **W0 proj** = `workspace_id W0.id`, `factory_id F0.id`; **W2 proj** = `workspace_id W2.id`, `factory_id F9.id`. **private** = `visibility "invited_only"`. **deleted** = `is_deleted True`, `deleted_at T0`, `deleted_by U1.id` (`is_active` untouched).
- **pmem(P, U)** = `ProjectMember(workspace_id=P.workspace_id, project_id=P.id, user_id=U.id, assigned_by=U1.id)`; a card may add `assigned_at`.
- **comp(P, "N")** = `ProjectComponent(workspace_id=P.workspace_id, project_id=P.id, name="N")`.
- **ev(P, "type", at, by)** = `ProjectEvent(workspace_id=P.workspace_id, project_id=P.id, event_type="type", description="seed", performed_by=by, created_at=at, metadata_json=None)`; `by` is a profile id or `None`.
- **bulk(n, p)** = n live projects of F1 in W1, one `db.execute(insert(Project), [...])`, named p + the number from 0, padded to 5 digits (`P00000` …), `description "Main"`, `created_by U1.id`, `visibility "workspace"`; then `db.expire_all()`.
- **set_owner(W, U)** = `W.owner_user_id = U.id`, then `db.flush()`.

**Named checks.**
- **re-read X** = `db.expire_all()`, then SELECT X by id; values are database values. **unchanged(X)** = after re-read, every column of X equals its snapshot taken after the last Given line (`db.refresh(X)` first).
- **nothing written** = the numbers of rows of `projects`, `project_members`, `project_events`, `project_components` (all workspaces) equal their values before the call.
- **events_of(P)** = `db.expire_all()`, then every `project_events` row with `project_id == P.id`, ordered by `id`. **members_of(P)** = the same on `project_members`. `metadata_json` is compared as a whole value, list order included.
- **idset(x)** = `{r.id for r in x}`. **names(x)** = `[r.name for r in x]`, order is part of the check. **val(x)** = `getattr(x, "value", x)`.
- `raises: HTTPException` = `with pytest.raises(HTTPException) as exc:` around the call; then `exc.value.status_code`, `exc.value.detail`, one per line. `raises: ValueError` / `ValidationError` the same. `raises: DataError` / `IntegrityError` = `with pytest.raises(<T>):` then `with db.begin_nested():` then the call; keep using `db` afterwards.
- `session:` lines check `db` directly, right after the call, before any re-read.
- **recorder** = a Given step: `stmts = []`, `event.listen(db.connection(), "before_cursor_execute", rec)` where `rec(conn, cursor, statement, params, context, executemany)` appends `statement`; removed with `event.remove` right after the When.
- **Rolled back** (commit spy, one per writer) = `with patch.object(db, "commit", wraps=db.commit) as cm:` around `sp = db.begin_nested()`, the call, `sp.rollback()`; then the Then lines.

**xfail cards.** Strict: `pytest.mark.xfail(strict=True, reason="BUG-NNN")`; `(non-strict)` = `strict=False`. Write the call and checks as shown, also when the call uses a parameter that does not exist yet. Target `schema` = the When only builds the schema object.

**Race simulations.** None.
## `ProjectManager._visibility_value`

### PRJM-VV-01 — no visibility reads as "workspace"
- **Rules:** `_visibility_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `P = Project(name="Draft", visibility=None)` (not added to the session).

**When**
- `result = PM._visibility_value(P)`.

**Then**
1. returns: `result == "workspace"`.

### PRJM-VV-02 — an enum member gives its value
- **Rules:** `_visibility_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `P = Project(name="Draft", visibility=ProjectVisibilityEnum.INVITED_ONLY)` (not added).

**When**
- `result = PM._visibility_value(P)`.

**Then**
1. returns: `result == "invited_only"`.
2. returns: `type(result) is str`.

### PRJM-VV-03 — the enum member WORKSPACE gives "workspace"
- **Rules:** `_visibility_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `P = Project(name="Draft", visibility=ProjectVisibilityEnum.WORKSPACE)` (not added).

**When**
- `result = PM._visibility_value(P)`.

**Then**
1. returns: `result == "workspace"`.

### PRJM-VV-04 — stored text is returned as stored
- **Rules:** `_visibility_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `P = Project(name="Draft", visibility="invited_only")` (not added).

**When**
- `result = PM._visibility_value(P)`.

**Then**
1. returns: `result == "invited_only"`.

### PRJM-VV-05 — any other text is returned unchanged, case and spaces kept
- **Rules:** `_visibility_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `P = Project(name="Draft", visibility=" Secret Team")` (not added).

**When**
- `result = PM._visibility_value(P)`.

**Then**
1. returns: `result == " Secret Team"`.

## `ProjectManager._is_workspace_owner`

### PRJM-WO-01 — the workspace's owner is the owner, with no membership row
- **Rules:** `_is_workspace_owner` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (no membership anywhere).
2. set_owner(W1, UX).

**When**
- `result = PM._is_workspace_owner(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-WO-02 — another user with a lower id is not the owner
- **Rules:** `_is_workspace_owner` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W1, U1).

**When**
- `result = PM._is_workspace_owner(db, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-WO-03 — another user with a higher id is not the owner
- **Rules:** `_is_workspace_owner` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (built after UG, so `UX.id > UG.id`).
2. set_owner(W1, UX).

**When**
- `result = PM._is_workspace_owner(db, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-WO-04 — a workspace with no owner has no owner
- **Rules:** `_is_workspace_owner` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. W1 has `owner_user_id None` (standing).

**When**
- `result = PM._is_workspace_owner(db, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-WO-05 — an unknown workspace answers False, no error
- **Rules:** `_is_workspace_owner` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. set_owner(W1, UG).

**When**
- `result = PM._is_workspace_owner(db, user_id=UG.id, workspace_id=MISSING)`.

**Then**
1. returns: `result is False`.

### PRJM-WO-06 — owning W0 (lower id) does not make the caller owner of W1
- **Rules:** `_is_workspace_owner` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W0, UG).

**When**
- `result = PM._is_workspace_owner(db, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-WO-07 — owning W2 (higher id) does not make the caller owner of W1
- **Rules:** `_is_workspace_owner` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W2, UG).

**When**
- `result = PM._is_workspace_owner(db, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

## `ProjectManager._is_privileged`

### PRJM-PV-01 — the workspace owner is privileged whatever their membership
- **Rules:** `_is_privileged` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground-team", status="suspended").
3. set_owner(W1, UX).

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-PV-02 — an active member with role owner is privileged
- **Rules:** `_is_privileged` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. U2 is an active `owner` member of W1 (standing).

**When**
- `result = PM._is_privileged(db, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-PV-03 — an active member with role ground-team-manager is privileged
- **Rules:** `_is_privileged` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground-team-manager").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-PV-04 — a plain ground-team member is not privileged
- **Rules:** `_is_privileged` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. UG is an active `ground-team` member of W1 (standing).

**When**
- `result = PM._is_privileged(db, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-05 — role owner but suspended is not privileged
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", status="suspended").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-06 — role owner but invited is not privileged
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", status="invited").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-07 — role owner but inactive is not privileged
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", status="inactive").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-08 — status "Active" (capital A) is not "active"
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", status="Active").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-09 — role ground-team-manager but suspended is not privileged
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground-team-manager", status="suspended").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-10 — role "Owner" (capital O) is not a privileged role
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "Owner").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-11 — role " owner" (leading space) is not a privileged role
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, " owner").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-12 — role "manager" (part of ground-team-manager) is not a privileged role
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "manager").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-13 — role "ground_team_manager" (underscores) is not a privileged role
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground_team_manager").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-14 — role finance is not privileged
- **Rules:** `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "finance").

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-15 — no membership and not the owner: not privileged
- **Rules:** `_is_privileged` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (no membership anywhere).

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-16 — role owner in W0 (lower workspace id) does not count in W1
- **Rules:** `_is_privileged` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", ws=W0), flushed first.
3. member(UX, "ground-team"), flushed second.

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-17 — role ground-team-manager in W2 (higher workspace id) does not count in W1
- **Rules:** `_is_privileged` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground-team-manager", ws=W2), flushed first (lower membership id).
3. member(UX, "ground-team"), flushed second.

**When**
- `result = PM._is_privileged(db, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-PV-18 — the privileged set is exactly owner and ground-team-manager
- **Rules:** `_is_privileged` R2 (Facts)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PRIVILEGED_ROLES`.

**Then**
1. returns: `set(result) == {"owner", "ground-team-manager"}`.

## `ProjectManager.can_access_project`

### PRJM-CA-01 — a workspace-visible project is open to a plain member, with no read
- **Rules:** `can_access_project` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Open"`.
2. recorder.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.
2. returns: `len(stmts) == 0`.

### PRJM-CA-02 — a project with no visibility is open to a plain member
- **Rules:** `can_access_project` R1; `_visibility_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `P = Project(workspace_id=W1.id, factory_id=F1.id, name="Draft", description="Main", created_by=U1.id, visibility=None)` (not added).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-03 — a private project is closed to a plain member
- **Rules:** `can_access_project` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-04 — the workspace owner with no membership opens a private project
- **Rules:** `can_access_project` R2; `_is_privileged` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (no membership).
2. set_owner(W1, UX).
3. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-05 — an active member with role owner opens a private project
- **Rules:** `can_access_project` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-06 — an active ground-team-manager opens a private project
- **Rules:** `can_access_project` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground-team-manager").
3. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-07 — the creator opens their private project
- **Rules:** `can_access_project` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`, but `created_by UG.id`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-08 — a project member opens a private project
- **Rules:** `can_access_project` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. pmem(P, UG).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-09 — a project member with no workspace membership still opens it (raw)
- **Rules:** `can_access_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (no membership anywhere).
2. P = private proj `name "Secret"`.
3. pmem(P, UX).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-10 — a project member whose membership is inactive still opens it (raw)
- **Rules:** `can_access_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground-team", status="inactive").
3. P = private proj `name "Secret"`.
4. pmem(P, UX).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-11 — a suspended member with role owner is refused a private project
- **Rules:** `can_access_project` R2; `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", status="suspended").
3. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-12 — an inactive ground-team-manager is refused a private project
- **Rules:** `can_access_project` R2; `_is_privileged` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "ground-team-manager", status="inactive").
3. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-13 — owning W0 does not open a private project of W1
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W0, UG).
2. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-14 — owning W2 does not open a private project of W1
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W2, UG).
2. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-15 — privileged only in W0 and W2 (rows built before the W1 row) does not open it
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", ws=W2), flushed first.
3. member(UX, "ground-team-manager", ws=W0), flushed second.
4. member(UX, "ground-team"), flushed last.
5. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UX.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-16 — membership of other private projects (lower and higher id) does not open this one
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PA = private proj `name "Alpha Secret"`.
2. P = private proj `name "Secret"`.
3. PZ = private proj `name "Zeta Secret"`.
4. pmem(PA, UG).
5. pmem(PZ, UG).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-17 — other users' membership of this project (lower and higher user id) does not open it
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (`UX.id > UG.id`).
2. P = private proj `name "Secret"`.
3. pmem(P, U2).
4. pmem(P, UX).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-18 — a membership row of this project filed under W2 does not open it in W1
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. `ProjectMember(workspace_id=W2.id, project_id=P.id, user_id=UG.id, assigned_by=U1.id)` (invalid data, built only to prove it opens nothing).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-19 — having created other projects (lower and higher id) does not open this one
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. PA = private proj `name "Alpha Secret"`, but `created_by UG.id`.
2. P = private proj `name "Secret"`.
3. PZ = private proj `name "Zeta Secret"`, but `created_by UG.id`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-20 — a creator with a higher id than the caller does not open it for the caller
- **Rules:** `can_access_project` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (`UX.id > UG.id`).
2. P = private proj `name "Secret"`, but `created_by UX.id`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-21 — a W1 owner with a lower id than the caller does not open it for the caller
- **Rules:** `can_access_project` R2; `_is_workspace_owner` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W1, U1).
2. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-22 — a W1 owner with a higher id than the caller does not open it for the caller
- **Rules:** `can_access_project` R2; `_is_workspace_owner` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (`UX.id > UG.id`).
2. set_owner(W1, UX).
3. P = private proj `name "Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-23 — a private project with no creator is closed to a plain member
- **Rules:** `can_access_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`, but `created_by None`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-24 — a private project with no creator is open to a privileged member
- **Rules:** `can_access_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`, but `created_by None`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-25 — a private project with no creator is open to its project member
- **Rules:** `can_access_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`, but `created_by None`.
2. pmem(P, UG).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-26 — visibility "Workspace" (capital W) is private
- **Rules:** `can_access_project` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Secret"`, but `visibility "Workspace"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-27 — visibility " workspace" (leading space) is private
- **Rules:** `can_access_project` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Secret"`, but `visibility " workspace"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-28 — visibility "work" (part of "workspace") is private
- **Rules:** `can_access_project` R1, R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Secret"`, but `visibility "work"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.

### PRJM-CA-29 — any other visibility text is private and opens for the creator only among plain members
- **Rules:** `can_access_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Secret"`, but `visibility "private"`, `created_by UG.id`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-30 — the project's own workspace is not looked at
- **Rules:** `can_access_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = private W2 proj `name "Far Secret"`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=U2.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-31 — a soft-deleted private project is still open to its creator
- **Rules:** `can_access_project` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = private deleted proj `name "Gone Secret"`, but `created_by UG.id`.

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is True`.

### PRJM-CA-32 — the check leaves the caller's unflushed edit in place
- **Rules:** `can_access_project` R2 (reads only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. B = proj `name "Board"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = PM.can_access_project(db, project=P, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `not db.new and not db.deleted`.

### PRJM-CA-33 — a W2 private project with its member row under W2 is closed when asked with W1
- **Rules:** `can_access_project` R2, R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = private W2 proj `name "Far Secret"`.
2. pmem(P9, UG) (so the row has `workspace_id W2.id`, the project's own workspace).

**When**
- `result = PM.can_access_project(db, project=P9, user_id=UG.id, workspace_id=W1.id)`.

**Then**
1. returns: `result is False`.
## `ProjectManager._get_project_or_404`

### PRJM-GN-01 — returns the project of the workspace
- **Rules:** `_get_project_or_404` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"`.
3. P9 = W2 proj `name "Nine"`.

**When**
- `result = PM._get_project_or_404(db, project_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `isinstance(result, Project)`.

### PRJM-GN-02 — a soft-deleted project is returned (raw)
- **Rules:** `_get_project_or_404` R1
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `result = PM._get_project_or_404(db, project_id=P.id, workspace_id=W1.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.is_deleted is True`.

### PRJM-GN-03 — an unknown id is 404
- **Rules:** `_get_project_or_404` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM._get_project_or_404(db, project_id=MISSING, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 999999999 not found"`.

### PRJM-GN-04 — id 0 is 404
- **Rules:** `_get_project_or_404` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM._get_project_or_404(db, project_id=0, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 0 not found"`.

### PRJM-GN-05 — a W0 project (lower id) is 404 in W1
- **Rules:** `_get_project_or_404` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"`.

**When**
- `PM._get_project_or_404(db, project_id=P0.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.

### PRJM-GN-06 — a W2 project (higher id) is 404 in W1
- **Rules:** `_get_project_or_404` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. P9 = W2 proj `name "Nine"`.

**When**
- `PM._get_project_or_404(db, project_id=P9.id, workspace_id=W1.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.

## `ProjectManager.require_project_access`

### PRJM-RA-01 — a workspace-visible project is returned to a plain member
- **Rules:** `require_project_access` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.require_project_access(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.name == "Roof job"`.

### PRJM-RA-02 — a private project is returned to its project member
- **Rules:** `require_project_access` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. pmem(P, UG).

**When**
- `result = PM.require_project_access(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == P.id`.

### PRJM-RA-03 — a private project the caller may not open is 403
- **Rules:** `require_project_access` R2, Errors R2
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `PM.require_project_access(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.
4. unchanged: unchanged(P).

### PRJM-RA-04 — an unknown id is 404
- **Rules:** `require_project_access` R1, Errors R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM.require_project_access(db, project_id=MISSING, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 999999999 not found"`.

### PRJM-RA-05 — another workspace's private project is 404, not 403
- **Rules:** `require_project_access` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = private W2 proj `name "Far Secret"`.

**When**
- `PM.require_project_access(db, project_id=P9.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.

### PRJM-RA-06 — a W0 project (lower id) is 404 in W1, even for a privileged caller
- **Rules:** `require_project_access` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"`.

**When**
- `PM.require_project_access(db, project_id=P0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.

### PRJM-RA-07 — the check leaves the caller's unflushed edit in place
- **Rules:** `require_project_access` R4 (reads only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. B = proj `name "Board"`.
3. `B.description = "Edited"` (not flushed).

**When**
- `result = PM.require_project_access(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. session: `B in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `not db.new and not db.deleted`.

## `ProjectManager.require_component_access`

### PRJM-RC-01 — returns the component's project id, not the component id
- **Rules:** `require_component_access` R1, R2, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `id XID(1)`.
2. C = comp(P, "Roof"), but `id XID(5)`.

**When**
- `result = PM.require_component_access(db, component_id=C.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result == XID(1)`.

### PRJM-RC-02 — a component of a private project is open to the project's member
- **Rules:** `require_component_access` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`, but `id XID(2)`.
2. C = comp(P, "Vault"), but `id XID(7)`.
3. pmem(P, UG).

**When**
- `result = PM.require_component_access(db, component_id=C.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result == XID(2)`.

### PRJM-RC-03 — a component of a private project the caller may not open is 403
- **Rules:** `require_component_access` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. C = comp(P, "Vault").

**When**
- `PM.require_component_access(db, component_id=C.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.

### PRJM-RC-04 — an unknown component id is 404
- **Rules:** `require_component_access` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").

**When**
- `PM.require_component_access(db, component_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component not found"`.

### PRJM-RC-05 — component id 0 is 404
- **Rules:** `require_component_access` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").

**When**
- `PM.require_component_access(db, component_id=0, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component not found"`.

### PRJM-RC-06 — a W0 component (lower id) is 404 in W1
- **Rules:** `require_component_access` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. C0 = comp(P0, "Cellar").
3. P = proj `name "Roof job"`.
4. C = comp(P, "Roof").

**When**
- `PM.require_component_access(db, component_id=C0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component not found"`.

### PRJM-RC-07 — a W2 component (higher id) is 404 in W1
- **Rules:** `require_component_access` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").
3. P9 = W2 proj `name "Nine"`.
4. C9 = comp(P9, "Floor").

**When**
- `PM.require_component_access(db, component_id=C9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project component not found"`.

### PRJM-RC-08 — a W1 component on a W2 project answers 404 for that project
- **Rules:** `require_component_access` R4
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"`.
2. CX = `ProjectComponent(workspace_id=W1.id, project_id=P9.id, name="Stray")` (invalid data, built only to prove the refusal).

**When**
- `PM.require_component_access(db, component_id=CX.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.

### PRJM-RC-09 — a component of a soft-deleted project is 404 for the project
- **Rules:** `require_component_access` R2 [BUG-1278]; `require_project_access` R3
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the project id is returned)

**Given**
1. P = deleted proj `name "Gone"`.
2. C = comp(P, "Roof").

**When**
- `PM.require_component_access(db, component_id=C.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.

## `ProjectManager._format_field_value`

### PRJM-FF-01 — None stays None
- **Rules:** `_format_field_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PM._format_field_value(None)`.

**Then**
1. returns: `result is None`.

### PRJM-FF-02 — an enum gives its value as text
- **Rules:** `_format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PM._format_field_value(ProjectStatusEnum.COMPLETED)`.

**Then**
1. returns: `result == "COMPLETED"`.

### PRJM-FF-03 — a datetime gives its date only
- **Rules:** `_format_field_value` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PM._format_field_value(datetime(2026, 3, 1, 15, 30, 45))`.

**Then**
1. returns: `result == "2026-03-01"`.

### PRJM-FF-04 — a two-decimal Decimal keeps both decimals
- **Rules:** `_format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PM._format_field_value(Decimal("1000.00"))`.

**Then**
1. returns: `result == "1000.00"`.

### PRJM-FF-05 — a one-decimal Decimal is written as given
- **Rules:** `_format_field_value` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PM._format_field_value(Decimal("1000.5"))`.

**Then**
1. returns: `result == "1000.5"`.

### PRJM-FF-06 — text is returned as text, spaces kept
- **Rules:** `_format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PM._format_field_value(" Line 3")`.

**Then**
1. returns: `result == " Line 3"`.

### PRJM-FF-07 — a number is turned into text
- **Rules:** `_format_field_value` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = PM._format_field_value(7)`.

**Then**
1. returns: `result == "7"`.

## `ProjectManager._collect_field_changes`

### PRJM-CF-01 — one entry per changed field, in the order of fields
- **Rules:** `_collect_field_changes` R1, R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. `R = Project(name="Old", description="Main", budget=Decimal("10.00"))` (not added).

**When**
- `result = PM._collect_field_changes(R, {"budget": Decimal("20.00"), "name": "New"}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == [{"field": "name", "label": "Name", "from_value": "Old", "to_value": "New"}, {"field": "budget", "label": "Budget", "from_value": "10.00", "to_value": "20.00"}]`.

### PRJM-CF-02 — the order comes from fields, not from the update dict
- **Rules:** `_collect_field_changes` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = Project(name="Old", description="Main")` (not added).

**When**
- `result = PM._collect_field_changes(R, {"name": "New", "description": "Side"}, {"description": "Description", "name": "Name"})`.

**Then**
1. returns: `[e["field"] for e in result] == ["description", "name"]`.

### PRJM-CF-03 — a key not in fields is ignored
- **Rules:** `_collect_field_changes` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = Project(name="Old", description="Main", created_by=U1.id)` (not added).

**When**
- `result = PM._collect_field_changes(R, {"created_by": U2.id, "description": "Side"}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == [{"field": "description", "label": "Description", "from_value": "Main", "to_value": "Side"}]`.

### PRJM-CF-04 — an equal value gives no entry
- **Rules:** `_collect_field_changes` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = Project(name="Old", description="Main")` (not added).

**When**
- `result = PM._collect_field_changes(R, {"name": "Old", "description": "Main"}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == []`.

### PRJM-CF-05 — an empty update dict gives an empty list
- **Rules:** `_collect_field_changes` R1, Returns
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = Project(name="Old", description="Main")` (not added).

**When**
- `result = PM._collect_field_changes(R, {}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == []`.
2. returns: `isinstance(result, list)`.

### PRJM-CF-06 — Decimal 1000 equals 1000.00: no entry
- **Rules:** `_collect_field_changes` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = Project(name="Old", budget=Decimal("1000.00"))` (not added).

**When**
- `result = PM._collect_field_changes(R, {"budget": Decimal("1000")}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == []`.

### PRJM-CF-07 — a deadline moved by hours in one day is an entry showing the same date twice
- **Rules:** `_collect_field_changes` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = Project(name="Old", deadline=datetime(2026, 3, 1, 9, 0, 0))` (not added).

**When**
- `result = PM._collect_field_changes(R, {"deadline": datetime(2026, 3, 1, 17, 0, 0)}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == [{"field": "deadline", "label": "Deadline", "from_value": "2026-03-01", "to_value": "2026-03-01"}]`.

### PRJM-CF-08 — a value set from nothing has from_value None
- **Rules:** `_collect_field_changes` R2; `_format_field_value` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `R = Project(name="Old", budget=None)` (not added).

**When**
- `result = PM._collect_field_changes(R, {"budget": Decimal("10.00")}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == [{"field": "budget", "label": "Budget", "from_value": None, "to_value": "10.00"}]`.

### PRJM-CF-09 — status, factory and visibility use their labels and value texts
- **Rules:** `_collect_field_changes` R1, R2 (Facts: labels)
- **Kind:** happy
- **Expect:** pass

**Given**
1. `R = Project(name="Old", status=ProjectStatusEnum.PLANNING, factory_id=F1.id, visibility="workspace")` (not added).

**When**
- `result = PM._collect_field_changes(R, {"visibility": "invited_only", "factory_id": F2.id, "status": ProjectStatusEnum.COMPLETED}, PROJECT_LOG_FIELDS)`.

**Then**
1. returns: `result == [{"field": "status", "label": "Status", "from_value": "PLANNING", "to_value": "COMPLETED"}, {"field": "factory_id", "label": "Factory", "from_value": str(F1.id), "to_value": str(F2.id)}, {"field": "visibility", "label": "Visibility", "from_value": "workspace", "to_value": "invited_only"}]`.

### PRJM-CF-10 — the log fields and their labels, in order
- **Rules:** `_collect_field_changes` R1 (Facts: `PROJECT_LOG_FIELDS`)
- **Kind:** happy
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = list(PROJECT_LOG_FIELDS.items())`.

**Then**
1. returns: `result == [("name", "Name"), ("description", "Description"), ("budget", "Budget"), ("deadline", "Deadline"), ("start_date", "Start date"), ("end_date", "End date"), ("priority", "Priority"), ("status", "Status"), ("factory_id", "Factory"), ("visibility", "Visibility")]`.
## `ProjectManager.log_for_component`

### PRJM-LC-01 — writes one event on the component's project with the component in the metadata
- **Rules:** `log_for_component` R2, Returns; `log_event` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `id XID(1)`.
2. C = comp(P, "Roof"), but `id XID(5)`.

**When**
- `result = PM.log_for_component(db, component_id=C.id, workspace_id=W1.id, event_type="task_added", description="Added task Seal", performed_by=U2.id, metadata={"task": "Seal"})`.

**Then**
1. returns: `isinstance(result, ProjectEvent)`.
2. returns: `result.id is not None`.
3. count: events_of(P) has exactly 1 row.
4. re-read that row: `project_id == XID(1)`, `workspace_id == W1.id`, `event_type == "task_added"`.
5. re-read that row: `description == "Added task Seal"`, `performed_by == U2.id`.
6. re-read that row: `metadata_json == {"task": "Seal", "component_id": XID(5), "component_name": "Roof"}`.

### PRJM-LC-02 — with no metadata the stored metadata is the component dict, never null
- **Rules:** `log_for_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").

**When**
- `result = PM.log_for_component(db, component_id=C.id, workspace_id=W1.id, event_type="note_added", description="Note")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `metadata_json == {"component_id": C.id, "component_name": "Roof"}`.
3. re-read the returned row: `performed_by is None`.

### PRJM-LC-03 — the caller's component keys win
- **Rules:** `log_for_component` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").

**When**
- `result = PM.log_for_component(db, component_id=C.id, workspace_id=W1.id, event_type="note_added", description="Note", performed_by=U2.id, metadata={"component_id": 5, "component_name": "Old Roof"})`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `metadata_json == {"component_id": 5, "component_name": "Old Roof"}`.

### PRJM-LC-04 — the caller's dict is not changed
- **Rules:** `log_for_component` R2
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").
3. `meta = {"task": "Seal"}`.

**When**
- `result = PM.log_for_component(db, component_id=C.id, workspace_id=W1.id, event_type="task_added", description="Added", performed_by=U2.id, metadata=meta)`.

**Then**
1. returns: `result.id is not None`.
2. returns: `meta == {"task": "Seal"}`.

### PRJM-LC-05 — an unknown component returns None and writes nothing
- **Rules:** `log_for_component` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").

**When**
- `result = PM.log_for_component(db, component_id=MISSING, workspace_id=W1.id, event_type="note_added", description="Note", performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. nothing written.

### PRJM-LC-06 — component id 0 returns None and writes nothing
- **Rules:** `log_for_component` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").

**When**
- `result = PM.log_for_component(db, component_id=0, workspace_id=W1.id, event_type="note_added", description="Note", performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. nothing written.

### PRJM-LC-07 — a W0 component (lower id) returns None in W1
- **Rules:** `log_for_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. C0 = comp(P0, "Cellar").
3. P = proj `name "Roof job"`.
4. C = comp(P, "Roof").

**When**
- `result = PM.log_for_component(db, component_id=C0.id, workspace_id=W1.id, event_type="note_added", description="Note", performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. nothing written.

### PRJM-LC-08 — a W2 component (higher id) returns None in W1
- **Rules:** `log_for_component` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").
3. P9 = W2 proj `name "Nine"`.
4. C9 = comp(P9, "Floor").

**When**
- `result = PM.log_for_component(db, component_id=C9.id, workspace_id=W1.id, event_type="note_added", description="Note", performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. session: `not db.new`.
3. nothing written.

### PRJM-LC-09 — log_for_component does not commit
- **Rules:** `log_for_component` R2 (Overview: never commits)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. C = comp(P, "Roof").

**When**
- Rolled back: `PM.log_for_component(db, component_id=C.id, workspace_id=W1.id, event_type="note_added", description="Note", performed_by=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. count: events_of(P) has exactly 0 rows.

## `ProjectManager.log_event`

### PRJM-LE-01 — writes one row with exactly the values given, flushed
- **Rules:** `log_event` R1, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.log_event(db, project_id=P.id, workspace_id=W1.id, event_type="cost_added", description="Added cost", performed_by=U2.id, metadata={"amount": "10.50"})`.

**Then**
1. returns: `isinstance(result, ProjectEvent)`.
2. returns: `result.id is not None`.
3. count: events_of(P) has exactly 1 row.
4. re-read that row: `workspace_id == W1.id`, `project_id == P.id`, `event_type == "cost_added"`.
5. re-read that row: `description == "Added cost"`, `performed_by == U2.id`.
6. re-read that row: `metadata_json == {"amount": "10.50"}`, `created_at is not None`.

### PRJM-LE-02 — no metadata and no performer are stored as null
- **Rules:** `log_event` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.log_event(db, project_id=P.id, workspace_id=W1.id, event_type="note", description="Plain")`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `metadata_json is None`, `performed_by is None`.

### PRJM-LE-03 — a soft-deleted project of the workspace is logged to
- **Rules:** `log_event` R3
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `result = PM.log_event(db, project_id=P.id, workspace_id=W1.id, event_type="note", description="After close", performed_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: events_of(P) has exactly 1 row.

### PRJM-LE-04 — an event type of 50 characters is stored
- **Rules:** `log_event` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.log_event(db, project_id=P.id, workspace_id=W1.id, event_type="e" * 50, description="Long", performed_by=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `event_type == "e" * 50`.

### PRJM-LE-05 — an event type of 51 characters fails at the flush
- **Rules:** `log_event` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM.log_event(db, project_id=P.id, workspace_id=W1.id, event_type="e" * 51, description="Long", performed_by=U2.id)`.

**Then**
1. raises: `DataError`.
2. count: events_of(P) has exactly 0 rows.

### PRJM-LE-06 — a W2 project (higher id) is refused as not found
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error: the row is written under W1)

**Given**
1. P = proj `name "Roof job"`.
2. P9 = W2 proj `name "Nine"`.

**When**
- `PM.log_event(db, project_id=P9.id, workspace_id=W1.id, event_type="note", description="Stray", performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. session: `not db.new`.
5. nothing written.

### PRJM-LE-07 — a W0 project (lower id) is refused as not found
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (no error: the row is written under W1)

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"`.

**When**
- `PM.log_event(db, project_id=P0.id, workspace_id=W1.id, event_type="note", description="Stray", performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.
4. session: `not db.new`.
5. nothing written.

### PRJM-LE-08 — an unknown project id is refused as not found
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush, not HTTPException)

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM.log_event(db, project_id=MISSING, workspace_id=W1.id, event_type="note", description="Stray", performed_by=U2.id)`, wrapped: `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then the call.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 999999999 not found"`.
4. nothing written.

### PRJM-LE-09 — project id 0 is refused as not found
- **Rules:** `log_event` R2 [BUG-1192]
- **Kind:** bug
- **Expect:** xfail BUG-1192
- **Fails today on:** Then 1 (the call raises IntegrityError at the flush, not HTTPException)

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM.log_event(db, project_id=0, workspace_id=W1.id, event_type="note", description="Stray", performed_by=U2.id)`, wrapped: `with pytest.raises(HTTPException) as exc:` then `with db.begin_nested():` then the call.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 0 not found"`.
4. nothing written.

### PRJM-LE-10 — log_event does not commit
- **Rules:** `log_event` R1
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- Rolled back: `PM.log_event(db, project_id=P.id, workspace_id=W1.id, event_type="note", description="Plain", performed_by=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. count: events_of(P) has exactly 0 rows.

## `ProjectManager.list_events`

### PRJM-EV-01 — newest first, id breaks ties, each with its performer's profile
- **Rules:** `list_events` R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. EA = ev(P, "a", T1, U1.id).
3. EB = ev(P, "b", T3, None).
4. EC = ev(P, "c", T2, U2.id) (older than EB, higher id).
5. ED = ev(P, "d", T3, UG.id).

**When**
- `result = PM.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `[e.id for e, _ in result] == [ED.id, EB.id, EC.id, EA.id]`.
2. returns: `[(p.id if p is not None else None) for _, p in result] == [UG.id, None, U2.id, U1.id]`.
3. returns: `isinstance(result, list)`.

### PRJM-EV-02 — events of another project and of another workspace are not listed
- **Rules:** `list_events` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. Q = proj `name "Wall job"`.
3. E1 = ev(P, "a", T1, U1.id).
4. EQ = ev(Q, "b", T2, U1.id).
5. `ProjectEvent(workspace_id=W2.id, project_id=P.id, event_type="c", description="seed", performed_by=U1.id, created_at=T3, metadata_json=None)` (invalid data).

**When**
- `result = PM.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `[e.id for e, _ in result] == [E1.id]`.

### PRJM-EV-03 — a project with no events gives an empty list
- **Rules:** `list_events` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result == []`.

### PRJM-EV-04 — a soft-deleted project's log is still answered
- **Rules:** `list_events` R2
- **Kind:** soft-delete
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.
2. E1 = ev(P, "deleted", T1, U1.id).

**When**
- `result = PM.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `[e.id for e, _ in result] == [E1.id]`.

### PRJM-EV-05 — a private project's log is 403 for a plain member
- **Rules:** `list_events` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. E1 = ev(P, "a", T1, U1.id).

**When**
- `PM.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.

### PRJM-EV-06 — a private project's log is open to its creator
- **Rules:** `list_events` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`, but `created_by UG.id`.
2. E1 = ev(P, "a", T1, U1.id).

**When**
- `result = PM.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `[e.id for e, _ in result] == [E1.id]`.

### PRJM-EV-07 — another workspace's project is 404
- **Rules:** `list_events` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"`.
2. E9 = ev(P9, "a", T1, U1.id).

**When**
- `PM.list_events(db, project_id=P9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.

### PRJM-EV-08 — performers are read together: at most three statements besides the project read
- **Rules:** `list_events` R4 [BUG-1964]
- **Kind:** bug
- **Expect:** xfail BUG-1964
- **Fails today on:** Then 2 (one profile read per performer: 6 statements besides the project read)

**Given**
1. P = proj `name "Roof job"`.
2. `UX = make_profile(db, name="Omar Ali")`; `UY = make_profile(db, name="Rina Das")`.
3. Five events, one per performer: ev(P, "a", T1, U1.id), ev(P, "b", T1, U2.id), ev(P, "c", T2, UG.id), ev(P, "d", T2, UX.id), ev(P, "e", T3, UY.id).
4. `db.expire_all()`.
5. recorder.

**When**
- `result = PM.list_events(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `len(result) == 5`.
2. returns: `len([s for s in stmts if "FROM projects" not in s]) <= 3`.

## `ProjectManager.list_members`

### PRJM-LM-01 — members in order of assigned_at, not of id
- **Rules:** `list_members` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. MA = pmem(P, U1), but `assigned_at T2`.
3. MB = pmem(P, U2), but `assigned_at T1`.
4. MC = pmem(P, UG), but `assigned_at T3`.

**When**
- `result = PM.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `[m.id for m in result] == [MB.id, MA.id, MC.id]`.

### PRJM-LM-02 — members of another project are not listed; a person who left the workspace is
- **Rules:** `list_members` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (no membership).
2. Q = proj `name "Wall job"`.
3. P = proj `name "Roof job"`.
4. MQ = pmem(Q, U1), but `assigned_at T1`.
5. MX = pmem(P, UX), but `assigned_at T2`.

**When**
- `result = PM.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `[m.id for m in result] == [MX.id]`.

### PRJM-LM-03 — members with one assigned_at come back by id
- **Rules:** `list_members` R2 (project member DAO R4 [BUG-1274])
- **Kind:** bug
- **Expect:** xfail BUG-1274 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (no tie-break: physical order after the update of the lower row)

**Given**
1. P = proj `name "Roof job"`.
2. MA = pmem(P, U1), but `assigned_at T1`.
3. MB = pmem(P, U2), but `assigned_at T1`.
4. `db.execute(text("SET LOCAL enable_indexscan = off"))`, `db.execute(text("SET LOCAL enable_bitmapscan = off"))`, `db.execute(text("SET LOCAL enable_indexonlyscan = off"))`.
5. `db.execute(text("UPDATE project_members SET assigned_by = assigned_by WHERE id = :i"), {"i": MA.id})`, then `db.expire_all()`.

**When**
- `result = PM.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `[m.id for m in result] == [MA.id, MB.id]`.

### PRJM-LM-04 — a private project's members are 403 for a plain member
- **Rules:** `list_members` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. pmem(P, U1).

**When**
- `PM.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.

### PRJM-LM-05 — another workspace's project is 404
- **Rules:** `list_members` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"`.

**When**
- `PM.list_members(db, project_id=P9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.

### PRJM-LM-06 — a soft-deleted project's members are 404
- **Rules:** `list_members` R1 [BUG-1278]; `require_project_access` R3
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the members are returned)

**Given**
1. P = deleted proj `name "Gone"`.
2. pmem(P, U1).

**When**
- `PM.list_members(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.
## `ProjectManager.add_member`

### PRJM-AM-01 — adds an active member and logs member_added with their name
- **Rules:** `add_member` R4, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = private proj `name "Secret"`.

**When**
- `result = PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `isinstance(result, ProjectMember)`.
2. returns: `result.id is not None`.
3. count: members_of(P) has exactly 1 row.
4. re-read that row: `workspace_id == W1.id`, `project_id == P.id`, `user_id == UX.id`, `assigned_by == U2.id`, `assigned_at is not None`.
5. count: events_of(P) has exactly 1 row.
6. re-read that event: `event_type == "member_added"`, `description == "Added Omar Ali to the project"`, `performed_by == U2.id`, `workspace_id == W1.id`.
7. re-read that event: `metadata_json == {"user_id": UX.id, "user_name": "Omar Ali"}`.

### PRJM-AM-02 — works the same on a workspace-visible project, added by a plain member
- **Rules:** `add_member` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "finance").
2. P = proj `name "Roof job"`.

**When**
- `result = PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=UG.id)`.

**Then**
1. returns: `result.user_id == UX.id`.
2. re-read the returned row: `assigned_by == UG.id`.
3. count: events_of(P) has exactly 1 row.
4. re-read that event: `description == "Added Omar Ali to the project"`, `performed_by == UG.id`.

### PRJM-AM-03 — a member of another project only is added here
- **Rules:** `add_member` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. Q = proj `name "Wall job"`.
3. P = proj `name "Roof job"`.
4. R = proj `name "Yard job"`.
5. pmem(Q, UX).
6. pmem(R, UX).

**When**
- `result = PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. returns: `result.project_id == P.id`.
2. count: members_of(P) has exactly 1 row.

### PRJM-AM-04 — a person with no membership of the workspace is 400
- **Rules:** `add_member` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (no membership).
2. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. session: `not db.new`.
5. nothing written.

### PRJM-AM-05 — an unknown user id is 400
- **Rules:** `add_member` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=MISSING, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-06 — an active member of W0 only (lower workspace id) is 400
- **Rules:** `add_member` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "owner", ws=W0).
2. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-07 — an active member of W2 only (higher workspace id) is 400
- **Rules:** `add_member` R2
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "owner", ws=W2).
2. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-08 — a suspended member is 400
- **Rules:** `add_member` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team", status="suspended").
2. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-09 — an invited member is 400
- **Rules:** `add_member` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team", status="invited").
2. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-10 — an inactive member is 400
- **Rules:** `add_member` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team", status="inactive").
2. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-11 — status "Active" (capital A) is 400
- **Rules:** `add_member` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team", status="Active").
2. P = proj `name "Roof job"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-12 — someone already a member is 409
- **Rules:** `add_member` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = proj `name "Roof job"`.
3. MX = pmem(P, UX).

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already a member of this project"`.
4. session: `not db.new and not db.dirty`.
5. unchanged: unchanged(MX).
6. nothing written.

### PRJM-AM-13 — the creator, a member from creation, is 409
- **Rules:** `add_member` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (creator U1).
2. pmem(P, U1), but `assigned_by U1.id`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=U1.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 409`.
3. raises: `exc.value.detail == "User is already a member of this project"`.
4. session: `not db.new and not db.dirty`.
5. nothing written.

### PRJM-AM-14 — a suspended person already on the project gets 400 (status is checked first)
- **Rules:** `add_member` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team", status="suspended").
2. P = proj `name "Roof job"`.
3. pmem(P, UX).

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "User is not an active member of this workspace"`.
4. nothing written.

### PRJM-AM-15 — a caller who may not open the private project is 403
- **Rules:** `add_member` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = private proj `name "Secret"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.
4. nothing written.

### PRJM-AM-16 — another workspace's project is 404
- **Rules:** `add_member` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P9 = W2 proj `name "Nine"`.

**When**
- `PM.add_member(db, project_id=P9.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. nothing written.

### PRJM-AM-17 — a soft-deleted project is 404 and nobody is added
- **Rules:** `add_member` R1 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the member is added)

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = deleted proj `name "Gone"`.

**When**
- `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.
4. session: `not db.new`.
5. nothing written.

### PRJM-AM-18 — add_member does not commit
- **Rules:** `add_member` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team").
2. P = proj `name "Roof job"`.

**When**
- Rolled back: `PM.add_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, assigned_by=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. count: members_of(P) has exactly 0 rows.
3. count: events_of(P) has exactly 0 rows.

## `ProjectManager.remove_member`

### PRJM-RM-01 — removes the row and logs member_removed with their name
- **Rules:** `remove_member` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "ground-team") (`UX.id > U1.id`, the creator).
2. P = private proj `name "Secret"`.
3. MU = pmem(P, U2).
4. MX = pmem(P, UX).

**When**
- `result = PM.remove_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. returns: `[m.id for m in members_of(P)] == [MU.id]`.
3. count: events_of(P) has exactly 1 row.
4. re-read that event: `event_type == "member_removed"`, `description == "Removed Omar Ali from the project"`, `performed_by == U2.id`, `workspace_id == W1.id`.
5. re-read that event: `metadata_json == {"user_id": UX.id, "user_name": "Omar Ali"}`.

### PRJM-RM-02 — a member with a lower id than the creator is removed
- **Rules:** `remove_member` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (`UX.id > U1.id`).
2. P = proj `name "Roof job"`, but `created_by UX.id`.
3. M1 = pmem(P, U1).

**When**
- `result = PM.remove_member(db, project_id=P.id, member_user_id=U1.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: members_of(P) has exactly 0 rows.
3. count: events_of(P) has exactly 1 row.

### PRJM-RM-03 — a person who left the workspace can be removed
- **Rules:** `remove_member` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")` (no membership).
2. P = proj `name "Roof job"`.
3. pmem(P, UX).

**When**
- `result = PM.remove_member(db, project_id=P.id, member_user_id=UX.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: members_of(P) has exactly 0 rows.
3. re-read the one event of P: `description == "Removed Omar Ali from the project"`.

### PRJM-RM-04 — a member may remove themselves
- **Rules:** `remove_member` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. pmem(P, UG).

**When**
- `result = PM.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=UG.id)`.

**Then**
1. returns: `result is None`.
2. count: members_of(P) has exactly 0 rows.
3. re-read the one event of P: `performed_by == UG.id`, `description == "Removed Mia Khan from the project"`.

### PRJM-RM-05 — removing the creator is 400 and nothing is deleted
- **Rules:** `remove_member` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (creator U1).
2. M1 = pmem(P, U1).

**When**
- `PM.remove_member(db, project_id=P.id, member_user_id=U1.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove the project creator from members"`.
4. session: `not db.deleted and not db.new`.
5. unchanged: unchanged(M1).
6. nothing written.

### PRJM-RM-06 — the creator check comes before the membership lookup
- **Rules:** `remove_member` R2, R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"` (creator U1; U1 has no project_members row).

**When**
- `PM.remove_member(db, project_id=P.id, member_user_id=U1.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot remove the project creator from members"`.
4. session: `not db.deleted and not db.new`.
5. nothing written.

### PRJM-RM-07 — a project with no creator: a member is removed
- **Rules:** `remove_member` R2, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `created_by None`.
2. pmem(P, UG).

**When**
- `result = PM.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. returns: `result is None`.
2. count: members_of(P) has exactly 0 rows.

### PRJM-RM-08 — someone not on the project is 404
- **Rules:** `remove_member` R3
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. M2 = pmem(P, U2).

**When**
- `PM.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project member not found"`.
4. unchanged: unchanged(M2).
5. nothing written.

### PRJM-RM-09 — a membership of other projects only (lower and higher id) is 404 here
- **Rules:** `remove_member` R3
- **Kind:** isolation
- **Expect:** pass

**Given**
1. Q = proj `name "Wall job"`.
2. P = proj `name "Roof job"`.
3. R = proj `name "Yard job"`.
4. MQ = pmem(Q, UG).
5. MR = pmem(R, UG).

**When**
- `PM.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project member not found"`.
4. unchanged: unchanged(MQ).
5. unchanged: unchanged(MR).
6. nothing written.

### PRJM-RM-10 — a caller who may not open the private project is 403
- **Rules:** `remove_member` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. M2 = pmem(P, U2).

**When**
- `PM.remove_member(db, project_id=P.id, member_user_id=U2.id, workspace_id=W1.id, performed_by=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.
4. unchanged: unchanged(M2).
5. nothing written.

### PRJM-RM-11 — another workspace's project is 404
- **Rules:** `remove_member` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"`.
2. M9 = pmem(P9, UG).

**When**
- `PM.remove_member(db, project_id=P9.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. unchanged: unchanged(M9).
5. nothing written.

### PRJM-RM-12 — a soft-deleted project is 404 and nobody is removed
- **Rules:** `remove_member` R1 [BUG-1278]
- **Kind:** bug
- **Expect:** xfail BUG-1278
- **Fails today on:** Then 1 (no error: the member is removed)

**Given**
1. P = deleted proj `name "Gone"`.
2. MG = pmem(P, UG).

**When**
- `PM.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.
4. session: `not db.deleted and not db.new`.
5. nothing written.

### PRJM-RM-13 — remove_member does not commit
- **Rules:** `remove_member` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. pmem(P, UG).

**When**
- Rolled back: `PM.remove_member(db, project_id=P.id, member_user_id=UG.id, workspace_id=W1.id, performed_by=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. count: members_of(P) has exactly 1 row.
3. count: events_of(P) has exactly 0 rows.

## `ProjectManager.set_visibility`

### PRJM-SV-01 — makes a project private, stamps it and logs the change
- **Rules:** `set_visibility` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `visibility == "invited_only"`, `updated_by == U2.id`, `updated_at == NOW`.
3. count: events_of(P) has exactly 1 row.
4. re-read that event: `event_type == "visibility_updated"`, `description == "Changed visibility from workspace to invited_only"`, `performed_by == U2.id`.
5. re-read that event: `metadata_json == {"changes": [{"field": "visibility", "label": "Visibility", "from_value": "workspace", "to_value": "invited_only"}]}`.

### PRJM-SV-02 — a project member makes a private project workspace-visible
- **Rules:** `set_visibility` R1, R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.
2. pmem(P, UG).

**When**
- `result = PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.WORKSPACE, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `visibility == "workspace"`, `updated_by == UG.id`.
3. re-read the one event of P: `description == "Changed visibility from invited_only to workspace"`, `performed_by == UG.id`.
4. re-read the one event of P: `metadata_json == {"changes": [{"field": "visibility", "label": "Visibility", "from_value": "invited_only", "to_value": "workspace"}]}`.

### PRJM-SV-03 — the same visibility returns the project unchanged, no stamp, no event
- **Rules:** `set_visibility` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `result = PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. unchanged: unchanged(P).
3. re-read P: `updated_by is None`, `updated_at is None`.
4. count: events_of(P) has exactly 0 rows.

### PRJM-SV-04 — a soft-deleted project is 400
- **Rules:** `set_visibility` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted project"`.
4. session: `P not in db.dirty and not db.new`.
5. unchanged: unchanged(P).
6. nothing written.

### PRJM-SV-05 — a soft-deleted project is 400 even when the visibility would not change
- **Rules:** `set_visibility` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.WORKSPACE, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted project"`.
4. session: `P not in db.dirty and not db.new`.
5. unchanged: unchanged(P).

### PRJM-SV-06 — a caller who may not open the private project is 403
- **Rules:** `set_visibility` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.WORKSPACE, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.
4. unchanged: unchanged(P).
5. nothing written.

### PRJM-SV-07 — another workspace's project is 404
- **Rules:** `set_visibility` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"`.

**When**
- `PM.set_visibility(db, project_id=P9.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. unchanged: unchanged(P9).

### PRJM-SV-08 — set_visibility does not commit
- **Rules:** `set_visibility` R4
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- Rolled back: `PM.set_visibility(db, project_id=P.id, visibility=ProjectVisibilityEnum.INVITED_ONLY, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read P: `visibility == "workspace"`.
3. count: events_of(P) has exactly 0 rows.
## `ProjectManager.create_project`

### PRJM-C-01 — create stores every sent field, in the caller's workspace, by the caller
- **Rules:** `create_project` R3, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Line 3 refit", description="New press line", budget=Decimal("2500.50"), deadline=datetime(2026, 6, 30, 17, 0, 0)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, Project)`.
2. returns: `result.id is not None`.
3. re-read the returned row: `factory_id == F1.id`, `name == "Line 3 refit"`, `description == "New press line"`.
4. re-read the returned row: `budget == Decimal("2500.50")`, `deadline == datetime(2026, 6, 30, 17, 0, 0)`.
5. re-read the returned row: `workspace_id == W1.id`, `created_by == U2.id`, `created_at is not None`.
6. count: `projects` rows with `workspace_id == W1.id`: exactly 1.

### PRJM-C-02 — a new project is live, workspace-visible, planning, low priority, with no other stamps
- **Rules:** `create_project` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `is_active is True`, `is_deleted is False`, `visibility == "workspace"`.
3. re-read the returned row: `val(status) == "PLANNING"`, `val(priority) == "LOW"`.
4. re-read the returned row: `budget is None`, `deadline is None`, `start_date is None`, `end_date is None`.
5. re-read the returned row: `updated_by is None`, `updated_at is None`.
6. re-read the returned row: `deleted_by is None`, `deleted_at is None`.

### PRJM-C-03 — the creator becomes a member and a created event is logged
- **Rules:** `create_project` R3a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: members_of(result) has exactly 1 row.
3. re-read that member: `user_id == U2.id`, `assigned_by == U2.id`, `workspace_id == W1.id`.
4. count: events_of(result) has exactly 1 row.
5. re-read that event: `event_type == "created"`, `description == 'Created project "Roof job"'`, `performed_by == U2.id`, `workspace_id == W1.id`.
6. re-read that event: `metadata_json is None`.

### PRJM-C-04 — any status may be given at creation, COMPLETED included
- **Rules:** `create_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", status=ProjectStatusEnum.COMPLETED), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `val(status) == "COMPLETED"`.

### PRJM-C-05 — an inactive but live factory is accepted
- **Rules:** `create_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=FI.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `factory_id == FI.id`.

### PRJM-C-06 — a soft-deleted factory is 400
- **Rules:** `create_project` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `PM.create_project(db, project_data=ProjectCreate(factory_id=FD.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot create project for deleted factory"`.
4. session: `not db.new`.
5. nothing written.

### PRJM-C-07 — an unknown factory is 404
- **Rules:** `create_project` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `PM.create_project(db, project_data=ProjectCreate(factory_id=MISSING, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 999999999 not found"`.
4. nothing written.

### PRJM-C-08 — factory id 0 is 404
- **Rules:** `create_project` R1
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `PM.create_project(db, project_data=ProjectCreate(factory_id=0, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Factory with ID 0 not found"`.
4. nothing written.

### PRJM-C-09 — a W0 factory (lower id) is 404 in W1
- **Rules:** `create_project` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `PM.create_project(db, project_data=ProjectCreate(factory_id=F0.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F0.id} not found"`.
4. session: `not db.new`.
5. nothing written.

### PRJM-C-10 — a W2 factory (higher id) is 404 in W1
- **Rules:** `create_project` R1 (HR-16)
- **Kind:** isolation
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `PM.create_project(db, project_data=ProjectCreate(factory_id=F9.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Factory with ID {F9.id} not found"`.
4. session: `not db.new`.
5. nothing written.

### PRJM-C-11 — the name's inner spaces and case are kept
- **Rules:** `create_project` R4 (HR-1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Line  3 REFIT", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Line  3 REFIT"`.

### PRJM-C-12 — the name is stored trimmed, also in the created event
- **Rules:** `create_project` R4 [BUG-1951]
- **Kind:** bug
- **Expect:** xfail BUG-1951
- **Fails today on:** Then 2 (stored as typed, with the spaces)

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="  Line 3 refit ", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `name == "Line 3 refit"`.
3. re-read the one event of the returned row: `description == 'Created project "Line 3 refit"'`.

### PRJM-C-13 — an empty name is refused by the schema
- **Rules:** `create_project` R4 [BUG-1951]
- **Kind:** bug
- **Expect:** xfail BUG-1951
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No projects exist.

**When**
- build `ProjectCreate(factory_id=F1.id, name="", description="Main")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"name" in str(exc.value)`.

### PRJM-C-14 — a name of only spaces is refused by the schema
- **Rules:** `create_project` R4 [BUG-1951]
- **Kind:** bug
- **Expect:** xfail BUG-1951
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No projects exist.

**When**
- build `ProjectCreate(factory_id=F1.id, name="   ", description="Main")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"name" in str(exc.value)`.

### PRJM-C-15 — a one-letter name is accepted by the schema
- **Rules:** `create_project` R4 (other side of the blank boundary)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = ProjectCreate(factory_id=F1.id, name="A", description="Main")` (target `schema`).

**Then**
1. returns: `result.name == "A"`.

### PRJM-C-16 — the description is kept as typed, empty or padded
- **Rules:** `create_project` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description=" two coats "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `description == " two coats "`.

### PRJM-C-17 — an empty description is stored as an empty string
- **Rules:** `create_project` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description=""), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `description == ""`.

### PRJM-C-18 — a budget of 0 is accepted
- **Rules:** `create_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `budget == Decimal("0.00")`.

### PRJM-C-19 — a budget of null is accepted
- **Rules:** `create_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `budget is None`.

### PRJM-C-20 — a budget with two decimals is stored exactly
- **Rules:** `create_project` R5 (HR-15: no rounding of an accepted value)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("1000.01")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `budget == Decimal("1000.01")`.

### PRJM-C-21 — a budget with 13 integer digits is stored exactly
- **Rules:** `create_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("9999999999999.99")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. re-read the returned row: `budget == Decimal("9999999999999.99")`.

### PRJM-C-22 — a negative budget is refused by the schema
- **Rules:** `create_project` R5 [BUG-1962]
- **Kind:** bug
- **Expect:** xfail BUG-1962
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No projects exist.

**When**
- build `ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("-5"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"budget" in str(exc.value)`.

### PRJM-C-23 — a budget of -0.01 is refused by the schema
- **Rules:** `create_project` R5 [BUG-1962]
- **Kind:** bug
- **Expect:** xfail BUG-1962
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. No projects exist.

**When**
- build `ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"budget" in str(exc.value)`.

### PRJM-C-24 — a budget with three decimals is refused by the schema
- **Rules:** `create_project` R5 [BUG-1963]
- **Kind:** bug
- **Expect:** xfail BUG-1963
- **Fails today on:** Then 1 (no error is raised; the database would round it to 1000.01)

**Given**
1. No projects exist.

**When**
- build `ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("1000.005"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"budget" in str(exc.value)`.

### PRJM-C-25 — a budget with 14 integer digits is refused by the schema
- **Rules:** `create_project` R5 [BUG-1963]
- **Kind:** bug
- **Expect:** xfail BUG-1963
- **Fails today on:** Then 1 (no error is raised; the flush would fail)

**Given**
1. No projects exist.

**When**
- build `ProjectCreate(factory_id=F1.id, name="Roof job", description="Main", budget=Decimal("10000000000000.00"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"budget" in str(exc.value)`.

### PRJM-C-26 — the plan's project limit is not checked
- **Rules:** `create_project` R6
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `plan = db.get(SubscriptionPlan, W1.subscription_plan_id)`; `plan.max_projects = 1`; `db.flush()`.
2. PA = proj `name "First job"`.

**When**
- `result = PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Second job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id is not None`.
2. count: `projects` rows with `workspace_id == W1.id`: exactly 2.

### PRJM-C-27 — create_project does not commit
- **Rules:** `create_project` R3a
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. No projects exist.

**When**
- Rolled back: `PM.create_project(db, project_data=ProjectCreate(factory_id=F1.id, name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. count: `projects` rows with `workspace_id == W1.id`: exactly 0.
3. count: `project_events` rows with `workspace_id == W1.id`: exactly 0.

## `ProjectManager.get_project`

### PRJM-G-01 — returns the project to a plain member
- **Rules:** `get_project` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. P = proj `name "Roof job"`.
3. P9 = W2 proj `name "Nine"`.

**When**
- `result = PM.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.name == "Roof job"`.

### PRJM-G-02 — a private project is returned to its creator
- **Rules:** `get_project` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`, but `created_by UG.id`.

**When**
- `result = PM.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == P.id`.

### PRJM-G-03 — a private project the caller may not open is 403
- **Rules:** `get_project` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `PM.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.

### PRJM-G-04 — an unknown id is 404
- **Rules:** `get_project` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `PM.get_project(db, project_id=MISSING, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == "Project with ID 999999999 not found"`.

### PRJM-G-05 — a W2 project is 404 in W1
- **Rules:** `get_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. P9 = W2 proj `name "Nine"`.

**When**
- `PM.get_project(db, project_id=P9.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.

### PRJM-G-06 — a soft-deleted project is 404 by default
- **Rules:** `get_project` R2 [BUG-1954]; `require_project_access` R3
- **Kind:** bug
- **Expect:** xfail BUG-1954
- **Fails today on:** Then 1 (no error: the deleted project is returned)

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `PM.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P.id} not found"`.

### PRJM-G-07 — include_deleted=True returns a soft-deleted project
- **Rules:** `get_project` R2 [BUG-1954]
- **Kind:** bug
- **Expect:** xfail BUG-1954
- **Fails today on:** Then 1 (the call raises TypeError: no `include_deleted` parameter today)

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `result = PM.get_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id, include_deleted=True)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.is_deleted is True`.

## `ProjectManager.delete_project`

### PRJM-D-01 — soft-deletes the project, stamps it, logs deleted, returns it
- **Rules:** `delete_project` R3
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is True`, `deleted_at == NOW`, `deleted_by == U2.id`.
3. re-read P: `is_active is True`.
4. count: events_of(P) has exactly 1 row.
5. re-read that event: `event_type == "deleted"`, `description == 'Deactivated project "Roof job"'`, `performed_by == U2.id`, `workspace_id == W1.id`.
6. re-read that event: `metadata_json is None`.

### PRJM-D-02 — an inactive project stays inactive when deleted
- **Rules:** `delete_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `is_active False`.

**When**
- `result = PM.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is True`, `is_active is False`.

### PRJM-D-03 — members, components and earlier events are untouched; nothing blocks the delete
- **Rules:** `delete_project` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.
2. MG = pmem(P, UG).
3. C = comp(P, "Roof").
4. E1 = ev(P, "created", T1, U1.id).

**When**
- `result = PM.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. unchanged: unchanged(MG).
3. unchanged: unchanged(C).
4. unchanged: unchanged(E1).
5. count: events_of(P) has exactly 2 rows.

### PRJM-D-04 — a plain member may delete a workspace-visible project
- **Rules:** `delete_project` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `is_deleted is True`, `deleted_by == UG.id`.

### PRJM-D-05 — an already deleted project is 400
- **Rules:** `delete_project` R2
- **Kind:** error
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `PM.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Project is already deleted"`.
4. session: `P not in db.dirty and not db.new`.
5. unchanged: unchanged(P).
6. nothing written.

### PRJM-D-06 — a caller who may not open the private project is 403
- **Rules:** `delete_project` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `PM.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.
4. unchanged: unchanged(P).
5. nothing written.

### PRJM-D-07 — another workspace's project is 404
- **Rules:** `delete_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.

**When**
- `PM.delete_project(db, project_id=P0.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P0.id} not found"`.
4. unchanged: unchanged(P0).
5. nothing written.

### PRJM-D-08 — delete_project does not commit
- **Rules:** `delete_project` R3
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- Rolled back: `PM.delete_project(db, project_id=P.id, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read P: `is_deleted is False`.
3. count: events_of(P) has exactly 0 rows.
## `ProjectManager.list_projects`

### PRJM-L-01 — a privileged caller gets every live project of the workspace, private ones included
- **Rules:** `list_projects` R6, Returns
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. PA = proj `name "Alpha"`.
3. PV = private proj `name "Vault"`.
4. P9 = W2 proj `name "Nine"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `isinstance(result, list)`.
2. returns: `idset(result) == {PA.id, PV.id}`.

### PRJM-L-02 — a plain caller gets workspace projects and the private ones they may open
- **Rules:** `list_projects` R7
- **Kind:** happy
- **Expect:** pass

**Given**
1. PA = proj `name "Alpha"`.
2. PV = private proj `name "Vault"`.
3. PM1 = private proj `name "Member Job"`.
4. PC = private proj `name "Own Job"`, but `created_by UG.id`.
5. pmem(PM1, UG).

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `idset(result) == {PA.id, PM1.id, PC.id}`.

### PRJM-L-03 — the workspace owner with no membership gets private projects too
- **Rules:** `list_projects` R6; `_is_privileged` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; set_owner(W1, UX).
2. PA = proj `name "Alpha"`.
3. PV = private proj `name "Vault"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UX.id)`.

**Then**
1. returns: `idset(result) == {PA.id, PV.id}`.

### PRJM-L-04 — owning W0 does not show W1's private projects
- **Rules:** `list_projects` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. set_owner(W0, UG).
2. PA = proj `name "Alpha"`.
3. PV = private proj `name "Vault"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `idset(result) == {PA.id}`.

### PRJM-L-05 — role owner in W2 (row built before the W1 row) does not show W1's private projects
- **Rules:** `list_projects` R7
- **Kind:** isolation
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`.
2. member(UX, "owner", ws=W2), flushed first.
3. member(UX, "ground-team"), flushed second.
4. PA = proj `name "Alpha"`.
5. PV = private proj `name "Vault"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UX.id)`.

**Then**
1. returns: `idset(result) == {PA.id}`.

### PRJM-L-06 — a suspended member with role owner sees only what a plain member sees
- **Rules:** `list_projects` R6, R7
- **Kind:** boundary
- **Expect:** pass

**Given**
1. `UX = make_profile(db, name="Omar Ali")`; member(UX, "owner", status="suspended").
2. PA = proj `name "Alpha"`.
3. PV = private proj `name "Vault"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UX.id)`.

**Then**
1. returns: `idset(result) == {PA.id}`.

### PRJM-L-07 — hidden private projects ahead of the page do not use its places *(revised 2026-11-27, order sweep)*
- **Rules:** `list_projects` R7 [BUG-1958]
- **Kind:** bug
- **Expect:** xfail BUG-1958 (non-strict): fails only when physical order puts the filtered-out row on the page; strict proof is PRJM-L-08 (skip).
- **Fails today on:** Then 1 (the page of the first two projects is filtered after paging: `[]`)

**Given**
1. H1 = private proj `name "Aa"`.
2. H2 = private proj `name "Ab"`.
3. H3 = private proj `name "Ac"`.
4. V1 = proj `name "Ba"`.
5. V2 = proj `name "Bb"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UG.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {V1.id, V2.id}`.

### PRJM-L-08 — a hidden private project ahead of the skipped row is not counted by skip
- **Rules:** `list_projects` R7 [BUG-1958]
- **Kind:** bug
- **Expect:** xfail BUG-1958
- **Fails today on:** Then 1 (skip drops the hidden row, then the filter: both visible rows come back)

**Given**
1. H = private proj `name "Aa"`.
2. V1 = proj `name "Ba"`.
3. V2 = proj `name "Bb"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UG.id, skip=1, limit=10)`.

**Then**
1. returns: `idset(result) == {V2.id}`.

### PRJM-L-09 — with a factory filter, hidden private projects do not use the page's places
- **Rules:** `list_projects` R1, R7 [BUG-1958]
- **Kind:** bug
- **Expect:** xfail BUG-1958 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (paged before the filter; the factory read has no order today, so the page rests on physical order)

**Given**
1. H1 = private proj `name "Aa"`.
2. H2 = private proj `name "Ab"`.
3. H3 = private proj `name "Ac"`.
4. V1 = proj `name "Ba"`.
5. V2 = proj `name "Bb"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UG.id, factory_id=F1.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {V1.id, V2.id}`.

### PRJM-L-10 — with a status filter, hidden private projects do not use the page's places
- **Rules:** `list_projects` R2, R7 [BUG-1958]
- **Kind:** bug
- **Expect:** xfail BUG-1958 (non-strict)
- **Author:** claude
- **Fails today on:** Then 1 (paged before the filter; the status read has no order today, so the page rests on physical order)

**Given**
1. H1 = private proj `name "Aa"`.
2. H2 = private proj `name "Ab"`.
3. H3 = private proj `name "Ac"`.
4. V1 = proj `name "Ba"`.
5. V2 = proj `name "Bb"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UG.id, status="PLANNING", skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {V1.id, V2.id}`.

### PRJM-L-11 — a privileged caller's page is read as is, private projects in it *(revised 2026-11-27, order sweep)*
- **Rules:** `list_projects` R6 [BUG-100]
- **Kind:** boundary
- **Expect:** xfail BUG-100 (non-strict): the unfiltered read is the base workspace list, which has no `ORDER BY` (BUG-100), so the first page of 2 is {H1, H2} only when the physical order happens to match (same reason as PRJM-L-10). Then 1 failed when the order sweep forced the other order. Revisit after launch.

**Given**
1. H1 = private proj `name "Aa"`.
2. H2 = private proj `name "Ab"`.
3. H3 = private proj `name "Ac"`.
4. V1 = proj `name "Ba"`.
5. V2 = proj `name "Bb"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, skip=0, limit=2)`.

**Then**
1. returns: `idset(result) == {H1.id, H2.id}`.

### PRJM-L-12 — factory_id filters to that factory of the workspace
- **Rules:** `list_projects` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P0 = W0 proj `name "Zero"`.
2. A = proj `name "Alpha"`.
3. B = proj `name "Beta"`, but `factory_id F2.id`.
4. C = proj `name "Gamma"`.
5. P9 = W2 proj `name "Nine"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id)`.

**Then**
1. returns: `idset(result) == {A.id, C.id}`.

### PRJM-L-13 — factory_id 0 filters and returns nothing
- **Rules:** `list_projects` R1 [BUG-1959]
- **Kind:** bug
- **Expect:** xfail BUG-1959
- **Fails today on:** Then 1 (0 is taken as no filter: every project is returned)

**Given**
1. A = proj `name "Alpha"`.
2. B = proj `name "Beta"`, but `factory_id F2.id`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=0)`.

**Then**
1. returns: `result == []`.

### PRJM-L-14 — factory and status together apply both
- **Rules:** `list_projects` R1a [BUG-1960]
- **Kind:** bug
- **Expect:** xfail BUG-1960
- **Fails today on:** Then 1 (the status is ignored: AC of F1 is returned too)

**Given**
1. AP = proj `name "Alpha"`.
2. AC = proj `name "Beta"`, but `status ProjectStatusEnum.COMPLETED`.
3. BP = proj `name "Gamma"`, but `factory_id F2.id`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, status="PLANNING")`.

**Then**
1. returns: `idset(result) == {AP.id}`.

### PRJM-L-15 — factory and status together: the factory still filters
- **Rules:** `list_projects` R1, R1a
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AP = proj `name "Alpha"`.
2. BP = proj `name "Gamma"`, but `factory_id F2.id`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, factory_id=F1.id, status="PLANNING")`.

**Then**
1. returns: `idset(result) == {AP.id}`.

### PRJM-L-16 — a status filter alone returns that status across factories
- **Rules:** `list_projects` R2
- **Kind:** happy
- **Expect:** pass

**Given**
1. AP = proj `name "Alpha"`.
2. AC = proj `name "Beta"`, but `status ProjectStatusEnum.COMPLETED`.
3. BP = proj `name "Gamma"`, but `factory_id F2.id`.
4. P9 = W2 proj `name "Nine"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, status="PLANNING")`.

**Then**
1. returns: `idset(result) == {AP.id, BP.id}`.

### PRJM-L-17 — an empty status means no filter
- **Rules:** `list_projects` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. AP = proj `name "Alpha"`.
2. AC = proj `name "Beta"`, but `status ProjectStatusEnum.COMPLETED`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, status="")`.

**Then**
1. returns: `idset(result) == {AP.id, AC.id}`.

### PRJM-L-18 — a status that is not an enum value raises ValueError in the manager
- **Rules:** `list_projects` R2 (BUG-1961 is fixed at the endpoint; the manager keeps its conversion)
- **Kind:** error
- **Expect:** pass

**Given**
1. AP = proj `name "Alpha"`.

**When**
- `PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, status="planning")`.

**Then**
1. raises: `ValueError`.

### PRJM-L-19 — without filters a soft-deleted project is not listed
- **Rules:** `list_projects` R3 [BUG-1955]
- **Kind:** bug
- **Expect:** xfail BUG-1955
- **Fails today on:** Then 1 (the raw workspace read lists it)

**Given**
1. A = proj `name "Alpha"`.
2. X = deleted proj `name "Old"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### PRJM-L-20 — without filters a soft-deleted project takes no place on the page
- **Rules:** `list_projects` R3 [BUG-1955]
- **Kind:** bug
- **Expect:** xfail BUG-1955
- **Fails today on:** Then 1 (skip drops the deleted row: both live rows come back)

**Given**
1. X = deleted proj `name "Aa"`.
2. V1 = proj `name "Ba"`.
3. V2 = proj `name "Bb"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, skip=1, limit=10)`.

**Then**
1. returns: `idset(result) == {V2.id}`.

### PRJM-L-21 — without filters an inactive project is listed
- **Rules:** `list_projects` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = proj `name "Alpha"`.
2. I = proj `name "Idle"`, but `is_active False`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `idset(result) == {A.id, I.id}`.

### PRJM-L-22 — without filters projects of a soft-deleted factory are not listed
- **Rules:** `list_projects` R4 [BUG-1956]
- **Kind:** bug
- **Expect:** xfail BUG-1956
- **Fails today on:** Then 1 (the factory is not looked at)

**Given**
1. A = proj `name "Alpha"`.
2. K = proj `name "Kiln job"`, but `factory_id FD.id`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.

### PRJM-L-23 — without filters projects of an inactive factory are listed
- **Rules:** `list_projects` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. A = proj `name "Alpha"`.
2. K = proj `name "Idle job"`, but `factory_id FI.id`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `idset(result) == {A.id, K.id}`.

### PRJM-L-24 — without filters the list is ordered by name, case-insensitive
- **Rules:** `list_projects` R5 [BUG-1957]
- **Kind:** bug
- **Expect:** xfail BUG-1957
- **Fails today on:** Then 1 (ordered by id: Zulu, apple, Banana)

**Given**
1. Z = proj `name "Zulu"`.
2. A = proj `name "apple"`.
3. B = proj `name "Banana"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `names(result) == ["apple", "Banana", "Zulu"]`.

### PRJM-L-25 — names equal but for case are ordered by id
- **Rules:** `list_projects` R5 [BUG-1957]
- **Kind:** bug
- **Expect:** xfail BUG-1957
- **Fails today on:** Then 1 (ordered by id: beta, Beta, Alpha)

**Given**
1. B1 = proj `name "beta"`.
2. B2 = proj `name "Beta"`.
3. A = proj `name "Alpha"`.

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `[r.id for r in result] == [A.id, B1.id, B2.id]`.

### PRJM-L-26 — the default limit is 100
- **Rules:** `list_projects` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `len(result) == 100`.

### PRJM-L-27 — limit 1000 returns all 101
- **Rules:** `list_projects` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, limit=1000)`.

**Then**
1. returns: `len(result) == 101`.

### PRJM-L-28 — skip 100 of 101 leaves one
- **Rules:** `list_projects` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. bulk(101, "P").

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, skip=100, limit=1000)`.

**Then**
1. returns: `len(result) == 1`.

### PRJM-L-29 — a negative skip fails in the database
- **Rules:** `list_projects` R5
- **Kind:** error
- **Expect:** pass

**Given**
1. A = proj `name "Alpha"`.

**When**
- `PM.list_projects(db, workspace_id=W1.id, user_id=U2.id, skip=-1)`.

**Then**
1. raises: `DataError`.

### PRJM-L-30 — listing leaves the caller's unflushed edit in place
- **Rules:** `list_projects` R7 (reads only)
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. A = proj `name "Alpha"`.
2. PV = private proj `name "Vault"`.
3. `A.description = "Edited"` (not flushed).

**When**
- `result = PM.list_projects(db, workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `idset(result) == {A.id}`.
2. session: `A in db.dirty`.
3. session: `len(db.dirty) == 1`.
4. session: `not db.new and not db.deleted`.
## `ProjectManager.update_project`

### PRJM-U-01 — changes the sent fields, stamps, and logs one updated event in field order
- **Rules:** `update_project` R2, R4, R6, R9
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(budget=Decimal("1250.75"), description="Two coats", name="Roof refit"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `result.name == "Roof refit"`.
3. re-read P: `name == "Roof refit"`, `description == "Two coats"`, `budget == Decimal("1250.75")`.
4. re-read P: `updated_by == U2.id`, `updated_at == NOW`.
5. count: events_of(P) has exactly 1 row.
6. re-read that event: `event_type == "updated"`, `description == "Updated project details"`, `performed_by == U2.id`, `workspace_id == W1.id`.
7. re-read that event: `metadata_json == {"changes": [{"field": "name", "label": "Name", "from_value": "Roof job", "to_value": "Roof refit"}, {"field": "description", "label": "Description", "from_value": "Main", "to_value": "Two coats"}, {"field": "budget", "label": "Budget", "from_value": "1000.00", "to_value": "1250.75"}]}`.

### PRJM-U-02 — a status change alone logs one status_updated event
- **Rules:** `update_project` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(status=ProjectStatusEnum.IN_PROGRESS), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `val(result.status) == "IN_PROGRESS"`.
2. count: events_of(P) has exactly 1 row.
3. re-read that event: `event_type == "status_updated"`, `description == "Changed project status"`, `performed_by == U2.id`.
4. re-read that event: `metadata_json == {"changes": [{"field": "status", "label": "Status", "from_value": "PLANNING", "to_value": "IN_PROGRESS"}]}`.

### PRJM-U-03 — status and another field changed: two events, status first
- **Rules:** `update_project` R4
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="Roof refit", status=ProjectStatusEnum.ON_HOLD), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. returns: `[e.event_type for e in events_of(P)] == ["status_updated", "updated"]`.
3. re-read the first event: `metadata_json == {"changes": [{"field": "status", "label": "Status", "from_value": "PLANNING", "to_value": "ON_HOLD"}]}`.
4. re-read the second event: `metadata_json == {"changes": [{"field": "name", "label": "Name", "from_value": "Roof job", "to_value": "Roof refit"}]}`.

### PRJM-U-04 — fields not sent are unchanged
- **Rules:** `update_project` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")`, `deadline datetime(2026, 6, 30, 17, 0, 0)`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(description="Two coats"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `name == "Roof job"`, `budget == Decimal("1000.00")`, `deadline == datetime(2026, 6, 30, 17, 0, 0)`.
3. re-read P: `val(status) == "PLANNING"`, `factory_id == F1.id`, `visibility == "workspace"`.

### PRJM-U-05 — the same values: no event
- **Rules:** `update_project` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="Roof job", description="Main", budget=Decimal("1000")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: events_of(P) has exactly 0 rows.
3. re-read P: `name == "Roof job"`, `budget == Decimal("1000.00")`.

### PRJM-U-06 — the same values do not stamp the project
- **Rules:** `update_project` R9 [BUG-1952]
- **Kind:** bug
- **Expect:** xfail BUG-1952
- **Fails today on:** Then 2 (stamped although nothing changed)

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="Roof job", description="Main"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `updated_by is None`, `updated_at is None`.

### PRJM-U-07 — an empty update: no event
- **Rules:** `update_project` R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. count: events_of(P) has exactly 0 rows.

### PRJM-U-08 — an empty update does not stamp the project
- **Rules:** `update_project` R9 [BUG-1952]
- **Kind:** bug
- **Expect:** xfail BUG-1952
- **Fails today on:** Then 2 (stamped although nothing was sent)

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `updated_by is None`, `updated_at is None`.

### PRJM-U-09 — a deadline moved by hours in one day is logged with the same date twice
- **Rules:** `update_project` R4; `_collect_field_changes` R2
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `deadline datetime(2026, 3, 1, 9, 0, 0)`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(deadline=datetime(2026, 3, 1, 17, 0, 0)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `deadline == datetime(2026, 3, 1, 17, 0, 0)`.
3. re-read the one event of P: `event_type == "updated"`.
4. re-read the one event of P: `metadata_json == {"changes": [{"field": "deadline", "label": "Deadline", "from_value": "2026-03-01", "to_value": "2026-03-01"}]}`.

### PRJM-U-10 — start and end dates are set and logged, end before start accepted
- **Rules:** `update_project` R3, R4
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(start_date=datetime(2026, 5, 10, 8, 0, 0), end_date=datetime(2026, 5, 1, 8, 0, 0)), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `start_date == datetime(2026, 5, 10, 8, 0, 0)`, `end_date == datetime(2026, 5, 1, 8, 0, 0)`.
3. re-read the one event of P: `metadata_json == {"changes": [{"field": "start_date", "label": "Start date", "from_value": None, "to_value": "2026-05-10"}, {"field": "end_date", "label": "End date", "from_value": None, "to_value": "2026-05-01"}]}`.

### PRJM-U-11 — any status may follow any status: CANCELLED to IN_PROGRESS
- **Rules:** `update_project` R3
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `status ProjectStatusEnum.CANCELLED`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(status=ProjectStatusEnum.IN_PROGRESS), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `val(result.status) == "IN_PROGRESS"`.
2. re-read P: `val(status) == "IN_PROGRESS"`.
3. re-read the one event of P: `metadata_json == {"changes": [{"field": "status", "label": "Status", "from_value": "CANCELLED", "to_value": "IN_PROGRESS"}]}`.

### PRJM-U-12 — ProjectUpdate has no factory or visibility field
- **Rules:** `update_project` R5
- **Kind:** boundary
- **Expect:** pass

**Given**
1. Nothing beyond the standing rows.

**When**
- `result = set(ProjectUpdate.model_fields)` (target `schema`).

**Then**
1. returns: `"factory_id" not in result`.
2. returns: `"visibility" not in result`.

### PRJM-U-13 — a plain member may edit a workspace-visible project
- **Rules:** `update_project` R1
- **Kind:** happy
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(description="Two coats"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. returns: `result.description == "Two coats"`.
2. re-read P: `updated_by == UG.id`.
3. re-read the one event of P: `performed_by == UG.id`.

### PRJM-U-14 — a soft-deleted project is 400, nothing written
- **Rules:** `update_project` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = deleted proj `name "Gone"`.

**When**
- `PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="Back"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 400`.
3. raises: `exc.value.detail == "Cannot update deleted project"`.
4. session: `P not in db.dirty`.
5. unchanged: unchanged(P).
6. nothing written.

### PRJM-U-15 — a caller who may not open the private project is 403
- **Rules:** `update_project` R1
- **Kind:** error
- **Expect:** pass

**Given**
1. P = private proj `name "Secret"`.

**When**
- `PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="Mine"), workspace_id=W1.id, user_id=UG.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 403`.
3. raises: `exc.value.detail == "You do not have access to this project"`.
4. unchanged: unchanged(P).
5. nothing written.

### PRJM-U-16 — another workspace's project is 404
- **Rules:** `update_project` R1
- **Kind:** isolation
- **Expect:** pass

**Given**
1. P9 = W2 proj `name "Nine"`.

**When**
- `PM.update_project(db, project_id=P9.id, project_data=ProjectUpdate(name="Mine"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. raises: `HTTPException`.
2. raises: `exc.value.status_code == 404`.
3. raises: `exc.value.detail == f"Project with ID {P9.id} not found"`.
4. unchanged: unchanged(P9).
5. nothing written.

### PRJM-U-17 — an explicit null clears the budget
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 2 (the null is dropped: the budget stays 1000.00)

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(budget=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `budget is None`.

### PRJM-U-18 — an explicit null clears the deadline
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 2 (the null is dropped: the deadline stays)

**Given**
1. P = proj `name "Roof job"`, but `deadline datetime(2026, 6, 30, 17, 0, 0)`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(deadline=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `deadline is None`.

### PRJM-U-19 — an explicit null clears the start date
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 2 (the null is dropped: the start date stays)

**Given**
1. P = proj `name "Roof job"`, but `start_date datetime(2026, 5, 1, 8, 0, 0)`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(start_date=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `start_date is None`.

### PRJM-U-20 — an explicit null clears the end date
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 2 (the null is dropped: the end date stays)

**Given**
1. P = proj `name "Roof job"`, but `end_date datetime(2026, 5, 31, 17, 0, 0)`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(end_date=None), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `end_date is None`.

### PRJM-U-21 — null for name is refused by ProjectUpdate
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(name=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"name" in str(exc.value)`.

### PRJM-U-22 — null for description is refused by ProjectUpdate
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(description=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"description" in str(exc.value)`.

### PRJM-U-23 — null for priority is refused by ProjectUpdate
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(priority=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"priority" in str(exc.value)`.

### PRJM-U-24 — null for status is refused by ProjectUpdate
- **Rules:** `update_project` R2a [BUG-1953]
- **Kind:** bug
- **Expect:** xfail BUG-1953
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(status=None)` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"status" in str(exc.value)`.

### PRJM-U-25 — the name's inner spaces and case are kept
- **Rules:** `update_project` R7 (HR-1)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="Roof  JOB 2"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `name == "Roof  JOB 2"`.

### PRJM-U-26 — a sent name is stored trimmed
- **Rules:** `update_project` R7 [BUG-1951]
- **Kind:** bug
- **Expect:** xfail BUG-1951
- **Fails today on:** Then 2 (stored as typed, with the spaces)

**Given**
1. P = proj `name "Roof job"`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="  Roof refit "), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `name == "Roof refit"`.

### PRJM-U-27 — a name of only spaces is refused by ProjectUpdate
- **Rules:** `update_project` R7 [BUG-1951]
- **Kind:** bug
- **Expect:** xfail BUG-1951
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(name="  ")` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"name" in str(exc.value)`.

### PRJM-U-28 — a budget of 0 is accepted on update
- **Rules:** `update_project` R8
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(budget=Decimal("0")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `budget == Decimal("0.00")`.

### PRJM-U-29 — a negative budget is refused by ProjectUpdate
- **Rules:** `update_project` R8 [BUG-1962]
- **Kind:** bug
- **Expect:** xfail BUG-1962
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(budget=Decimal("-0.01"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"budget" in str(exc.value)`.

### PRJM-U-30 — a budget with three decimals is refused by ProjectUpdate
- **Rules:** `update_project` R8 [BUG-1963]
- **Kind:** bug
- **Expect:** xfail BUG-1963
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(budget=Decimal("1000.005"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"budget" in str(exc.value)`.

### PRJM-U-31 — a budget with 14 integer digits is refused by ProjectUpdate
- **Rules:** `update_project` R8 [BUG-1963]
- **Kind:** bug
- **Expect:** xfail BUG-1963
- **Fails today on:** Then 1 (no error is raised)

**Given**
1. Nothing beyond the standing rows.

**When**
- build `ProjectUpdate(budget=Decimal("10000000000000.00"))` (target `schema`).

**Then**
1. raises: `ValidationError`.
2. raises: `"budget" in str(exc.value)`.

### PRJM-U-32 — a one-decimal budget is logged in its stored two-decimal form
- **Rules:** `update_project` R8 [BUG-1963]
- **Kind:** bug
- **Expect:** xfail BUG-1963
- **Fails today on:** Then 3 (the entry shows the typed form "1000.5")

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(budget=Decimal("1000.5")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `budget == Decimal("1000.50")`.
3. re-read the one event of P: `metadata_json == {"changes": [{"field": "budget", "label": "Budget", "from_value": "1000.00", "to_value": "1000.50"}]}`.

### PRJM-U-33 — update_project does not commit
- **Rules:** `update_project` R6
- **Kind:** side-effect
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`.

**When**
- Rolled back: `PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(name="Roof refit"), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. mock called: `cm.call_count == 0`.
2. re-read P: `name == "Roof job"`.
3. count: events_of(P) has exactly 0 rows.

### PRJM-U-34 — a one-decimal budget is stored with two decimals
- **Rules:** `update_project` R8 (column keeps 2 decimals; HR-15)
- **Kind:** boundary
- **Expect:** pass

**Given**
1. P = proj `name "Roof job"`, but `budget Decimal("1000.00")`.

**When**
- `result = PM.update_project(db, project_id=P.id, project_data=ProjectUpdate(budget=Decimal("1000.5")), workspace_id=W1.id, user_id=U2.id)`.

**Then**
1. returns: `result.id == P.id`.
2. re-read P: `budget == Decimal("1000.50")`.
3. count: events_of(P) has exactly 1 row.

## Deferred to other specs
| Rule | Owner | What must be tested there |
|---|---|---|
| `list_projects` R2 [BUG-1961] | `GET /projects/` (`app/api/v1/endpoints/projects.py`), FU-1 (a) | `project_status=planning` / `bogus` answers 422 (400 today per BUG-461), the manager is not reached; the five enum values pass. |
| Integration-only: `HTTPException` mapping | `ProjectService` / project endpoints | 403 `You do not have access to this project`, 404 `Project with ID <id> not found`, 404 `Project component not found`, 400s and 409 reach the client with those texts. |
| FU-1 (b) | `POST /projects/` | The catch-all answers 400 with `str(e)` (BUG-037 pattern): a database error's text must not reach the client. |
| FU-1 (c) | `ProjectService.list_members` | Member profiles and memberships read together (`n-plus-one-read`). |
| FU-1 (d), `get_project` R2 | `ProjectService.get_project` | `include_deleted` reachable when a caller needs it. |
| `require_project_access` R3 for components | component / item / note / task / miscellaneous cost / ledger services | A component page of a soft-deleted project answers 404 (BUG-1278). |
| BUG-1280 | `WorkspaceManager.remove_member_from_workspace` | Someone removed from the workspace loses their `project_members` rows, one `member_removed` event per project. |

## Spec gaps
| # | Where | What is missing | How it blocked the design |
|---|---|---|---|
| 1 | Facts / Notes | The module of `ProjectCreate` / `ProjectUpdate` is not named. | Conventions use `app.schemas.project`; a wrong path fails every test at import. |
| 2 | `create_project` R3, `update_project` R2 | `priority`: enum name, module and values other than `LOW` are not given. | No card changes the priority; the default is checked as `val(priority) == "LOW"`; the `Priority` label is covered only by `PROJECT_LOG_FIELDS` (CF-10). |
| 3 | `set_visibility` signature | The type of `visibility` (enum member or text) is not stated. | Cards pass `ProjectVisibilityEnum` members; stored and logged values are checked as text. |
| 4 | `require_project_access` R3 | After BUG-1278 / BUG-1954 the method's own default for a deleted project, and the option's name, are not given ("e.g. `include_deleted`"). | R3 is checked only through its callers; no card calls `require_project_access` on a deleted project. |
| 5 | `list_events` R3 | "the profile is gone": whether `performed_by` has a foreign key (can a profile be gone?) is not given. | No card for a gone profile; `performed_by None` → `None` is covered. |
| 6 | `create_project` R3 | Which `ProjectCreate` fields are required (is `description` optional?) and the type of `deadline` (date or datetime). | Every card sends `description`; deadlines are naive datetimes. |
| 7 | Facts | What a factory's soft delete writes besides `is_deleted` (HR-4 "real states"). | FD carries `is_deleted True` only, as in the project DAO cases. |

## Coverage matrix
| Callable | Rule / Error row | Cases |
|---|---|---|
| `_visibility_value` | R1 | PRJM-VV-01 … VV-05, CA-02 |
| `_is_workspace_owner` | R1 | PRJM-WO-01 … WO-07, CA-21, CA-22 |
| `_is_privileged` | R1 | PRJM-PV-01, PV-15, CA-04, L-03 |
| `_is_privileged` | R2 | PRJM-PV-02 … PV-18, CA-11, CA-12, CA-15, L-05, L-06 |
| `can_access_project` | R1 | PRJM-CA-01, CA-02, CA-26 … CA-28 |
| `can_access_project` | R2 | PRJM-CA-03 … CA-22, CA-29, CA-32, CA-33 |
| `can_access_project` | R3 | PRJM-CA-23 … CA-25, CA-30, CA-31, CA-33 |
| `_get_project_or_404` | R1 | PRJM-GN-01 … GN-06 |
| `require_project_access` | R1 / Errors R1 | PRJM-RA-04, RA-05, RA-06 |
| `require_project_access` | R2 / Errors R2 | PRJM-RA-03 |
| `require_project_access` | R3 [BUG-1278, BUG-1954] / Errors R3 | PRJM-RC-09, LM-06, AM-17, RM-12, G-06 (through callers; Spec gap 4) |
| `require_project_access` | R4 | PRJM-RA-01, RA-02, RA-07 |
| `require_component_access` | R1 | PRJM-RC-01, RC-04 … RC-07 |
| `require_component_access` | R2 [BUG-1278] | PRJM-RC-01, RC-02, RC-09 |
| `require_component_access` | R3 | PRJM-RC-03 |
| `require_component_access` | R4 | PRJM-RC-08 |
| `_format_field_value` | R1 | PRJM-FF-01, FF-02, FF-03, CF-08 |
| `_format_field_value` | R2 | PRJM-FF-04 … FF-07 |
| `_collect_field_changes` | R1 | PRJM-CF-01 … CF-05, CF-09, CF-10 |
| `_collect_field_changes` | R2 | PRJM-CF-01, CF-06, CF-07, CF-08, CF-09 |
| `log_for_component` | R1 | PRJM-LC-05 … LC-08 |
| `log_for_component` | R2 | PRJM-LC-01 … LC-04, LC-09 |
| `log_event` | R1 | PRJM-LE-01, LE-02, LE-10 |
| `log_event` | R2 [BUG-1192] | PRJM-LE-06 … LE-09 |
| `log_event` | R3 | PRJM-LE-03 |
| `log_event` | R4 | PRJM-LE-04, LE-05 |
| `list_events` | R1 | PRJM-EV-05, EV-06, EV-07 |
| `list_events` | R2 | PRJM-EV-04 |
| `list_events` | R3 | PRJM-EV-01, EV-02, EV-03 |
| `list_events` | R4 [BUG-1964] | PRJM-EV-08 (regression: EV-01) |
| `list_members` | R1 [BUG-1278] | PRJM-LM-04, LM-05, LM-06 |
| `list_members` | R2 (incl. DAO BUG-1274) | PRJM-LM-01, LM-02, LM-03 |
| `add_member` | R1 [BUG-1278] | PRJM-AM-02, AM-15, AM-16, AM-17 |
| `add_member` | R2 | PRJM-AM-04 … AM-11, AM-14 |
| `add_member` | R3 | PRJM-AM-03, AM-12, AM-13, AM-14 |
| `add_member` | R4 | PRJM-AM-01, AM-02, AM-03, AM-18 |
| `remove_member` | R1 [BUG-1278] | PRJM-RM-04, RM-10, RM-11, RM-12 |
| `remove_member` | R2 | PRJM-RM-02, RM-05, RM-06, RM-07 |
| `remove_member` | R3 | PRJM-RM-06, RM-08, RM-09 |
| `remove_member` | R4 | PRJM-RM-01 … RM-04, RM-07, RM-13 |
| `set_visibility` | R1 | PRJM-SV-02, SV-06, SV-07 |
| `set_visibility` | R2 | PRJM-SV-04, SV-05 |
| `set_visibility` | R3 | PRJM-SV-03 |
| `set_visibility` | R4 | PRJM-SV-01, SV-02, SV-08 |
| `create_project` | R1 | PRJM-C-07 … C-10 |
| `create_project` | R2 | PRJM-C-05, C-06 |
| `create_project` | R3 | PRJM-C-01, C-02, C-04 |
| `create_project` | R3a | PRJM-C-03, C-27 |
| `create_project` | R4 [BUG-1951] | PRJM-C-11 … C-17 |
| `create_project` | R5 [BUG-1962, BUG-1963] | PRJM-C-18 … C-25 |
| `create_project` | R6 | PRJM-C-26 |
| `get_project` | R1 | PRJM-G-01 … G-05 |
| `get_project` | R2 [BUG-1954] | PRJM-G-06, G-07 |
| `list_projects` | R1 [BUG-1959] | PRJM-L-12, L-13, L-15 |
| `list_projects` | R1a [BUG-1960] | PRJM-L-14, L-15 |
| `list_projects` | R2 [BUG-1961 deferred] | PRJM-L-16, L-17, L-18 |
| `list_projects` | R3 [BUG-1955] | PRJM-L-19, L-20, L-21 |
| `list_projects` | R4 [BUG-1956] | PRJM-L-22, L-23 |
| `list_projects` | R5 [BUG-1957] | PRJM-L-24 … L-29 |
| `list_projects` | R6 | PRJM-L-01, L-03, L-11 |
| `list_projects` | R7 [BUG-1958] | PRJM-L-02, L-04 … L-10, L-30 |
| `update_project` | R1 | PRJM-U-13 … U-16 |
| `update_project` | R2 | PRJM-U-01, U-04 |
| `update_project` | R2a [BUG-1953] | PRJM-U-17 … U-24 |
| `update_project` | R3 | PRJM-U-10, U-11 |
| `update_project` | R4 | PRJM-U-01 … U-03, U-05, U-07, U-09 … U-11 |
| `update_project` | R5 | PRJM-U-04, U-12 |
| `update_project` | R6 | PRJM-U-01, U-33 |
| `update_project` | R7 [BUG-1951] | PRJM-U-25, U-26, U-27 |
| `update_project` | R8 [BUG-1962, BUG-1963] | PRJM-U-28 … U-32, U-34 |
| `update_project` | R9 [BUG-1952] | PRJM-U-01, U-06, U-08, U-13 |
| `delete_project` | R1 | PRJM-D-04, D-06, D-07 |
| `delete_project` | R2 | PRJM-D-05 |
| `delete_project` | R3 | PRJM-D-01, D-02, D-03, D-08 |
