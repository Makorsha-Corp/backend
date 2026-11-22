# Execution notes — `app/services/help_ticket_service.py`

> Cases: `tests/unit/services/help_ticket_service.cases.md` (revision 2) · Tests: `tests/unit/services/test_help_ticket_service.py` · Source commit: e48a092
> Result: 88 of 88 cases implemented · 62 passed · 26 xfail as designed (25 strict, all xfailed; 1 non-strict, L-16, xfailed in every run) · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `item_tag_service.notes.md`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows** (autouse `standing_rows`, chained fixtures so the order is fixed): `w1` "Gamma {TAG}", `w2` "Delta {TAG}", then profiles `mgr` Karim, `cr` Rahim, `own` Owen, `adm` Sam (`is_platform_admin=True`), `fin` Fatima. `tag` = `uuid4().hex[:8]` per test. No memberships: the role is an argument.
- **Given rows:** `mk_ticket(number, **but)` (W1, "Printer jam" / "It jams" / "hardware", created by CR), `mk_closed(number, **but)` (status closed, `closed_at` PAST, `closed_by` MGR). `commit_point(db)` = `db.commit()`, which only releases a savepoint under the `db` fixture; every write card and every update error card commits its Given rows before the When, so the service's rollback cannot take them away. `mk_extra()` (extra row X, returns `X_ID`) and `mk_pending()` (pending P) are added after the commit point and not committed.
- **Externals:** `clock(now, utc)` patches `app.dao.help_ticket.datetime` (a `datetime` subclass with a fixed `now()`), `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow`; every C card runs its When inside it, C-05 with its own two values. `close_clock()` patches `app.managers.help_ticket_manager.utcnow`; every U card except U-11 (real clock, `SET LOCAL TIME ZONE 'America/New_York'` first) runs its When inside it.
- **Checks:** `reread` (expire_all + `db.get`), `snap` (the seven fields of `unchanged(T)`, taken at the commit point and after the call), `counts` (W1, W2 row counts = "nothing written"), `x_gone`, `idset`, `own_ids`, `committed` (fresh SELECT after the one test-level `db.rollback()`), `spies`, `failing_commit`, `failing_refresh`, `seqscan`. Ids are copied to locals at the commit point, so later reads never depend on an expired instance.
- **DB errors:** C-02's unknown user fails at the FK on flush; the service's rollback is what the card checks, so no test savepoint. L-15 and P-07 wrap the call in `db.begin_nested()` as the Conventions say.
- `HelpTicketStatusEnum` (spec gap 1) is imported from `app.models.enums`, where `app/schemas/help_ticket.py` takes it.

## Fails-today check
`--runxfail` with a scratch plugin that maps the failing test-file line to its `# Then N`. Every xfail fails on the Then line its card names, with the value the card describes:
- C-05: Then 2, `'HELP-2027-001'` (local clock's year). C-06: Then 2, `'  Printer  '`. C-09, U-29: Then 2, `'   ' is None`. U-26: Then 2, `'  Toner low  '`.
- C-07, C-08, U-27, U-28, U-30, U-31: Then 1, `DID NOT RAISE ValidationError`.
- L-12: Then 1, `set()` (the admin sees none). P-05: Then 1, T2 matches `_` too.
- L-16 (non-strict): Then 1, `[TB, TC, TA]` — physical order after the update, in every run.
- U-10: Then 2, `closed_by` = OWN's id instead of MGR's. U-11: Then 2, `timedelta(seconds=18000)`.
- U-16 … U-25: Then 1, `DID NOT RAISE HelpTicketForbiddenError`.

## Reference run
`refplug_help_ticket.py` (scratch, loaded with `-p`, PYTHONPATH = scratch folder) patches in memory, before the test module is imported: `HelpTicketCreate` / `HelpTicketUpdate` subclasses that trim, refuse blank title / description, store blank category as `None` and refuse null title / description in an update (BUG-1574, BUG-1575); DAO `create_with_user` taking the year from `utcnow()` (BUG-1441); `list_by_workspace` / `list_platform` ordered by `created_at DESC, id DESC` (BUG-1442) and `list_platform` escaping `%`, `_`, `\` (BUG-1443); manager `list_tickets` admitting platform admins (BUG-1578); manager `update_ticket` refusing text fields from anyone but the creator (BUG-1863), leaving a closed ticket's stamps alone (BUG-1576) and writing `closed_at` as aware UTC (BUG-1577).
- With `--runxfail`: **88 passed** (revision 2; 87 at revision 1). Without it: the 25 strict cards XPASS (strict → failed) and L-16 XPASSes.
- Test-file line coverage, to show the lines past each failure point run: today 39 lines of the test file are never reached (the checks after each failing Then); with the reference plugin and `--runxfail` only one line is missed (line 221 at revision 2), the fake `datetime.now()`, which the fixed DAO no longer calls.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (45 statements; the service has no `if`). The "re-read finds nothing" fallback of `create_ticket` R3 / `update_ticket` R7 (`refreshed or ticket`, spec gap 2) is one expression: its line is covered, but the `ticket` side is never used, because no card patches the DAO's `get_by_id` (not an external). Kind: `unreachable` in unit tests — the spec (revision 2026-11-04) marks it not unit-testable and cases Revision 2 closed gap 2 with no card.

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. BUG-1574 / BUG-1575 live in `app/schemas/help_ticket.py`; BUG-1576, BUG-1577, BUG-1578, BUG-1863 in `app/managers/help_ticket_manager.py`; BUG-1441 … BUG-1443 in `app/dao/help_ticket.py`.
- BUG-1441's fix must look `utcnow` up on `app.dao.help_ticket` (the clock patch uses `create=True` there and also patches `app.utils.time.utcnow`), or C-01 / C-05 will see the real year.
- U-11 depends on the real clock and on `created_at` being the transaction start: the outer test transaction opens a few milliseconds before the close, far below the 60 s the card allows.
- L-16 is non-strict: it rests on the physical order after an UPDATE under seqscan.
- Platform list cards search by TAG (the workspace names carry it), so rows of other tests running side by side never match; P-05 searches `_` and compares only its own two ids.

## Revision history
- **Revision 2 (2026-11-04)** — cases revision 2 (from `help_ticket_service.verify.md` finding 1). Added `test_hts_p_08__the_platform_lists_default_limit_is_100` (HTS-P-08: 101 tickets titled `T{k} {TAG}`, `list_platform_tickets(db, search=TAG)` without a limit, `len(own(result)) == 100`); passes. No existing test changed; no card changed or retired. Gap 2 is closed by the spec (not unit-testable), recorded under Coverage gaps. Re-verified: 62 passed / 26 xfailed in each of 3 plain runs; `--runxfail` shows the same 26 failures on the same Then lines as revision 1; the reference plugin needed no change (P-08 is a pass case, TAG is hex so BUG-1443's escaping does not touch it) and gives 88 passed under `--runxfail`, test-file line coverage 890/891 (only the fake `datetime.now()`); branch coverage of the service 100%; ruff check and format clean; LF.
