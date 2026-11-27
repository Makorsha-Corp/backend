# Tester pre-check: dao-help_ticket

Date: 2026-11-27 (batch 3). Source `app/dao/help_ticket.py`. Spec `tests/unit/dao/help_ticket.spec.md`.
Database `bf_dao_help_ticket_test`.

Search: I grepped the bare numbers `1440`–`1443` in `tests/**/*.py`. The markers use reason
constants `BUG_1441`, `BUG_1442`, `BUG_1443` (defined in both files below) in
`pytest.mark.xfail(strict=..., reason=BUG_14xx)`. No test names BUG-1440.

Caller test files (found with Grep for `help_ticket_dao`, `create_with_user`, `list_platform`,
`list_by_workspace`, `generate_ticket_number`, `help_ticket`):
- `E:\Projects\Makorsh-Corp\backend\tests\unit\dao\test_help_ticket.py` (unit's own)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\services\test_help_ticket_service.py` (targets)
- `E:\Projects\Makorsh-Corp\backend\tests\unit\managers\test_help_ticket_manager.py` (no target; its C cards run `create_with_user` under a clock helper)
- `E:\Projects\Makorsh-Corp\backend\tests\test_help_tickets.py`, `E:\Projects\Makorsh-Corp\backend\tests\test_help_platform.py` (legacy; no target)
- Use only the base lookup (`get_by_id_and_workspace`, unchanged), no target: `tests\unit\managers\test_attachment_manager.py`, `test_attachment_markup_manager.py`, `test_mobile_upload_session_manager.py`, `tests\unit\services\test_attachment_service.py`, `test_attachment_markup_service.py`, `test_discussion_service.py`, `test_mobile_upload_service.py`, `tests\unit\utils\test_notification_entity_label.py`.

Run today with `--runxfail`: all 13 targets fail, each on the Then its card names.

Candidate fixes swapped in with a scratch plugin (no `app/` edit), run over the 5 files above
(own, service, manager, 2 legacy):

| Candidate | Result |
|---|---|
| none (today) | 440 passed, 78 xfailed |
| `utcnow()` (module import), `ORDER BY created_at DESC, id DESC` in both lists, search escaped (`\`, `%`, `_`) with `escape='\'`, **unused `datetime` import kept** | exactly the 13 targets flip (8 strict, 5 non-strict); nothing else changes |
| same, **unused `datetime` import removed** (the clean fix) | 33 failed: every clock test errors in `mock.patch` (`app.dao.help_ticket` has no `datetime`) |
| clean fix, with the correction in `wrong-tests.md` applied | exactly the 13 targets flip; nothing else changes |

## BUG-1440: numbering race — not in this unit (no test)

No test names it. Spec `create_with_user` R3 says "Not unit-testable with one connection: no
case". Without a test the flip check cannot see the fix, and nothing is ever committed in the
suite, so a real two-transaction test is out. Also: the row allows "retry on the unique
violation", but R4 (a taken number raises `IntegrityError` 23505, nothing saved) has passing tests
(HLP-CW-04, HTM-C-05); a retry fix would flip them and the flip check would reject it, while a
lock-based fix keeps them. **Skipped this round** and listed out of scope in the brief. A later
round needs (a) a decision that the fix is a lock (advisory transaction lock per workspace+year,
or a counter row read `FOR UPDATE`), or an R4 change if it is a retry, and (b) a check that can
tell it from a racy shortcut (e.g. a SQL-text check for the lock statement, or a two-connection
test with `pg_try_advisory_xact_lock` / `lock_timeout`). Not a wrong test: a missing one.

## BUG-1441: the year comes from the local clock

| File | Tests | Strict |
|---|---|---|
| DAO | HLP-CW-03 | yes; fails on Then 2 (`HELP-2027-001`, not `HELP-2026-001`) |
| service | HTS-C-05 | yes; fails on Then 2 (same) |

Verdict: **right check, wrong helper → entry in `docs/bugfix/wrong-tests.md`** (conditional keep).
The expected value is a patched constant (local 1 Jan 2027 05:00, UTC 31 Dec 2026 23:00), time-zone
independent (A14). The patch targets are `app.dao.help_ticket.utcnow` (`create=True`) and
`app.utils.time.utcnow`, so both a module-level `from app.utils.time import utcnow` and a
function-local import pass. But the same helper patches `app.dao.help_ticket.datetime` without
`create=True`, so a fix that removes the then-unused `datetime` import breaks 25 passing clock tests
in three files (dao, service, manager). The diff adds `create=True` (3 lines); today's outcome is
unchanged. **Condition:** on `origin/main` before the batch-3 baseline; otherwise skip BUG-1441
this round (remove it from `brief.md`, re-run the firewall).

## BUG-1442: tied `created_at`, no `id` tie-break

| File | Tests | Strict |
|---|---|---|
| DAO | HLP-LW-17, LW-27 | no (forced seqscan + update of the lowest id) |
| DAO | HLP-LW-18 (SQL text) | yes; fails on Then 3 (no `.id` after `ORDER BY`) |
| DAO | HLP-LP-20, LP-26 | no |
| DAO | HLP-LP-21 (SQL text) | yes; fails on Then 3 |
| service | HTS-L-16 | no |

Verdict: **right**, all 7. LW-17 / LP-20 / HTS-L-16 check R5's order on a tie (highest id first);
LW-27 / LP-26 that the id, not the title, decides. LW-18 / LP-21 want `created_at` before `.id` in
the ORDER BY. A normal ORM `HelpTicket.id.desc()` passes; a raw `text("id DESC")` would fail (A11).
The non-strict ones fail today under the forced seqscan, as their cards say.

## BUG-1443: unescaped `%` / `_` / `\` in the platform search

| File | Tests | Strict |
|---|---|---|
| DAO | HLP-LP-11 (`_`), LP-12 (`%`), LP-13 (`\`) | yes; fail on Then 2 / Then 1 |
| service | HTS-P-05 (`_`) | yes |

Verdict: **right**, all 4. They match R6 and HR-8 (all three characters). A shortcut that escapes
only `%` and `_` fails LP-13. Each test puts the text in the title only; the other three fields
(ticket number, description, workspace name) are not checked for escaping. A fix that escapes the
one shared term covers all four, so this is a coverage gap, not a wrong test (SE: check all four
`ilike` calls use the escaped term).

## Outside this unit

- BUG-1440 (above): needs a lock decision (R4 conflicts with "retry") and a test before it can be planned.
- BUG-1577 (`help_ticket_manager.update_ticket` close time) is the manager's clock bug; its tests patch
  `app.managers.help_ticket_manager.utcnow`, untouched here.
- Same helper pattern risk elsewhere: any clock-bug test that patches the *old* name
  (`<module>.datetime`) without `create=True` breaks when the fix drops that import. Worth a grep
  before planning other `local-clock-instead-of-utc` units.

## Notes for the systems engineer

- Year: must come from `utcnow()` (spec R2); `datetime.now(timezone.utc)` written directly would
  also be UTC but is not what the spec names.
- Order: ORM `created_at.desc(), id.desc()` in both lists, before offset/limit; no raw `text()` sort.
- Search: escape `\` first, then `%` and `_`, and pass the escape character to all four `ilike` calls
  (or rely on Postgres's default `\` escape, but explicit is clearer); trimming and the "spaces only
  = no filter" rule (R3, R4) must stay.
- Numbering (`generate_ticket_number`, R4 23505 behaviour) must not change: BUG-1440 is out of scope.

## Note for stage C

Remove the markers of the 13 tests above (constants `BUG_1441`, `BUG_1442`, `BUG_1443` in
`tests/unit/dao/test_help_ticket.py` and `tests/unit/services/test_help_ticket_service.py` go too;
nothing else uses them). Expected flip check: 8 strict xfailed → passed (CW-03, LW-18, LP-11, LP-12,
LP-13, LP-21, HTS-C-05, HTS-P-05), 5 non-strict xfailed → passed (LW-17, LW-27, LP-20, LP-26,
HTS-L-16), nothing else.
