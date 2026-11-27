# Execution notes — `app/managers/help_ticket_manager.py`

> Cases: `tests/unit/managers/help_ticket_manager.cases.md` (revision 2, 2026-11-26, incl. gap fill R-07 / R-08 and verifier-round U-64) · Tests: `tests/unit/managers/test_help_ticket_manager.py` · Source commit: 41d5ac1
> Result: 194 of 194 cases implemented · 165 passed · 29 xfailed as designed (all strict) · 0 xpassed · 0 discrepancies · 0 errors — branch coverage 100% (85 statements, 24 branches)
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/managers/test_help_ticket_manager.py -q -p no:cacheprovider --cov=app.managers.help_ticket_manager --cov-branch --cov-report=term-missing`

## How the tests are built
Normal mode: no local model. Every test carries `# [claude] <ID>`, a `# Then N` comment per Then line, and the card's rules in its docstring. Tests follow card order exactly (checked by diffing the `### HTM-…` headings against the `# [claude]` comments).

- **Names:** card row names are lower-case here (`T` → `t`, `W1.id` → `w1.id`). `HM`, `OWNER_R`, `GTM_R`, `GT_R`, `FIN_R`, `PENDING`, `OPENED`, `CLOSED`, `SUPPORT`, `FEEDBACK`, `MISSING`, `PAST`, `CLOSE_AT`, `FORBID`, `NOTFOUND`, `STATUS_FORBID` are module constants. `TAG` is the `tag` fixture.
- **Standing rows:** chained fixtures `w0 → w1 → w2 → no_owners → mgr → cr → own → adm → fin`, ending in the autouse `standing_rows`. `no_owners` sets `owner_user_id = None` on all three workspaces and flushes. So W0.id < W1.id < W2.id and MGR.id < CR.id < OWN.id < ADM.id < FIN.id in every test.
- **Given rows:** `mk_ticket(number, **but)` (pending / support by column default), `mk_opened(number, **but)`, `mk_closed(number, **but)` insert and flush. `set_owner(db, ws, profile)` is "owner of W by X" (set, then flush). `mk_pending()` adds P and does **not** flush. P is always the last Given line, so no later `set_owner` flush picks it up.
- **Externals:** `clock()` (C cards) patches `app.dao.help_ticket.datetime` (a `datetime` subclass whose `now()` is 2026-06-01 12:00), `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow`. `close_clock()` patches `app.managers.help_ticket_manager.utcnow` to the aware `CLOSE_AT` around every U card's call except U-17 (real clock). U-62 and U-63 call no manager code (a schema build and a constant), so they have nothing to wrap. `spies(db)` wraps `commit` / `rollback`. Nothing else is mocked.
- **Snapshot vs re-read:** `snap(db, id)` reads the 9 `unchanged` columns (now including `type`) with a Core `select`, so it does not expire or refresh any session object. That keeps the `session:` lines honest: they see T untouched by the test. `unchanged(db, id)` = `expire_all` + `db.get`, the card's re-read. `counts(db, w0, w1, w2)` = "nothing written". With `autoflush=False`, neither of them flushes P.
- **`sql_log` (AC-18):** a `before_cursor_execute` listener on `db.connection()`, removed in `finally`. `t.workspace` is read once before the listener starts, as the revised card says, so the check stays query-free after the BUG-2103 fix reads it.
- **Database errors:** `with pytest.raises(X):` then `with db.begin_nested():` around the call (L-17, L-18, P-09, C-04, C-05, U-29, U-30). Refusals (`HelpTicketForbiddenError`, `HelpTicketStatusChangeForbiddenError`, `HelpTicketInvalidTransitionError`, plain `ValueError`) use a plain `pytest.raises` with no savepoint, as Conventions say.
- **Rolled back (C-06, U-31):** inside `spies`, `sp = db.begin_nested()` right before the call. The `in savepoint` lines and the mock lines run before `sp.rollback()`, and the `after rollback` line runs after it.
- **Schema-bypassing payloads:** `HelpTicketUpdate.model_construct(_fields_set={...}, ...)` (U-11 … U-14, U-29, U-30, U-44, U-45) and `HelpTicketCreate.model_construct(...)` (C-02). Pydantic raises a harmless `PydanticSerializationUnexpectedValue` UserWarning on `model_dump` of a plain-string status. That is expected; the project does not turn warnings into errors.
- **R-07:** `S` is a `SimpleNamespace` built from T's 13 columns, as the card writes it. Reading `created_at` / `updated_at` off the flushed T loads the server defaults first.

## Fails-today check (2026-11-26)
`--runxfail` with a scratch plugin (`htm_failline.py`) that maps each failing line to the `# Then N` comment above it. **29 failed, 164 passed.** Every xfail fails inside the Then its card names and nowhere else:

- AC-20, AC-21, AC-22 (BUG-2103): Then 1, `False is True`.
- G-22 (BUG-2103): the When line raises `HelpTicketForbiddenError`. The card says the call raises, so it fails before the Then 1 check that depends on it.
- L-14, L-15 (BUG-1578): Then 1, the admin sees nothing / only their own TA.
- L-27, L-28, L-30 (BUG-3250): Then 1, only the owner's own ticket / `set()` / `set()`.
- U-17 (BUG-1577): Then 2, 5 h 0 min under `America/New_York`.
- U-18 … U-22, U-25 … U-28, U-52 (BUG-1863): Then 1, `DID NOT RAISE HelpTicketForbiddenError`.
- U-51 (BUG-3251): Then 2, today's text is "Only platform admins may change ticket status.".
- U-53, U-57 … U-60 (BUG-3251): Then 1. `TypeError: update_ticket() got an unexpected keyword argument 'role'` comes out of the Then 1 `pytest.raises` block.
- U-54, U-55, U-56 (BUG-3251): the `result = HM.update_ticket(..., role=…)` line raises `TypeError`, before the `# Then 1` comment. Rule used here: **a `TypeError` at the call counts as failing at the first Then that depends on the call**, which is Then 1 (`result is T`). That is what the cards' "Fails today on: Then 1 (the call raises TypeError …)" means.

