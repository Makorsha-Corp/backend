# Execution notes — `app/managers/help_ticket_manager.py`

> Cases: `tests/unit/managers/help_ticket_manager.cases.md` (revision 1) · Tests: `tests/unit/managers/test_help_ticket_manager.py` · Source commit: e48a092
> Result: 135 of 135 cases implemented · 120 passed · 15 xfailed as designed (all strict) · 0 discrepancies · 0 errors — branch coverage 100% (72 statements, 20 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --cov=app.managers.help_ticket_manager --cov-branch --cov-report=term-missing`

## How the tests are built
Normal mode: no local model. Every test carries `# [claude] <ID>`, a `# Then N` comment per Then line, and the card's rules in its docstring. Same conventions as `tests/unit/services/test_help_ticket_service.py`, plus W0.

- **Names:** card row names are lower-case here (`T` → `t`, `W1.id` → `w1.id`). `HM`, `OWNER_R`, `GTM_R`, `GT_R`, `FIN_R`, `OPEN`, `CLOSED`, `MISSING`, `PAST`, `CLOSE_AT`, `FORBID`, `NOTFOUND` are module constants. `TAG` is the `tag` fixture.
- **Standing rows:** chained fixtures `w0 → w1 → w2 → mgr → cr → own → adm → fin`, ending in the autouse `standing_rows`. So W0.id < W1.id < W2.id and MGR.id < CR.id < OWN.id < ADM.id < FIN.id in every test.
- **Given rows:** `mk_ticket(number, **but)`, `mk_closed(number, **but)` (insert and flush). `mk_pending()` adds P and does **not** flush. Unnamed Given rows are built without a variable.
- **Externals:** `clock()` (C cards) patches `app.dao.help_ticket.datetime` (a `datetime` subclass whose `now()` is 2026-06-01 12:00), `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow`. `close_clock()` (every U card except U-17) patches `app.managers.help_ticket_manager.utcnow` to the aware `CLOSE_AT`. `spies(db)` wraps `commit` / `rollback`. Nothing else is mocked.
- **Snapshot vs re-read:** `snap(db, id)` reads the 8 `unchanged` columns with a Core `select`, so it does not expire or refresh any session object. That matters for the BUG-1863 cards, whose `session:` lines must see T untouched by the test. `unchanged(db, id)` = `expire_all` + `db.get`, the card's re-read. `counts(db, w0, w1, w2)` = "nothing written". With `autoflush=False`, neither of them flushes P.
- **`sql_log` (AC-18):** a `before_cursor_execute` listener on `db.connection()`, removed in `finally`. `Profile.is_platform_admin` has a Python-side default, so it is already in the instance after the flush. Reading it emits no SELECT, which is what makes AC-18 pass.
- **Database errors:** `with pytest.raises(X):` then `with db.begin_nested():` around the call (L-17, L-18, P-09, C-04, C-05, U-29, U-30). BUG-1863 refusals use a plain `pytest.raises` with no savepoint, as Conventions say.
- **Rolled back (C-06, U-31):** inside `spies`, `sp = db.begin_nested()` right before the call. The `in savepoint` lines and the mock lines (Then 3 and 4) run before `sp.rollback()`, and the `after rollback` line runs after it.
- **Schema-bypassing payloads:** `HelpTicketUpdate.model_construct(_fields_set={...}, ...)` (U-11 … U-14, U-29, U-30) and `HelpTicketCreate.model_construct(...)` (C-02). Pydantic raises a harmless `PydanticSerializationUnexpectedValue` UserWarning on `model_dump` of a plain-string status (U-11 … U-14). That is expected; the project does not turn warnings into errors.
- **Spec gap 1 (enum import):** `HelpTicketStatusEnum` and `RoleEnum` come from `app.models.enums`.

## Fails-today check
- `--runxfail`, with a scratch plugin that maps each failing line to its `# Then N` comment: all 15 xfail cards fail inside the Then their card names. None fails anywhere else.
  - L-14: `set() == {TM, TC}`, so the admin sees nothing. L-15: only the admin's own TA.
  - U-16: `closed_by` was rewritten to OWN.id.
  - U-17: `closed_at - created_at` = 5 h 0 min under `America/New_York`.
  - U-18 … U-28: `DID NOT RAISE HelpTicketForbiddenError` on the Then 1 `pytest.raises` line.
- **Reference fixes:** a second scratch plugin, never in `app/`, patches `HelpTicketManager.update_ticket` and `list_tickets` in process with the intended behavior:
  - BUG-1863: a text field sent by a non-creator raises before any write.
  - BUG-1576: closing a closed ticket is a no-op.
  - BUG-1577: an aware-UTC `closed_at`.
  - BUG-1578: a platform admin gets no creator filter.

  With `--runxfail` + that plugin, **135 passed**. Every line after each failure point ran and holds under the fix (session state, pending P, re-read, counts).
- Plugins and outputs are in `C:\Users\User\AppData\Local\Temp\makorsh-pipeline\mgr6e\help\` (`htm_failline.py`, `htm_fix.py`, `failline.json`).

## Stability
3 plain runs: 120 passed and 15 xfailed each time, with the same outcome for every test. Ruff: all checks pass, including `--select F841,F811`. An AST pass found no unused test arguments. LF line endings. The file-level `noqa` (SIM117, DTZ001) is the same as in the service tests.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage.

## Factories added
None.

## Notes for maintainers
- When BUG-1863 is fixed, U-18 … U-28 XPASS (strict → failed): remove their markers. U-04, U-06 and U-08 must stay green: an empty payload and a close / reopen by a non-creator are not refusals. The same goes for BUG-1576 (U-16), BUG-1577 (U-17) and BUG-1578 (L-14, L-15). L-16 holds before and after BUG-1578.
- U-17 uses the real clock and `SET LOCAL TIME ZONE`. Its xfail margin is 5 h against a 60 s limit, so it is not timing-sensitive.
- P-01 … P-11 are scoped by `search=TAG`, because all three workspace names carry TAG. Rows that other runs commit to the shared database cannot match.
- **For the permissions feature:** the whole access rule is two static methods, `can_view_all_tickets` (role in `{"owner", "ground-team-manager"}`) and `can_access_ticket` (platform admin → role → creator). `role` is trusted as passed: BUG-1885 (suspended membership) lives in the endpoint's `_workspace_role`. Three things are not settled today:
  - **Edit-right:** it does not exist yet (BUG-1863). The fix needs a separate "may edit text" check (creator only), apart from "may see / close".
  - **List rule:** `list_tickets` does not reuse `can_access_ticket` (BUG-1578). A shared predicate would keep the list and the get in step.
  - **Attachments:** `AttachmentManager` calls neither helper (BUG-1950, spec FU-1).
- **For the notifications feature:** the manager sends nothing. The natural hooks are `create_ticket` (new ticket → platform support inbox) and `update_ticket`'s status branch. Notify only on a real transition: after BUG-1576, a repeat close changes nothing and must not notify again. The service owns the commit, so a notification should go out after the service's commit, not from the manager.
