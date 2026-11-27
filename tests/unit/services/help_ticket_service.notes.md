# Execution notes — `app/services/help_ticket_service.py`

> Cases: `tests/unit/services/help_ticket_service.cases.md` (revision 4, 2026-11-26) · Tests: `tests/unit/services/test_help_ticket_service.py` · Source commit: 41d5ac1
> Result: 158 of 158 cases implemented · 119 passed · 39 xfail as designed (38 strict, all xfailed; 1 non-strict, L-16, xfailed in every run) · 0 xpass · 0 errors · 0 discrepancies — branch coverage 100%
> Run: `.venv/Scripts/python.exe -m pytest tests/unit/services/test_help_ticket_service.py -q -p no:cacheprovider`

## How the tests are built
Same form as `item_tag_service.notes.md`: one test per card, in card order, `# [claude] <ID>` above each, `# Then N` before the checks of Then line N.
- **Standing rows** (autouse `standing_rows`, chained fixtures so the order is fixed): `w1` "Gamma {TAG}", `w2` "Delta {TAG}", then profiles `mgr` Karim, `cr` Rahim, `own` Owen, `adm` Sam (`is_platform_admin=True`), `fin` Fatima. `tag` = `uuid4().hex[:8]` per test. No memberships: the role is an argument.
- **Constants:** `PENDING`, `OPENED`, `CLOSED` (`HelpTicketStatusEnum`), `SUPPORT`, `FEEDBACK` (`HelpTicketTypeEnum`), roles, `MISSING`, `PAST`, `FORBID`, `NOTFOUND`; one `BUG_n` reason string per bug, titled as in `docs/testing/bugs.md`.
- **Given rows:** `mk_ticket(number, **but)` (W1, "Printer jam" / "It jams" / "hardware", created by CR; `status` and `type` left to the model defaults `"pending"` / `"support"`), `mk_opened(number, **but)` (status opened), `mk_closed(number, **but)` (status closed, `closed_at` PAST, `closed_by` MGR). `commit_point(db)` = `db.commit()`, which only releases a savepoint under the `db` fixture. `mk_extra()` (extra row X, returns `X_ID`), `mk_extra_row()` (the same row, returns X itself, for cards with `session: X not in db`) and `mk_pending()` (pending P) are added after the commit point and not committed.
- **Externals:** `clock(now, utc)` patches `app.dao.help_ticket.datetime` (a `datetime` subclass with a fixed `now()`), `app.dao.help_ticket.utcnow` (`create=True`) and `app.utils.time.utcnow`; every C card runs its When inside it, C-05 with its own two values. `close_clock()` patches `app.managers.help_ticket_manager.utcnow`; every U and V card runs its When inside it except U-11 and V-22 (real clock, `SET LOCAL TIME ZONE 'America/New_York'` first).
- **Checks:** `reread` (expire_all + `db.get`), `snap` (the eight fields of `unchanged(T)`, `type` included since revision 3, taken at the commit point and after the call), `counts` (W1, W2 row counts = "nothing written"), `x_gone`, `idset`, `own_ids`, `committed` (fresh SELECT after the one test-level `db.rollback()`), `spies`, `rollback_spy` (refusal spy: the test's `pytest.raises(<Type>)` wraps it, no savepoint), `failing_commit`, `failing_refresh`, `seqscan`. Ids are copied to locals at the commit point, so later reads never depend on an expired instance.
- **`session: X not in db`** is the first check after the raise (U-35, U-48, V-05, V-08, V-12): the service's rollback expunges the flushed-but-uncommitted X.
- **Plain-string status** (U-54, U-55) is built with `HelpTicketUpdate.model_construct(status=...)`; pydantic warns at `model_dump` (`PydanticSerializationUnexpectedValue`) because a str sits in an enum field — expected, harmless. `type` in the request (U-56, V-17) is dropped by `model_validate` (the schema ignores unknown keys).
- **DB errors:** C-02's unknown user fails at the FK on flush; the service's rollback is what the card checks, so no test savepoint. L-15 and P-07 wrap the call in `db.begin_nested()` as the Conventions say.

## Fails-today check
`--runxfail` with a scratch plugin (`thenmap.py`) that maps the last failing test-file line to the `# Then N` comment above it. Every xfail fails on the Then line its card names, with the value the card describes:
- C-05: Then 2, `'HELP-2027-001'`. C-06: Then 2, `'  Printer  '`. C-09, U-29: Then 2, `'   ' is None`. U-26, V-21: Then 2, `'  Toner low  '`.
- C-07, C-08, U-27, U-28, U-30, U-31: Then 1, `DID NOT RAISE ValidationError`.
- L-12: Then 1, `set()`. P-05: Then 1, T2 matches `_` too. L-16 (non-strict): Then 1, `[TA, TC, TB]` physical order, in every run.
- U-11, V-22: Then 2, `timedelta(seconds=18000, …)`.
- U-16 … U-21, U-23 … U-25, U-58: Then 1, `DID NOT RAISE HelpTicketForbiddenError`. V-11, V-12, V-14, V-15 (BUG-3270): Then 1, the same.
- BUG-3251: U-04, U-05, U-38, U-39, U-40, U-41, U-43 fail with `HelpTicketStatusChangeForbiddenError: Only platform admins may change ticket status.` raised by the When call whose result Then 1 checks — before the first assertion, as the cards' "Fails today on: Then 1 (the call raises …)" says (the plugin reports "before any Then"). U-42: Then 1, the same error escapes `pytest.raises(HelpTicketInvalidTransitionError)`.

## Discrepancies
None.

## Coverage gaps
None — 100% branch coverage (57 statements, 2 branches: the `ticket is None` check of `update_platform_ticket`). The "re-read finds nothing" fallback (`refreshed or ticket`, lines 48, 123, 150) is covered as a line, but its `ticket` side is never used: `unreachable` in unit tests — the spec marks it not unit-testable (revision 2026-11-04, extended to L150 2026-11-26).

## Factories added
None.

## Notes for maintainers
- When a bug is fixed its cards XPASS: remove the marker. BUG-1574 / BUG-1575 live in `app/schemas/help_ticket.py`; BUG-1577, BUG-1578, BUG-1863, BUG-3251 in `app/managers/help_ticket_manager.py` (BUG-3251 also needs the service to pass `role`); BUG-3270 in the manager plus `app/api/v1/endpoints/platform_help.py`; BUG-1441 … BUG-1443 in `app/dao/help_ticket.py`.
- Once BUG-3251 is fixed, U-22 and U-57 (passing today with `HelpTicketStatusChangeForbiddenError`) must still pass: after the fix the refusal becomes `HelpTicketForbiddenError` from the text check (BUG-1863); both cards accept either.
- BUG-1441's fix must look `utcnow` up on `app.dao.help_ticket` (the clock patch uses `create=True` there and also patches `app.utils.time.utcnow`), or C-01 / C-05 will see the real year.
- U-11 / V-22 depend on the real clock and on `created_at` being the transaction start: the outer test transaction opens milliseconds before the close, far below the 60 s the card allows.
- L-16 is non-strict: it rests on the physical order after an UPDATE under seqscan.
- Platform list cards search by TAG (the workspace names carry it), so rows of other tests running side by side never match; P-05 searches `_` and compares only its own two ids; P-12's W3 "Omega" carries no TAG on purpose.

## Revision history
- **Revision 4 (2026-11-26)** — cases revision 4 (from `help_ticket_service.verify.md` Round 2026-11-26). Added 4 pass tests in card order, no existing test changed: HTS-U-60 (a `SimpleNamespace(id=CR.id, name="Rahim")` caller without `is_platform_admin` is refused a status change, `HelpTicketStatusChangeForbiddenError`, nothing written), HTS-U-61 (the same object as creator changes the title; committed), HTS-U-62 and HTS-V-23 (`HelpTicketUpdate.model_construct(title=None)` → `IntegrityError` before the commit; `X not in db`, x_gone, nothing written, session usable, T unchanged). All four pass. Re-verified: 119 passed / 39 xfailed in each of 3 plain runs; `--runxfail` gives the same 39 failures on the same Then lines as revision 3; branch coverage 100%; ruff check and format clean. No discrepancies.
- **Revision 3 (2026-11-26)** — cases revision 3 (merge of `origin/main`: `pending | opened | closed` workflow, `type`, `update_platform_ticket`). The old file did not import (`HelpTicketStatusEnum("open")`).
  - **Scaffold:** `OPEN` removed; `PENDING`, `OPENED`, `CLOSED`, `SUPPORT`, `FEEDBACK` added; imports of `HelpTicketStatusChangeForbiddenError`, `HelpTicketInvalidTransitionError`, `HelpTicketTypeEnum`; new `mk_opened`, `mk_extra_row`, `rollback_spy`; `unchanged(T)` now includes `type`; close clock covers V cards; `BUG_1576` reason removed (resolved), `BUG_3251`, `BUG_3270` added.
  - **Revised tests:** C-01 (pending, `type`, new Then 8; renamed slug), G-01, U-01, U-03, P-02 (`pending` / `support`); L-08 (`opened` filter, pending row added); U-04 (opened ticket, `status=CLOSED`), U-05 (`status=OPENED`) → strict xfail BUG-3251; U-06 (admin closes an opened ticket, Then 1–4); U-09 (`opened → opened` refused 400, nothing written); U-10 (admin, `closed → closed` refused, stamps kept — now a pass, BUG-1576 resolved); U-11 (admin closes an opened ticket); U-16 (docstring: Errors row 7); U-22 (manager text + close → `PermissionError`, now a pass); U-33, U-34 (admin closes an opened ticket).
  - **Added:** C-11; L-17 … L-23; G-17 … G-19; U-35 … U-59; V-01 … V-22; P-09 … P-14; Q-05, Q-06. No retired ids.
  - Re-verified: 115 passed / 39 xfailed in each of 3 plain runs; `--runxfail` gives 39 failures, each on its card's Then line (above); branch coverage 100%; `ruff check` and `ruff format` clean; no unused test arguments (AST pass). The reference plugin of revision 2 (`refplug_help_ticket.py`) was not re-run: it patched the pre-merge manager and would need rewriting for BUG-3251 / BUG-3270.
- **Revision 2 (2026-11-04)** — cases revision 2 (from `help_ticket_service.verify.md` finding 1). Added `test_hts_p_08__the_platform_lists_default_limit_is_100` (HTS-P-08: 101 tickets titled `T{k} {TAG}`, `list_platform_tickets(db, search=TAG)` without a limit, `len(own(result)) == 100`); passes. No existing test changed; no card changed or retired. Gap 2 is closed by the spec (not unit-testable), recorded under Coverage gaps. Re-verified: 62 passed / 26 xfailed in each of 3 plain runs; `--runxfail` shows the same 26 failures on the same Then lines as revision 1; the reference plugin needed no change and gives 88 passed under `--runxfail`, test-file line coverage 890/891 (only the fake `datetime.now()`); branch coverage of the service 100%; ruff check and format clean; LF.