The BUG-3251 cards are written for the decided signature `role: str | None = None` (keyword-only). When that lands, the `TypeError` goes away. U-54 … U-60 then test the real grant and refusal rules, and U-53 still needs BUG-1863 too. Plugin and output: `C:\Users\User\AppData\Local\Temp\claude\5703096e36d5cd6b\5dcda696-13dd-4b73-983c-11d3c05a8ed9\scratchpad\` (`htm_failline.py`, `failline.json`). This run used no reference-fix plugin, so lines after each failure point are not proved under the fixes.

## Stability
3 plain runs: 164 passed and 29 xfailed each time. Ruff passes, including `--select F841,F811`. An AST pass found no unused test arguments. UTF-8, LF line endings.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (85 statements, 24 branches).

## Factories added
None. R-08 uses the shared `make_profile(db, name="")`.

## Revision history
- **2026-11-26 — cases revision 2** (merge 41d5ac1: statuses `pending` / `opened` / `closed`, ticket `type`, status rights, transition table; OQ-66 / BUG-3251; then the gap fill adding R-07 / R-08).
  - **Why:** the revision 1 file no longer imported, because it built `HelpTicketStatusEnum("open")`.
  - **Conventions:** `OPEN` removed. Added PENDING / OPENED / CLOSED, SUPPORT / FEEDBACK, `STATUS_FORBID`, the `no_owners` standing step, `mk_opened` and `set_owner`. `unchanged(T)` now covers `type`. New imports: `HelpTicketStatusChangeForbiddenError`, `HelpTicketInvalidTransitionError`, `ALLOWED_STATUS_TRANSITIONS`, `HelpTicketTypeEnum`. The `BUG_1576` reason is dropped (closed). Added `BUG_2103`, `BUG_3250`, `BUG_3251`.
  - **Rewritten (card revised in place):** AC-18, L-07, L-08, L-09, P-02, P-04, C-01, C-02, U-01, U-06 … U-17, U-23, U-24, U-26, U-31, U-32, R-01, I-01.
    - U-16 is no longer xfail: BUG-1576 is closed and the case is now a passing refusal.
    - U-23 and U-24 are no longer xfail: they pass under R4a, where the status refusal fires first.
    - U-07 is now a refusal.
  - **Added:** AC-20 … AC-25, G-22, L-20 … L-30, P-12 … P-14, C-07, U-33 … U-63, R-04 … R-08.
  - **Retired:** none.
  - **Unchanged tests kept as they were:** VA-*, AC-01 … 17, AC-19, G-01 … 21, L-01 … 06, L-10 … 19, P-01, P-03, P-05 … 11, Q-*, C-03 … 06, U-02 … 05, U-18 … 22, U-25, U-27 … 30, R-02, R-03, I-02 … 05. They pick up the new conventions through the shared helpers.

- **2026-11-26 — verifier round: HTM-U-64 added** (a pass card after U-63: closing an opened ticket that already has stamps overwrites `closed_by` / `closed_at` with the admin and `CLOSE_AT`). One new test, no other test changed. Re-run: 165 passed, 29 xfailed, 100% branch coverage. `--runxfail`: 29 failed, 165 passed, the same 29 xfails on the same Then lines, and U-64 passes.

## Notes for maintainers
- **When a bug is fixed**, its strict xfails XPASS (strict → failed); remove their markers.
  - BUG-1863: U-18 … U-22, U-25 … U-28, U-52. U-53 also needs BUG-3251.
  - BUG-3251: U-51, U-53 … U-60. This needs `role: str | None = None` on `update_ticket`. If `role` became required, every passing `update_ticket` card would break with `TypeError`.
  - BUG-2103: AC-20 … 22, G-22. BUG-3250: L-27, L-28, L-30. BUG-1578: L-14, L-15. BUG-1577: U-17.
  - Kept passing beside them, and must stay green after the fixes: AC-23 and L-29 (owner of *another* workspace), L-16, U-04 (empty payload), U-23 / U-24, and U-58 … U-60 (refusals once `role` exists).
- U-17 uses the real clock and `SET LOCAL TIME ZONE`. Its xfail margin is 5 h against a 60 s limit, so it is not timing-sensitive.
- P-* cards are scoped by `search=TAG`, because all three workspace names carry TAG. Rows that other runs commit to the shared database cannot match.
- **For the permissions feature:** the access rule is still `can_view_all_tickets` (role in `{"owner", "ground-team-manager"}`) and `can_access_ticket` (platform admin → role → creator). `owner_user_id` is not read anywhere yet (BUG-2103 / BUG-3250).
  - The status right is the `is_platform_admin` flag alone. BUG-3251 adds role owner / ground-team-manager and `owner_user_id`.
  - The text-edit right does not exist yet (BUG-1863).
- **For the notifications feature:** the natural hooks are `create_ticket` (a new pending ticket) and `update_ticket`'s status branch. Every allowed move is now a real transition: same-status requests raise `HelpTicketInvalidTransitionError`, so a notifier there never fires on a no-op. The service owns the commit, so a notification should go out after the service's commit.
