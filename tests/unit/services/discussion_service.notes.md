# Execution notes — `app/services/discussion_service.py`

> Cases: `tests/unit/services/discussion_service.cases.md` (revision 5) · Tests: `tests/unit/services/test_discussion_service.py` · Source commit: e48a092
> Result: 97 of 97 cases implemented · 41 passed · 56 xfailed (54 strict, 2 non-strict: L-12, L-13, both xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_discussion_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `notification_service.notes.md`. This service has no manager, no `BaseService` and no rollback (D1–D4).
- **Standing rows** (autouse `standing_rows`, Conventions order): `w1`, `w2`, `ua` "Ann", `ub` "Bob", `us` "Sue", `uo` "Otto", `memberships` (UA, UB active and US suspended in W1; UO active in W2), `f1`, `f9`, `p1`, `p9`.
- **Given rows:** `mk_msg(**but)`, `mk_reply(parent, **but)`, `mk_msgs(n)` (one `add_all`), `mk_xm()` (XM, called after the commit point), `mk_project(name, **cols)`, `mk_item(**but)`, `mk_stage()`, `mk_purchase(stage)`, `mk_ticket(**but)`; `older`, `bump_d`, `seqscan` run the card's SQL as written; `commit_point` = `db.commit()`.
- **Revision 4 builders:** `mk_person(name, role)` ("person N as R": profile plus an active W1 membership), `mk_admin()` ("admin PA": `is_platform_admin = True`, no membership), `set_owner(db, ws, profile)` ("W1 owner is U"), `mk_private_project(name)` (`visibility "invited_only"`, `created_by UA.id`), `mk_component(project)`, `invite(profile, project)` (a `ProjectMember` row). Cards that spell a row as code (C-32 UC, C-47, C-48, C-51) run that code directly.
- **Reading helpers:** `reread(db, model, id)`, `ids`, `order`, `reply_ids`, `notes(db, mid, recipient=None)` (fresh SELECT, ordered by id; `recipient=` adds the card's `recipient_user_id` filter), `recipients`, `count_discussions` / `count_notifications(**filters)`, `unloaded`, `spies`, `record_sql` + `selects_of` (a `before_cursor_execute` listener on the session's connection, DSS-L-14 only).
- **committed:** lines: one `db.rollback()` before the first, then fresh queries. **session:** lines: `pytest.raises(DBAPIError)` (L-04) / `pytest.raises(PendingRollbackError)` (C-26) around `SELECT 1`.
- Patches: only the spies and C-27's failing commit. No race simulation.

## Fails-today check
`--runxfail`, failing line mapped to its `# Then N` by scratch `thenmap.py`, read against each card's "Fails today on":
- X-05: Then 1, `[12, 12] == []`.
- L-08 … L-11, C-19 … C-22, C-24: Then 1 `DID NOT RAISE NotFoundError` (the thread is listed / the message stored).
- L-12 (non-strict): Then 2, order `[R3, R2, R1]` — the updated R1 comes last.
- L-13 (non-strict): Then 2, `[B, C, A]` — the updated A comes last.
- L-14: Then 2, no `parent_id IN` statement during the call.
- C-07: Then 2, recipients `[UA, UB]`. C-08: Then 3, preview `'@Bob @Otto'`.
- C-09 … C-15, C-23, C-50: Then 1, `TypeError: APIException.__init__() missing 2 required positional arguments: 'error_type' and 'title'`.
- L-15, L-16, L-28, L-32, L-33: Then 1, `TypeError: DiscussionService.list() got an unexpected keyword argument 'user_id'` (inside the `raises:` wrap).
- L-18 … L-27, L-29 … L-31: the same `TypeError`, raised by the When call just before `# Then 1` (these cards bind `result = svc.list(...)`, so the call cannot sit inside Then 1). The error is the one their "Fails today on" names.
- C-28, C-29, C-42, C-46 … C-49, C-51, C-57, C-58: Then 1 `DID NOT RAISE NotFoundError` (the message is stored).
- C-52, C-53, C-54: Then 4, `1 == 0` (UB is notified). C-55: Then 3, `1 == 0`.

## Reference run
Scratch plugin `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\svc3e\discussion\refplug.py` (`PYTHONPATH=<folder> pytest -p refplug`) patches in-process, never in `app/`:
- ASCII-only `@\[([0-9]+)\]` in both `discussion_service` and `notification_service` (BUG-1536);
- a record check by `entity_type` table (project `is_deleted`, item `is_active`, purchase order, component and help ticket none, machine `is_deleted`) in the workspace, before the parent checks, raising `NotFoundError("Record not found")` (BUG-1686, BUG-1687);
- `NotFoundError` / `ValidationError` for the three reply refusals (BUG-1694);
- the preview names only profiles with a membership in the workspace (BUG-1534); the author is dropped from the mentions (BUG-1535);
- `get_by_entity` orders by `created_at, id`, loads `replies` with an explicit `selectinload` and sorts them by `created_at, id` (BUG-1438, BUG-1439, BUG-1490);
- revision 4: `list` gains `user_id=None`; after the record check, `list` (when `user_id` is given) and `create` refuse with `NotFoundError("Record not found")` a caller who may not open the record — a private project or its component: workspace owner, active `owner` / `ground-team-manager` member, the project's creator or a `project_members` row of that project (as `ProjectManager.can_access_project`); a help ticket: platform admin, active `owner` / `ground-team-manager` member, or its creator (as `HelpTicketManager.can_access_ticket`); other types: no check (BUG-1867, BUG-1868). The mention list drops anyone who may not open the record (BUG-1879). BUG-1880 is in `status_service` and touches no discussion code, so it is not patched here.

With `--runxfail`: **97 passed** — every line past each failure point runs and holds. Without `--runxfail`: 54 strict XPASS(strict) failures, 2 non-strict XPASSes, 41 passed.

## Stability
3 plain runs and one with `PGOPTIONS=-c enable_seqscan=off`: 41 passed, 56 xfailed each; no test moved. Ruff passes; LF only.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (34 statements, 10 branches).

## Factories added
None.

## Revision history
- **Revision 3 (2026-11-04)**, from `discussion_service.verify.md`:
  - R-DS-1 (executor fix): in DSS-C-01, `mid = result.id` is now read after the Then 1 `loaded:` checks; reading `result.id` first reloaded an expired object and hid a missing refresh. Proof: scratch variant `norefresh.py` (makes the service's `db.refresh` a no-op, `-p norefresh`) fails C-01 at Then 1, `'id' in inspect(result).unloaded`; without the variant C-01 passes.
  - New cards: DSS-L-17 (`limit=51` of 52 roots gives 51 and total 52), DSS-C-30 (a parent of another workspace: today's `TypeError` or `NotFoundError`, no commit, no rollback, XM kept, nothing written), DSS-C-31 (the same for a parent on another record type, `TypeError` or `AppValidationError`), DSS-C-32 (UB and a new active member UC are notified, the suspended US is not). All four pass. No other test changed.
  - Checks: 3 plain runs plus one with `enable_seqscan=off`: 31 passed, 23 xfailed each. `--runxfail`: the same 23 fail on the same Then lines as listed above. `refplug.py` with `--runxfail`: 54 passed (no extension needed). Coverage still 100%. Ruff passes; LF only.
- **Revision 4 (2026-11-04)**, after the owner's answers to OQ-5 / OQ-13:
  - Rewritten as refused callers, strict xfail: L-15 (BUG-1867), L-16 (BUG-1868), C-28 (BUG-1867), C-29 (BUG-1868).
  - New tests: L-18 … L-31 (all strict xfail; they pass `user_id`), C-33 … C-41, C-43 … C-45, C-56 (pass), C-42, C-46 … C-51 (strict xfail BUG-1867 / BUG-1868), C-52 … C-55 (strict xfail BUG-1879). New builders as listed above; `mk_ticket` takes overrides; `notes` takes `recipient=`.
  - `Rules:` docstrings: `create` Errors rows 2 … 5 renumbered 3 … 6.
  - Checks: 3 plain runs plus one with `enable_seqscan=off`: 40 passed, 52 xfailed each. `--runxfail`: 52 failed, each on the Then line its card names (list above). `refplug.py` extended for BUG-1867, BUG-1868, BUG-1879: with `--runxfail` 92 passed. The R-DS-1 variant `norefresh.py` still fails C-01. Coverage 100%. Ruff passes; LF only.
- **Revision 5 (2026-11-04)**, from `discussion_service.verify.md` round 3:
  - New tests: L-32 and C-57 (a platform admin is refused on a private project, strict xfail BUG-1867); L-33 and C-58 (a suspended member with role owner is refused on a help ticket they did not create, strict xfail BUG-1868); C-59 (a suspended creator posts on their ticket, pass). Rows the cards spell as code (UQ, UZ and their memberships) run directly. No other test changed.
  - Fails today: L-32, L-33 at Then 1 with the `list` `user_id` `TypeError`; C-57, C-58 at Then 1 `DID NOT RAISE NotFoundError`.
  - `refplug.py` needed no change: it already allows a platform admin on help tickets only and counts a role only for an active membership, while a ticket's creator passes whatever their status. With `--runxfail` 97 passed; without it, 54 strict XPASS(strict) failures, 2 non-strict XPASSes, 41 passed.
  - Checks: 3 plain runs plus one with `enable_seqscan=off`: 41 passed, 56 xfailed each. `--runxfail`: 56 failed, each on its card's Then line. Coverage 100%. Ruff passes; LF only.

## Notes for maintainers
- When BUG-1694 is fixed, C-16 … C-18, C-30, C-31 keep passing (they accept `TypeError` or the fixed class); C-09 … C-15 XPASS — remove their markers.
- When BUG-1686 is fixed, C-23 needs the record check before the parent check, else it still fails (on the parent's error). Likewise C-50 needs the visibility check before the parent check (BUG-1867).
- When BUG-1867 / BUG-1868 add `user_id` to `list`, all L-15 … L-31 XPASS together; the older `list` cards keep today's call (the cases file says they gain `user_id=UA.id` with the fix — update them then).
- L-12 / L-13 rest on physical row order after an update with index scans off; they are non-strict by design.
